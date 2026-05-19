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

        return target_list[:10]
