import pandas as pd
from datetime import datetime, timedelta


def _is_outlet(store_type_val: str) -> bool:
    """상설 매장 여부 판단. DB 실제 값: '상설', 'outlet' 모두 처리"""
    v = str(store_type_val).strip().lower()
    return v in ("상설") or "outlet" in v


class AssortmentScorer:
    """상품구색 5개 지표 채점 엔진 — v8.0 아이템 점수 추가 및 로직 전면 개편"""

    ITEM_GROUPS = {
        'Outer': ['JK', 'JA', 'JD', 'JE', 'JH', 'JJ', 'JL', 'JP', 'JT', 'JV', 'JW', 'SJ', 'VK', 'VW', 'CK', 'CM', 'VT', 'CT', 'CD', 'BY', 'KC', 'PD', 'FU', 'U', 'E', 'J', 'C', 'D', 'Y', 'L'],
        'Top': ['BL', 'BA', 'BB', 'BN', 'BW', 'DR', 'GM', 'HA', 'HS', 'HW', 'KA', 'KN', 'KR', 'KV', 'KW', 'LA', 'LS', 'LW', 'MA', 'MB', 'MH', 'MW', 'MZ', 'RA', 'RB', 'RN', 'RP', 'RS', 'RW', 'SM', 'YA', 'YC', 'YH', 'YS', 'YW', 'XH', 'MN', 'MR', 'PP', 'GN', 'BR', 'FZ', 'FW', 'TS', 'ST', 'PO', 'SH', 'WS', 'KO', 'KP', 'B', 'K', 'T'],
        'Bottom': ['SL', 'PT', 'TA', 'TC', 'TH', 'TJ', 'TM', 'TN', 'TR', 'ST', 'IL', 'YI', 'YF', 'XF', 'XD', 'WP', 'WQ', 'XV', 'YV', 'SP', 'LE', 'DK', 'N', 'P'],
        'Skirt': ['SK', 'TS', 'WH', 'WJ', 'WK', 'WM', 'KS', 'S'],
        'Dress': ['OP', 'OJ', 'OK', 'OM', 'ON', 'OW', 'YO', 'LO', 'SP', 'YJ', 'DP', 'O']
    }

    def __init__(self, config: dict = None):
        self.today = datetime.now()
        self.current_month = self.today.month
        self.config = config if config else {}
        self.best_cutoff = self.today - timedelta(days=14)

    @staticmethod
    def _safe_float(val) -> float:
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', '').strip())
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_discount_rate(val) -> float:
        try:
            s = str(val).replace('%', '').strip()
            if not s or s in ('nan', 'None', ''):
                return 0.0
            f = float(s)
            if 0.0 < f <= 1.0:
                f = f * 100.0
            return f
        except (TypeError, ValueError):
            return 0.0

    def _get_item_group(self, item_code: str) -> str:
        """item_code(주로 앞 2자리) 기반 아이템 그룹 매핑"""
        if not item_code or pd.isna(item_code):
            return 'Others'
        code = str(item_code).strip().upper()[:2]
        for group, codes in self.ITEM_GROUPS.items():
            if code in codes or str(item_code).strip().upper() in codes:
                return group
        return 'Others'

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        df = df.copy()
        
        # [v8.0] 기본 수치 변환
        df['_amt'] = df['stock_amt'].apply(self._safe_float)
        if 'item_code' in df.columns:
            df['item_group'] = df['item_code'].apply(self._get_item_group)
        else:
            df['item_group'] = 'Others'

        # 목표 매출액(tM) 추출 및 목표 총액 설정
        tM = float(df['tM'].iloc[0]) if ('tM' in df.columns and not pd.isna(df['tM'].iloc[0])) else 50_000_000.0
        if tM <= 0: tM = 1.0
        target_total = tM * 2.0  # 목표 재고액 (200%)

        # 매장 유형 판단
        store_type_val = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
        is_outlet = _is_outlet(store_type_val)

        # 중복 제거 참조용 함수 (v7 기준 유지)
        def _get_record_ref(mask):
            sub = df[mask]
            if sub.empty: return sub
            if 'inv_uid' in sub.columns and sub['inv_uid'].notna().any():
                return sub.drop_duplicates('inv_uid')
            if is_outlet:
                return sub
            else:
                d_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
                valid_cols = [c for c in d_cols if c in sub.columns]
                return sub.drop_duplicates(subset=valid_cols) if valid_cols else sub

        # 1. 지표별 대분류 가중치 설정
        if is_outlet:
            # 상설: 할인율(40%), 신선도(15%), 시즌(15%), 베스트10(20%), 아이템(10%)
            weights = {'dis': 0.40, 'fresh': 0.15, 'sea': 0.15, 'best': 0.20, 'item': 0.10}
        else:
            # 정상: 할인율(30%), 신선도(20%), 시즌(15%), 베스트10(25%), 아이템(10%)
            weights = {'dis': 0.30, 'fresh': 0.20, 'sea': 0.15, 'best': 0.25, 'item': 0.10}

        # [v8.7] 연차(Age) 계산: 설정된 year_base 또는 시스템 연도 기준
        year_base = self.config.get('year_base', 2026)
        if year_base < 100: year_base += 2000
        ref_y = year_base

        def _get_age_sync(y):
            try:
                if not y or pd.isna(y): return 0
                val = str(y).replace('년','').strip()
                y_num = int(val)
                if y_num < 100: y_num += 2000
                return max(0, ref_y - y_num)
            except: return 0

        df['_age'] = df['year'].apply(_get_age_sync) if 'year' in df.columns else 0

        # ────────── A. 할인율 지표 ──────────
        df['_dis_rate'] = df['discount_rate'].apply(self._parse_discount_rate) if 'discount_rate' in df.columns else 0.0
        if is_outlet:
            # 상설: 실시간 할인율(U열) 기준
            dis_cfg = [
                {'m': (df['_dis_rate'] >= 70), 'r': 0.10},
                {'m': (df['_dis_rate'] >= 50) & (df['_dis_rate'] < 70), 'r': 0.20},
                {'m': (df['_dis_rate'] >= 30) & (df['_dis_rate'] < 50), 'r': 0.30},
                {'m': (df['_dis_rate'] > 0)   & (df['_dis_rate'] < 30), 'r': 0.10},
            ]
        else:
            # 정상: 연차(year) 기준 매핑 — 70%+(4년+), 50%+(3년), 30%+(2년), 1-30%(1년)
            dis_cfg = [
                {'m': (df['_age'] >= 4), 'r': 0.00},
                {'m': (df['_age'] == 3), 'r': 0.05},
                {'m': (df['_age'] == 2), 'r': 0.10},
                {'m': (df['_age'] == 1), 'r': 0.15},
            ]
        dis_atts = []
        for item in dis_cfg:
            act = _get_record_ref(item['m'])['_amt'].sum()
            tgt = target_total * item['r']
            dis_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else (100.0 if act <= 0 else 0.0))
        discount_score = (sum(dis_atts) / len(dis_atts)) if dis_atts else 0.0

        # ────────── B. 신선도 지표 ──────────
        ft = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series([''] * len(df))
        if is_outlet:
            # 상설: freshness_type 명시적 필드 사용
            fresh_cfg = [{'m': (ft == '신상'), 'r': 0.10}, {'m': (ft == '기획'), 'r': 0.20}]
        else:
            # 정상: 연차 0년차를 신상으로 간주
            fresh_cfg = [{'m': (df['_age'] == 0), 'r': 0.70}]
        
        fresh_atts = []
        for item in fresh_cfg:
            act = _get_record_ref(item['m'])['_amt'].sum()
            tgt = target_total * item['r']
            fresh_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else 0.0)
        freshness_score = (sum(fresh_atts) / len(fresh_atts)) if fresh_atts else 0.0

        # ────────── C. 시즌 지표 ──────────
        month = self.current_month
        sc = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series([''] * len(df))
        
        # [v8.8] 새로운 계절 구분: 봄(1,2,3), 여름(4,5,6), 가을(7,8,9), 겨울(10,11,12)
        # 사용자 요청: 4월은 '봄(50%)' / '여름(30%)'으로 계산 (전환기 예외 적용)
        
        # 시즌 코드 그룹 정의
        CO_SPRING = ['봄', '1', '9']
        CO_SUMMER = ['여름', '2', '9']
        CO_AUTUMN = ['가을', '3', '8', '9']
        CO_WINTER = ['겨울', '4', '9']

        if month in [1, 2, 3]: # 봄 시즌 중
            curr_codes, other_codes = CO_SPRING, CO_SUMMER
        elif month == 4: # [사용자 예외] 4월은 봄(50%)/여름(30%)
            curr_codes, other_codes = CO_SPRING, CO_SUMMER
        elif month in [5, 6]: # 여름 시즌
            curr_codes, other_codes = CO_SUMMER, CO_SPRING
        elif month in [7, 8, 9]: # 가을 시즌
            curr_codes, other_codes = CO_AUTUMN, CO_WINTER
        else: # 겨울 시즌 (10, 11, 12)
            curr_codes, other_codes = CO_WINTER, CO_AUTUMN

        season_cfg = [
            {'m': sc.isin(curr_codes),  'r': 0.50}, 
            {'m': sc.isin(other_codes), 'r': 0.30}, 
        ]
        
        season_atts = []
        for item in season_cfg:
            act = _get_record_ref(item['m'])['_amt'].sum()
            tgt = target_total * item['r']
            season_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else 0.0)
        
        season_score = (sum(season_atts) / len(season_atts)) if season_atts else 0.0

        # ────────── D. 베스트10 스타일 ──────────
        best_styles = []
        # [v116.0] 판매 데이터 기반 베스트 스타일 선정 (Fallback: 재고액 기반)
        if 'sales_qty' in df.columns:
            if 'sales_date' in df.columns and df['sales_date'].notna().any():
                df['_sale_dt'] = pd.to_datetime(df['sales_date'], errors='coerce')
                max_dt = df['_sale_dt'].max()
                cutoff = (max_dt - timedelta(days=14)) if pd.notna(max_dt) else (self.today - timedelta(days=14))
                recent_df = df[df['_sale_dt'] >= cutoff].copy()
                
                # 최근 데이터가 너무 적으면 전체 데이터 사용
                if len(recent_df) < 5: recent_df = df.copy()
            else:
                recent_df = df.copy()
            
            sq = pd.to_numeric(recent_df['sales_qty'], errors='coerce').fillna(0)
            sales_sum = recent_df.assign(_sq=sq).groupby('style_code')['_sq'].sum().sort_values(ascending=False)
            best_styles = sales_sum.head(10)[sales_sum > 0].index.tolist()
        
        # [v116.1] 판매 데이터가 부족한 경우(신규 브랜드 등) 재고액 상위 상품으로 보충
        if len(best_styles) < 10:
            remaining_count = 10 - len(best_styles)
            stk_sum = df.groupby('style_code')['stock_amt'].sum().sort_values(ascending=False)
            # 이미 선정된 스타일 제외
            stk_candidates = stk_sum[~stk_sum.index.isin(best_styles)]
            extra_styles = stk_candidates.head(remaining_count).index.tolist()
            best_styles.extend(extra_styles)
        
        # [v105.7] BEST 10 styles: Adjust target inventory weight to 20%
        act_best = _get_record_ref(df['style_code'].isin(best_styles))['_amt'].sum()
        tgt_best = target_total * 0.20
        best_score = min(100.0, (act_best / tgt_best * 100)) if tgt_best > 0 else 0.0

        # ────────── E. 아이템 지표 ──────────
        item_cfg = [
            {'g': 'Outer',  'r': 0.30},
            {'g': 'Top',    'r': 0.30},
            {'g': 'Bottom', 'r': 0.20},
            {'g': 'Skirt',  'r': 0.10},
            {'g': 'Dress',  'r': 0.10},
        ]
        item_atts = []
        for item in item_cfg:
            act = _get_record_ref(df['item_group'] == item['g'])['_amt'].sum()
            tgt = target_total * item['r']
            item_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else 0.0)
        item_score = (sum(item_atts) / len(item_atts)) if item_atts else 0.0

        # ──────────────────────────────────────────
        # 최종 총점 산출
        # ──────────────────────────────────────────
        df['discount_score']  = round(discount_score, 1)
        df['freshness_score'] = round(freshness_score, 1)
        df['season_score']    = round(season_score, 1)
        df['best_score']      = round(best_score, 1)
        df['item_score']      = round(item_score, 1)

        total_score = (
            discount_score  * weights['dis']   +
            freshness_score * weights['fresh'] +
            season_score    * weights['sea']   +
            best_score      * weights['best']  +
            item_score      * weights['item']
        )
        df['total_score'] = round(total_score, 1)

        # 임시 컬럼 정리
        drop_cols = ['_amt', '_dis_rate', '_sale_dt', 'item_group']
        return df.drop(drop_cols, axis=1, errors='ignore')
