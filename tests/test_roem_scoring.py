
import pandas as pd
from core.scoring_logic import AssortmentScorer
from config.scoring_config import SCORING_CONFIG

def run_test(store_type='정상', target_sales=50000000):
    # 1. 테스트용 Mock 데이터 생성
    mock_data = pd.DataFrame([
        # Outer
        {'store_name':'테스트신구로점', 'brand_name':'로엠', 'store_type':store_type, 'year':'2026', 'stock_amt':10000000, 'stock_qty':100, 'style_code':'JK01', 'item_code':'JK', 'discount_rate':'0%', 'freshness_type':'신상', 'season_code':'봄', 'sales_qty':50, 'sales_date':'2026-04-10'},
        # Top
        {'store_name':'테스트신구로점', 'brand_name':'로엠', 'store_type':store_type, 'year':'2025', 'stock_amt':5000000, 'stock_qty':50, 'style_code':'BL01', 'item_code':'BL', 'discount_rate':'20%', 'freshness_type':'기획', 'season_code':'여름', 'sales_qty':20, 'sales_date':'2026-04-05'},
        # Bottom
        {'store_name':'테스트신구로점', 'brand_name':'로엠', 'store_type':store_type, 'year':'2024', 'stock_amt':3000000, 'stock_qty':30, 'style_code':'PT01', 'item_code':'PT', 'discount_rate':'40%', 'freshness_type':'신상', 'season_code':'가을', 'sales_qty':10, 'sales_date':'2026-04-01'},
        # Skirt
        {'store_name':'테스트신구로점', 'brand_name':'로엠', 'store_type':store_type, 'year':'2023', 'stock_amt':2000000, 'stock_qty':20, 'style_code':'SK01', 'item_code':'SK', 'discount_rate':'60%', 'freshness_type':'기획', 'season_code':'겨울', 'sales_qty':5, 'sales_date':'2026-03-30'},
        # Dress
        {'store_name':'테스트신구로점', 'brand_name':'로엠', 'store_type':store_type, 'year':'2022', 'stock_amt':1000000, 'stock_qty':10, 'style_code':'OP01', 'item_code':'OP', 'discount_rate':'80%', 'freshness_type':'신상', 'season_code':'봄', 'sales_qty':1, 'sales_date':'2026-03-25'},
    ])

    mock_data['tM'] = target_sales # 원(Won) 단위 유지

    # 2. 엔진 설정
    config_key = f'여성_{store_type}_로엠'
    config = SCORING_CONFIG.get(config_key, SCORING_CONFIG.get('기본_설정'))
    scorer = AssortmentScorer(config)

    # 3. 점수 산출
    result_df = scorer.score(mock_data)

    # 결과 리포트
    print('\n' + '='*60)
    print(f'   [v8.0 엔진 테스트 리포트: {store_type} 매장]   ')
    print('='*60)
    s = result_df.iloc[0]
    print(f' 1) 할인율 점수 : {s["discount_score"]:>5.1f}점')
    print(f' 2) 신선도 점수 : {s["freshness_score"]:>5.1f}점')
    print(f' 3) 시즌 점수   : {s["season_score"]:>5.1f}점')
    print(f' 4) BEST 점수   : {s["best_score"]:>5.1f}점')
    print(f' 5) 아이템 점수 : {s["item_score"]:>5.1f}점')
    print('-'*60)
    print(f' >>> 최종 총점 : {s["total_score"]:>5.1f}점')
    print('='*60)

if __name__ == "__main__":
    run_test('정상')
    run_test('상설')
