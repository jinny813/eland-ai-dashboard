import sqlite3
import pandas as pd
import logging
from core.scoring_logic import AssortmentScorer
from core.comparison_engine import ComparisonEngine
from config.scoring_config import SCORING_CONFIG

logger = logging.getLogger(__name__)

class ActionAnalyzer:
    """
    프로덕션 급 분석 엔진: KPI 지표 부족분 기반 가중치 산출 및 
    상품별 Target_Score를 매겨 최적의 액션 가이드 도출
    """
    def __init__(self, db_path="database/product_master.db"):
        self.db_path = db_path
        self.scorer = AssortmentScorer(SCORING_CONFIG)

    def _get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def get_action_recommendations(self, b_df: pd.DataFrame, bp_brand_df: pd.DataFrame = None) -> dict:
        """
        [v20.0] 사용자 요청 정밀 로직 적용:
        1) 재고 확보 필요: 자사 BEST 10 중 [재고 < 판매량] 품목 → 목표 재고액 기반 확보 수량 산출
        2) 집중 판매 필요: 전사 BEST 10 중 [현 지점 판매 <= 10개] 품목 → 진열 강화 안내
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

        # 1. 재고 확보 필요 상품 (자사 BEST 10 기반)
        secure_list = []
        # 자사 판매 BEST 10 추출
        agg_dict = {
            'sales_qty': 'sum', 'stock_qty': 'sum', 'stock_amt': 'sum', 'normal_price': 'first'
        }
        for c in ['style_name', 'product_name', 'item_name']:
            if c in b_df.columns:
                agg_dict[c] = 'first'
        
        my_best = b_df.groupby('style_code').agg(agg_dict).sort_values('sales_qty', ascending=False).head(10)
        my_best_codes = [str(c).strip() for c in my_best.index.tolist()]

        for sc, row in my_best.iterrows():
            # [v20.2] 재고가 판매량보다 적거나, 목표 대비 부족한 경우
            if row['stock_qty'] < row['sales_qty'] or row['stock_amt'] < target_per_item:
                price = row['normal_price'] if row['normal_price'] > 0 else 1.0
                shortfall_amt = target_per_item - row['stock_amt']
                qty_by_amt = int(max(0, shortfall_amt) / price)
                qty_by_sales = int(max(0, row['sales_qty'] - row['stock_qty']))
                
                final_secure_qty = max(qty_by_amt, qty_by_sales)
                if final_secure_qty < 3: continue # 너무 적은 수량은 제외
                if final_secure_qty > 50: final_secure_qty = 50 # 최대치 제한
                
                name = get_name(sc, row)
                secure_list.append({
                    "rank": len(secure_list) + 1,
                    "icon": "🏆",
                    "tag": "BEST (TOP 10)",
                    "style_code": sc,
                    "style_name": name,
                    "action_msg": f"{final_secure_qty}장 확보",
                    "message": f"<b>{name}</b> / {sc} / <b>{final_secure_qty}장 확보</b>",
                    "keywords": ["재고부족", "인기상품", "추가입고"],
                    "sub_info": f"현재고 {int(row['stock_qty'])}EA / 2주 판매 {int(row['sales_qty'])}EA"
                })

        # 2. 집중 판매 필요 상품
        push_list = []
        brand_name_raw = b_df['brand_name'].iloc[0] if not b_df.empty else ""

        # [v151.0] JJ지고트 → BP 데이터 유무와 무관하게 무조건 하드코딩 5개 주입
        if "JJ지고트" in brand_name_raw:
            logger.info(f"[{brand_name_raw}] Applying Hard-coded Focus List (unconditional).")
            jj_focus_list = [
                {"rank": 1, "code": "GR3M0TC921", "name": "트렌치 코트",                    "msg": "NC 1위 / 본매장 재고 1EA"},
                {"rank": 2, "code": "GR3A0TCJ11", "name": "레더 디테쳐블 칼라 트렌치 코트", "msg": "NC 2위 / 본매장 재고 13EA"},
                {"rank": 3, "code": "GP4A0OP811", "name": "브레이드 패치 포켓 원피스",       "msg": "NC 3위 / 본매장 재고 16EA"},
                {"rank": 4, "code": "GP4A0OP331", "name": "벨티드 플리츠 원피스+재킷 세트", "msg": "NC 4위 / 본매장 재고 42EA"},
                {"rank": 5, "code": "GP3A0JKJ41", "name": "롤업 슬리브 트위드 재킷",        "msg": "NC 5위 / 본매장 재고 9EA"},
            ]
            for item in jj_focus_list:
                push_list.append({
                    "rank": item['rank'],
                    "style_code": item['code'],
                    "style_name": item['name'],
                    "sales_qty": 0, "stock_qty": 0,
                    "tag": "JJ 전략 상품",
                    "reason": f"<span style='color:#DC2626; font-weight:800;'>[{item['msg']}]</span>"
                })

        elif bp_brand_df is not None and not bp_brand_df.empty:
            bp_df = bp_brand_df.copy()
            for c in ['sales_qty', 'stock_qty']:
                if c in bp_df.columns: bp_df[c] = pd.to_numeric(bp_df[c], errors='coerce').fillna(0)
            # [v148.0] ComparisonEngine을 통한 정밀 차집합 분석 (강제 렌더링 포함)
            gap_codes = ComparisonEngine.get_gap_analysis(bp_brand_df, my_best_codes)
            for sc in gap_codes:
                my_item = b_df[b_df['style_code'] == sc]
                my_sales = my_item['sales_qty'].sum() if not my_item.empty else 0
                my_stock = my_item['stock_qty'].sum() if not my_item.empty else 0
                row = my_item.iloc[0] if not my_item.empty else bp_df[bp_df['style_code'] == sc].iloc[0]
                name = get_name(sc, row)
                push_list.append({
                    "style_code": sc,
                    "style_name": name,
                    "sales_qty": int(my_sales),
                    "stock_qty": int(my_stock),
                    "tag": "전사 인기 상품" if my_stock > 0 else "추가 확보 검토",
                    "reason": f"<b>전사 인기 상품이지만 현 지점 판매 순위권 밖 - 집중 노출 필요</b>"
                })
                if len(push_list) >= 10: break

        return {
            "ai_unified": secure_list,
            "push": push_list,
            "has_bp_data": True if (push_list or (bp_brand_df is not None and not bp_brand_df.empty)) else False
        }
