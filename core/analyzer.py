import sqlite3
import pandas as pd
import logging
from core.scoring_logic import AssortmentScorer
from core.comparison_engine import ComparisonEngine
from config.scoring_config import SCORING_CONFIG

logger = logging.getLogger(__name__)

import os

class ActionAnalyzer:
    """
    프로덕션 급 분석 엔진: KPI 지표 부족분 기반 가중치 산출 및 
    상품별 Target_Score를 매겨 최적의 액션 가이드 도출
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # __file__ 기준으로 database/product_master.db의 절대 경로를 안전하게 조립
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "product_master.db")
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
            conn = self._get_db_connection()
            codes_str = "', '".join([s.replace("'", "''") for s in style_codes])
            p_master = pd.read_sql(f"SELECT style_code, product_name, category FROM products WHERE style_code IN ('{codes_str}')", conn)
            p_map = p_master.set_index('style_code').to_dict('index')
            conn.close()

        def get_name(sc, row):
            if sc in p_map: 
                name = p_map[sc]['product_name'] or p_map[sc]['category']
                if name: return name
            return str(row.get('style_name', row.get('product_name', row.get('item_name', sc))))

        # 1. 본 매장(자사) 판매 BEST 10 추출 (재고 확보 필요 상품)
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
            stock_qty = int(row['stock_qty'])
            if stock_qty <= 5:
                name = get_name(sc, row)
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

        # 2. NC 전체 판매 BEST 10 추출 (집중 판매 필요 상품)
        if bp_brand_df is not None and not bp_brand_df.empty:
            nc_best = bp_brand_df.groupby('style_code').agg(agg_dict).sort_values('sales_qty', ascending=False).head(10)
            for sc, row in nc_best.iterrows():
                # 본 매장의 해당 품번 재고 조회
                my_stock_series = b_df[b_df['style_code'] == sc]['stock_qty']
                my_stock = int(my_stock_series.sum()) if not my_stock_series.empty else 0
                
                if my_stock > 5:
                    name = get_name(sc, row)
                    push_list.append({
                        "rank": len(push_list) + 1,
                        "style_code": sc,
                        "style_name": name,
                        "sales_qty": int(row['sales_qty']),
                        "stock_qty": my_stock,
                        "tag": "집중 판매 필요",
                        "reason": f"<span style='color:#F97316; font-weight:800;'>집중 판매 필요 (재고 {my_stock}개)</span>"
                    })

        return {
            "ai_unified": secure_list,
            "push": push_list,
            "has_bp_data": True
        }
