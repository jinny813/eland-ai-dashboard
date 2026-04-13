"""
core/scoring_logic.py
=====================
[버전] v7.0 — 상설/정상 완전 분리 전처리

■ 매장 유형 분기:
  - 정상 (store_type == '정상') : year 기반 age 계산 → 기존 로직 유지
  - 상설 (store_type == '상설') : DB 컬럼 직접 사용
      · 할인율 → discount_rate (U열) 버킷 분류
      · 신선도 → freshness_type (T열) 값 직접 사용
      · 시즌   → season_code (C열) 한글값 ('봄','여름','가을','겨울')
      · BEST   → sales_qty (K열) 상위 10 style_code 재고액 집계

■ 핵심 산식 (공통):
  1. 목표 재고액 (Target) = 목표 매출(tM) * 2.0
  2. 지표 달성률 = min(실제재고액 / 목표재고액, 100%)
  3. 최종 총점 = 4개 지표별 달성률의 가중 평균
"""

import pandas as pd
from datetime import datetime, timedelta


def _is_outlet(store_type_val: str) -> bool:
    """상설 매장 여부 판단. DB 실제 값: '상설', 'outlet' 모두 처리"""
    v = str(store_type_val).strip().lower()
    return v in ("상설") or "outlet" in v


class AssortmentScorer:
    """상품구색 4개 지표 채점 엔진 — 매장유형별 분리 전처리 (v7)"""

    def __init__(self, config: dict):
        self.today = datetime.now().date()
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
        """'30%', '30', 0.3 등 다양한 할인율 표현 → 0~100 스케일 float 변환"""
        try:
            s = str(val).replace('%', '').strip()
            if not s or s in ('nan', 'None', ''):
                return 0.0
            f = float(s)
            # 0.0~1.0 범위면 소수 표현(0.3 = 30%)으로 간주
            if 0.0 < f <= 1.0:
                f = f * 100.0
            return f
        except (TypeError, ValueError):
            return 0.0

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        df = df.copy()

        # 목표 매출액(tM) 추출
        tM = float(df['tM'].iloc[0]) if ('tM' in df.columns and not pd.isna(df['tM'].iloc[0])) else 50_000_000.0
        if tM <= 0:
            tM = 1.0
        target_total = tM * 2.0  # 목표 재고액 (원 단위)

        # [v7.2] 매장 유형별 중복 제거 분기 (정상 매장 로직 복구)
        def _get_record_ref(mask):
            sub = df[mask]
            if sub.empty: return sub
            
            # [수정 3] 상설/정상 공통: inv_uid가 있으면 최우선으로 중복 제거 (데이터 뻥튀기 방지)
            if 'inv_uid' in sub.columns and sub['inv_uid'].notna().any():
                return sub.drop_duplicates('inv_uid')

            if is_outlet:
                # 상설: 인동팩토리 등은 모든 행 합산 (단, inv_uid 없을 경우 fallback)
                return sub
            else:
                # 정상: 로엠/미쏘 등은 기준 컬럼 조합으로 중복 제거
                d_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
                valid_cols = [c for c in d_cols if c in sub.columns]
                return sub.drop_duplicates(subset=valid_cols) if valid_cols else sub

        df['_amt'] = df['stock_amt'].apply(self._safe_float)

        # 매장 유형 판단
        store_type_val = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
        is_outlet = _is_outlet(store_type_val)

        # ──────────────────────────────────────────
        # 분기 A: 상설 매장 — DB 컬럼 직접 사용
        # ──────────────────────────────────────────
        if is_outlet:
            # [최신 표준 가중치] 할인율(45%), 신선도(15%), 시즌(15%), 베스트(25%)
            w_dis_g, w_fresh_g, w_sea_g, w_best_g = 0.45, 0.15, 0.15, 0.25

            # ── 1. 할인율 점수: 4단계 (70%+, 50%+, 30%+, 1%~30%) - 0% 정상가 선제외
            df['_dis_rate'] = df['discount_rate'].apply(self._parse_discount_rate) if 'discount_rate' in df.columns else 0.0

            dis_cfg = [
                {'mask': (df['_dis_rate'] >= 70),                                 'ratio': 0.10, 'label': '70%이상'},
                {'mask': (df['_dis_rate'] >= 50) & (df['_dis_rate'] < 70),        'ratio': 0.20, 'label': '50%이상'},
                {'mask': (df['_dis_rate'] >= 30) & (df['_dis_rate'] < 50),        'ratio': 0.30, 'label': '30%이상'},
                {'mask': (df['_dis_rate'] > 0)   & (df['_dis_rate'] < 30),        'ratio': 0.10, 'label': '1~30%미만'},
            ]
            dis_sum_att = 0.0
            for item in dis_cfg:
                act = _get_record_ref(item['mask'])['_amt'].sum()
                tgt = target_total * item['ratio']
                att = min(100.0, (act / tgt * 100)) if tgt > 0 else (100.0 if act <= 0 else 0.0)
                dis_sum_att += att
            discount_score = (dis_sum_att / len(dis_cfg)) if dis_cfg else 0.0

            # ── 2. 신선도 점수: 신상(10%), 기획(20%), 시즌OFF(70%) - 명시적 매핑
            ft = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series([''] * len(df))
            
            fresh_cfg = [
                {'m': (ft == '신상'),   'r': 0.10, 'label': '신상'},
                {'m': (ft == '시즌OFF'), 'r': 0.70, 'label': '시즌OFF'},
                {'m': (ft == '기획'),   'r': 0.20, 'label': '기획'},
            ]
            fresh_sum_att = 0.0
            for item in fresh_cfg:
                act = _get_record_ref(item['m'])['_amt'].sum()
                tgt = target_total * item['r']
                att = min(100.0, (act / tgt * 100)) if tgt > 0 else 100.0
                fresh_sum_att += att
            freshness_score = (fresh_sum_att / len(fresh_cfg))

            # ── 3. 시즌 점수: 목표 비중 70%
            ss_months = [2, 3, 4, 5, 6, 7]
            is_ss_now = datetime.now().month in ss_months
            sc = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series([''] * len(df))
            if is_ss_now:
                curr_season_mask = sc.isin(['봄', '여름', '2', '1', '9'])
            else:
                curr_season_mask = sc.isin(['가을', '겨울', '3', '4', '9'])

            act_sea = _get_record_ref(curr_season_mask)['_amt'].sum()
            tgt_sea = target_total * 0.70
            season_score = min(100.0, (act_sea / tgt_sea * 100)) if tgt_sea > 0 else 0.0

            # ── 4. BEST 점수: 베스트 10 목표 비중 25% (날짜 필터 없이 전체 sales_qty 기준)
            best_score = 0.0
            if 'sales_qty' in df.columns:
                sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
                # [수정] DB에 있는 전체 판매량을 합산하여 상위 10개 품번 추출
                sales_sum = df.assign(_sq=sq).groupby('style_code')['_sq'].sum().sort_values(ascending=False)

                if not sales_sum.empty:
                    cutoff_rank = min(len(sales_sum), 10)
                    min_val = sales_sum.iloc[cutoff_rank - 1]
                    best_styles = sales_sum[sales_sum >= min_val][sales_sum > 0].index
                    act_best = _get_record_ref(df['style_code'].isin(best_styles))['_amt'].sum()
                    tgt_best = target_total * 0.25
                    best_score = min(100.0, (act_best / tgt_best * 100)) if tgt_best > 0 else 0.0

        # ──────────────────────────────────────────
        # 분기 B: 정상 매장 — 기존 year/age 기반 로직 (로엠 등, 변경 금지)
        # ──────────────────────────────────────────
        else:
            # [최신 표준 가중치] 할인율(30%), 신선도(20%), 시즌(20%), 베스트(30%)
            w_dis_g, w_fresh_g, w_sea_g, w_best_g = 0.30, 0.20, 0.20, 0.30

            # 연차(Age) 계산
            def _get_year_base():
                try:
                    if 'year' in df.columns:
                        years = pd.to_numeric(df['year'].astype(str).str.replace('년', '').strip(), errors='coerce')
                        return int(years.max())
                    return 2026
                except:
                    return 2026

            year_base = _get_year_base()

            def _get_age_logic(y):
                try:
                    val = str(y).replace('년', '').strip()
                    y_num = int(val)
                    if y_num < 100:
                        y_num += 2000
                    return max(0, year_base - y_num)
                except:
                    return 0

            df['_age'] = df['year'].apply(_get_age_logic) if 'year' in df.columns else 0

            # 1. 할인율 지표 (정상: age 기반 매핑 — 70%+(0), 50%+(5), 30%+(10), 1-30%(15))
            dis_cfg = [
                {'mask': (df['_age'] >= 4), 'ratio': 0.00},
                {'mask': (df['_age'] == 3), 'ratio': 0.05},
                {'mask': (df['_age'] == 2), 'ratio': 0.10},
                {'mask': (df['_age'] == 1), 'ratio': 0.15},
            ]
            dis_sum_att = 0.0
            for item in dis_cfg:
                act = _get_record_ref(item['mask'])['_amt'].sum()
                tgt = target_total * item['ratio']
                att = min(100.0, (act / tgt * 100)) if tgt > 0 else (100.0 if act <= 0 else 0.0)
                dis_sum_att += att
            discount_score = (dis_sum_att / len(dis_cfg)) if dis_cfg else 0.0

            # 2. 신선도 지표 (정상: 신상(70%), 시즌오프(30%))
            is_plan = df['price_type'].astype(str).str.contains('균일|기획', na=False)
            is_new  = (df['_age'] == 0) & (~is_plan)
            is_off  = (df['_age'] >= 1) & (~is_plan)

            fresh_cfg = [{'m': is_new, 'r': 0.70}, {'m': is_off, 'r': 0.30}]
            fresh_sum_att = 0.0
            for item in fresh_cfg:
                act = _get_record_ref(item['m'])['_amt'].sum()
                tgt = target_total * item['r']
                att = min(100.0, (act / tgt * 100)) if tgt > 0 else 100.0
                fresh_sum_att += att
            freshness_score = (fresh_sum_att / len(fresh_cfg))

            # 3. 시즌 지표 (정상: 시즌 상품 목표 비중 70%)
            ss_months = [2, 3, 4, 5, 6, 7]
            is_ss_now = datetime.now().month in ss_months
            curr_season_mask = df['season_code'].astype(str).str.contains(
                '1|2|9' if is_ss_now else '3|4|9', na=False
            )
            act_sea = _get_record_ref(curr_season_mask)['_amt'].sum()
            tgt_sea = target_total * 0.70
            season_score = min(100.0, (act_sea / tgt_sea * 100)) if tgt_sea > 0 else 0.0

            # 4. BEST 지표 (정상: 베스트 10 목표 비중 25%)
            best_score = 0.0
            if 'sales_qty' in df.columns and 'sales_date' in df.columns:
                df['_sale_dt'] = pd.to_datetime(df['sales_date'], errors='coerce')
                max_dt = df['_sale_dt'].max()
                if pd.notna(max_dt):
                    cutoff = max_dt - timedelta(days=14)
                    recent_df = df[df['_sale_dt'] >= cutoff].copy()
                else:
                    recent_df = df.copy()

                recent_df['sales_qty'] = pd.to_numeric(recent_df['sales_qty'], errors='coerce').fillna(0)
                sales_sum = recent_df.groupby('style_code')['sales_qty'].sum().sort_values(ascending=False)

                if not sales_sum.empty:
                    cutoff_rank = min(len(sales_sum), 10)
                    min_val = sales_sum.iloc[cutoff_rank - 1]
                    best_styles = sales_sum[sales_sum >= min_val].index
                    act_best = _get_record_ref(df['style_code'].isin(best_styles))['_amt'].sum()
                    tgt_best = target_total * 0.25
                    best_score = min(100.0, (act_best / tgt_best * 100)) if tgt_best > 0 else 0.0

        # ──────────────────────────────────────────
        # 공통: 점수 컬럼 부여 및 총점 산출
        # ──────────────────────────────────────────
        df['discount_score']  = round(discount_score,  1)
        df['freshness_score'] = round(freshness_score, 1)
        df['season_score']    = round(season_score,    1)
        df['best_score']      = round(best_score,      1)

        total_score = (
            discount_score  * w_dis_g  +
            freshness_score * w_fresh_g +
            season_score    * w_sea_g  +
            best_score      * w_best_g
        ) if not df.empty else 0.0

        df['total_score'] = round(total_score, 1)

        # 임시 컬럼 정리
        drop_cols = ['_amt', '_age', '_sale_dt', '_dis_rate']
        return df.drop(drop_cols, axis=1, errors='ignore')
