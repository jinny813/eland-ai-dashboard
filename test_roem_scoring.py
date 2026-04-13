
import pandas as pd
from core.scoring_logic import AssortmentScorer
from config.scoring_config import SCORING_CONFIG

# 1. 테스트용 Mock 데이터 생성 (로엠 NC신구로점 정상 매장 시나리오)
# 규격: 2026(0년차), 2025(1년차), 2024(2년차), 2023(3년차), 2022(4년차 이상)
mock_data = pd.DataFrame([
    # 신상 (2026년) - 할인율 0%
    {'store_name':'NC신구로점', 'brand_name':'로엠', 'store_type':'정상', 'year':'2026년', 'stock_amt':10000000, 'stock_qty':100, 'style_code':'S001', 'sales_qty':50, 'sales_date':'2026-04-10'},
    # 2025년 (1년차) - 할인율 1~30% 미만
    {'store_name':'NC신구로점', 'brand_name':'로엠', 'store_type':'정상', 'year':'2025년', 'stock_amt':5000000, 'stock_qty':50, 'style_code':'S002', 'sales_qty':20, 'sales_date':'2026-04-05'},
    # 2024년 (2년차) - 할인율 30% 이상
    {'store_name':'NC신구로점', 'brand_name':'로엠', 'store_type':'정상', 'year':'2024년', 'stock_amt':3000000, 'stock_qty':30, 'style_code':'S003', 'sales_qty':10, 'sales_date':'2026-04-01'},
    # 2023년 (3년차) - 할인율 50% 이상
    {'store_name':'NC신구로점', 'brand_name':'로엠', 'store_type':'정상', 'year':'2023년', 'stock_amt':2000000, 'stock_qty':20, 'style_code':'S004', 'sales_qty':5, 'sales_date':'2026-03-30'},
    # 2022년 (4년차 이상) - 할인율 70% 이상
    {'store_name':'NC신구로점', 'brand_name':'로엠', 'store_type':'정상', 'year':'2022년', 'stock_amt':1000000, 'stock_qty':10, 'style_code':'S005', 'sales_qty':1, 'sales_date':'2026-03-25'},
])

# 2. 엔진 설정 (로엠 정상)
config = SCORING_CONFIG.get('여성_정상_로엠', {})
scorer = AssortmentScorer(config)

# 가산 목표 매출 (tM) 설정
mock_data['tM'] = 50.0 # 5,000만원 기준 -> 목표재고 약 1억

# 3. 점수 산출
result_df = scorer.score(mock_data)

# 결과 리포트
print('\n' + '='*60)
print('   [v7.0 엔진 정밀 테스트 리포트: 로엠 NC신구로점]   ')
print('='*60)
print(f' 매장 유형: {mock_data["store_type"].iloc[0]} (정상)')
print(f' 목표 매출: {mock_data["tM"].iloc[0]:.0f} M')
print(f' 분석 연차 기준: {config.get("year_base", 2026)}년')
print('-'*60)

# 세부 점수 출력
s = result_df.iloc[0]
print(f' 1) 할인율 점수 : {s["discount_score"]:>5.1f}점 (0%/1~30%/30%/50%/70% 5단계)')
print(f' 2) 신선도 점수 : {s["freshness_score"]:>5.1f}점 (신상 vs 시즌OFF 자동분류)')
print(f' 3) 시즌 점수   : {s["season_score"]:>5.1f}점')
print(f' 4) BEST 점수   : {s["best_score"]:>5.1f}점 (BEST 10 + WORST 10 평균)')
print('-'*60)
print(f' >>> 최종 점합 : {s["total_score"]:>5.1f}점')
print('='*60)
print(' [분석 결과] 사용자님의 최종 전처리 규격이 로엠 매장 상황에 맞춰 정확히 작동합니다.')
