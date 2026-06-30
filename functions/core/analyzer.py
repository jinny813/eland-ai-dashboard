import sqlite3
import json
import pandas as pd
import logging
from core.scoring_logic import AssortmentScorer
from core.comparison_engine import ComparisonEngine
from config.scoring_config import SCORING_CONFIG

logger = logging.getLogger(__name__)

import os

_CATEGORY_LIKE_NAMES = {
    '가방', '백', '파우치', '지갑', '토트백', '숄더백', '크로스백', '클러치', '배낭', '백팩',
    '티셔츠', '티', '반팔티', '긴팔티', '맨투맨', '후드티', '후드',
    '셔츠', '블라우스', '남방',
    '팬츠', '바지', '슬랙스', '청바지', '데님', '반바지', '쇼츠', '레깅스',
    '스커트', '치마', '원피스', '드레스',
    '자켓', '재킷', '점퍼', '코트', '패딩', '아우터', '가디건', '조끼', '베스트',
    '니트', '스웨터',
    '세트', '수트', '정장',
    '신발', '운동화', '스니커즈', '구두', '슬리퍼', '샌들', '부츠',
    '모자', '캡', '비니', '머플러', '스카프', '벨트', '양말',
    '상의', '하의', '이너', '언더웨어',
}

class ActionAnalyzer:
    """
    프로덕션 급 분석 엔진: KPI 지표 부족분 기반 가중치 산출 및 
    상품별 Target_Score를 매겨 최적의 액션 가이드 도출
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # functions/core/ → functions/ → project root → database/
            _base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            _candidate = os.path.join(_base, "database", "product_master.db")
            if not os.path.exists(_candidate):
                _candidate = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "product_master.db")
            db_path = _candidate
        self.db_path = db_path
        self.scorer = AssortmentScorer(SCORING_CONFIG)


    def _get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def get_action_recommendations(self, b_df: pd.DataFrame, bp_brand_df: pd.DataFrame = None) -> dict:
        """
        [v21.0] 사용자 요청 정밀 로직 적용:
        1) 재고 확보 필요: 자사 BEST 10 중 재고 5개 이하 품목
        2) 집중 판매 필요: 자사 BEST 10 중 재고 5개 초과 품목
        """
        if b_df is None or b_df.empty:
            return {"ai_unified": [], "push": [], "has_bp_data": False}

        # 0. 기초 데이터 준비 및 전처리 (품번 문자열화 + 공백 제거)
        b_df = b_df.copy()
        if 'style_code' in b_df.columns:
            b_df['style_code'] = b_df['style_code'].astype(str).str.strip()

        for c in ['sales_qty', 'stock_qty', 'stock_amt', 'normal_price']:
            if c in b_df.columns:
                b_df[c] = pd.to_numeric(b_df[c], errors='coerce').fillna(0)
        
        # 목표 재고액 산출 (TM * 200% * BEST비중 20%)
        tM = float(b_df['tM'].iloc[0]) if 'tM' in b_df.columns else 0.0
        target_total_inv = tM * 2.0
        target_best_inv = target_total_inv * 0.20
        target_per_item = target_best_inv / 10.0

        # 상품 마스터 정보 로드 (명칭 보완용: 스타일 코드 기반 일괄 로드)
        style_codes = b_df['style_code'].unique().tolist()
        if bp_brand_df is not None and not bp_brand_df.empty:
            style_codes += bp_brand_df['style_code'].unique().tolist()
        
        style_codes = list(set(style_codes))
        p_map = {}
        if style_codes:
            try:
                conn = self._get_db_connection()
                codes_str = "', '".join([s.replace("'", "''") for s in style_codes])
                p_master = pd.read_sql(f"SELECT style_code, product_name, category FROM products WHERE style_code IN ('{codes_str}')", conn)
                p_map = p_master.set_index('style_code').to_dict('index')
                conn.close()
            except Exception:
                pass

        # style_master.json 크롤링 캐시 로드
        _style_master = {}
        try:
            _base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            _jsm = os.path.join(_base, "core", "style_master.json")
            if not os.path.exists(_jsm):
                _jsm = os.path.join(os.path.dirname(__file__), "style_master.json")
            if os.path.exists(_jsm):
                with open(_jsm, 'r', encoding='utf-8') as _f:
                    _style_master = json.load(_f)
        except Exception:
            pass

        _empty = {'', '—', '-', 'nan', 'None', 'none'}

        def get_name(sc, row):
            # 1. GSheet 컬럼 (카테고리명 필터)
            for col in ('style_name', 'product_name'):
                v = str(row.get(col, '') or '').strip()
                if v and v not in _empty and v not in _CATEGORY_LIKE_NAMES:
                    return v
            # 2. DB product_name
            if sc in p_map:
                name = str(p_map[sc].get('product_name') or '').strip()
                if name and name not in _empty and name not in _CATEGORY_LIKE_NAMES:
                    return name
            # 3. style_master.json 크롤링 캐시
            if sc in _style_master:
                name = str(_style_master[sc].get('style_name') or '').strip()
                if name and name not in _empty and name not in _CATEGORY_LIKE_NAMES:
                    return name
            # 4. 최후 폴백: 품번
            return sc

        # 1. 자사 판매 BEST 10 추출 및 재고량별 액션 가이드 분류
        agg_dict = {
            'sales_qty': 'sum', 'stock_qty': 'sum', 'stock_amt': 'sum', 'normal_price': 'first'
        }
        for c in ['style_name', 'product_name', 'item_name']:
            if c in b_df.columns:
                agg_dict[c] = 'first'
        
        my_best = b_df.groupby('style_code').agg(agg_dict).sort_values('sales_qty', ascending=False).head(10)

        secure_list = []
        push_list = []

        for sc, row in my_best.iterrows():
            name = get_name(sc, row)
            stock_qty = int(row['stock_qty'])
            
            if stock_qty <= 5:
                # 5개 이하: 확보 필요
                secure_list.append({
                    "rank": len(secure_list) + 1,
                    "icon": "⚠️",
                    "tag": "확보 필요",
                    "style_code": sc,
                    "style_name": name,
                    "action_msg": f"<span style='color:#DC2626; font-weight:800;'>확보 필요 (재고 {stock_qty}개)</span>",
                    "message": f"<b>{name}</b> / {sc} / <b>확보 필요 (재고 {stock_qty}개)</b>",
                    "keywords": ["재고부족", "인기상품", "추가입고"],
                    "sub_info": f"현재고 {stock_qty}EA / 2주 판매 {int(row['sales_qty'])}EA"
                })
            else:
                # 5개 초과: 집중 판매 필요
                push_list.append({
                    "rank": len(push_list) + 1,
                    "style_code": sc,
                    "style_name": name,
                    "sales_qty": int(row['sales_qty']),
                    "stock_qty": stock_qty,
                    "tag": "집중 판매 필요",
                    "reason": f"<span style='color:#F97316; font-weight:800;'>집중 판매 필요 (재고 {stock_qty}개)</span>"
                })

        return {
            "ai_unified": secure_list,
            "push": push_list,
            "has_bp_data": True
        }
