import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ComparisonEngine:
    @staticmethod
    def get_gap_analysis(bp_df, my_best_codes):
        """
        [v148.0] 사용자 요청 정밀 비교 로직
        1. 데이터 표준화 (Normalization)
        2. 차집합 연산 수행 (A - B)
        3. 강제 렌더링 (Fallback)
        """
        if bp_df is None or bp_df.empty:
            return []

        # 1. 데이터 표준화: 품번 str 변환 및 strip
        bp_df = bp_df.copy()
        bp_df['style_code'] = bp_df['style_code'].astype(str).str.strip()
        my_best_codes = [str(c).strip() for c in my_best_codes]

        # 전사 BEST 10 추출
        bp_best = bp_df.groupby('style_code')['sales_qty'].sum().sort_values(ascending=False).head(10)
        bp_best_codes = bp_best.index.tolist()

        # 2. 비교 연산 수행: BP BEST에는 있지만 우리 지점 BEST 10에는 없는 품번
        target_list = [c for c in bp_best_codes if c not in my_best_codes]

        # [v148.0 추적 로그]
        trace_sc = 'GR3M0TC921'
        in_bp = trace_sc in bp_best_codes
        in_store = trace_sc in my_best_codes
        in_gap = trace_sc in target_list
        logger.info(f"--- [ComparisonEngine Trace] ---")
        logger.info(f"Target: {trace_sc} | BP Best: {in_bp} | Store Best: {in_store} | Final Gap: {in_gap}")

        # 3. 강제 렌더링: 결과가 비어있으면 BP 1~3위 강제 할당 (트렌치 코트 등)
        if not target_list:
            logger.warning("Gap List empty. Forcing BP Top 3 rendering (Strict Fallback).")
            target_list = bp_best_codes[:3]

        return target_list[:10]
