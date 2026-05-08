import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scoring_logic import AssortmentScorer
from config.scoring_config import get_weights_by_category

def run_test():
    # 스포츠 / 상설 테스트 데이터
    config = get_weights_by_category("스포츠", "상설")
    scorer = AssortmentScorer(config)

    data = {
        'style_code': ['SN123', 'CS123', 'RN456', 'TS123', 'PT123'],
        'item_code': ['SNAA', 'CSAA', 'RNBB', 'TSCC', 'PTDD'],
        'stock_amt': [1000000, 500000, 2000000, 3000000, 1000000],
        'discount_rate': ['70%', '50%', '30%', '10%', '0%'],
        'freshness_type': ['신상', '기획', '이월', '신상', '이월'],
        'season_code': ['봄', '여름', '가을', '겨울', '봄'],
        'sales_qty': [10, 5, 20, 30, 2],
        'tM': [10000000] * 5,
        'store_type': ['상설'] * 5,
        'area': [30.0] * 5,
        'data_month': ['4월'] * 5
    }
    df = pd.DataFrame(data)

    scored_df = scorer.score(df)
    print("\n[Score Results]")
    print(scored_df[['product_score', 'eff_score', 'total_score']].iloc[0])

    print("\n[Detail Scores]")
    print(scored_df[['discount_score', 'freshness_score', 'season_score', 'best_score', 'item_score']].iloc[0])

    print("\n[Shortage Segments]")
    shortage = scorer.get_shortage_segments(df)
    print(shortage)

if __name__ == "__main__":
    run_test()
