import pandas as pd
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

from core.data_manager import DataManager
from parsers.babagroup_parser import BabaGroupParser

def test_timeseries_merge():
    dm = DataManager()
    parser = BabaGroupParser()
    
    # 1. 가상의 재고 데이터 (1개 품번)
    # 실제 바바그룹 형식과 유사하게 구성
    inv_data = pd.DataFrame([
        {'매장명': 'NC신구로', '품번': 'BABA-001', '판매구분': '정상', '총재고_수량': '100', '총재고_매가': '1,000,000'},
    ])
    
    # 2. 가상의 판매 데이터 (동일 품번, 3개 날짜)
    sales_data = pd.DataFrame([
        {'품번': 'BABA-001', '판매수량': '5', '판매액': '50,000', '판매일자': '2026-03-01'},
        {'품번': 'BABA-001', '판매수량': '10', '판매액': '100,000', '판매일자': '2026-03-15'},
        {'품번': 'BABA-001', '판매수량': '2', '판매액': '20,000', '판매일자': '2026-03-30'},
    ])
    
    print("--- 시계열 병합 및 재고 마스킹 테스트 ---")
    # DataManager의 process_and_merge 직접 호출 (바바그룹 파서 사용)
    final_df = dm.process_and_merge(
        brand_name="JJ지고트", # BabaGroupParser 트리거
        store_name="NC신구로",
        category_group="여성",
        store_type="상설",
        data_month="3월",
        inv_data=inv_data,
        sales_data=sales_data
    )
    
    # 결과 출력
    cols_to_show = ['style_code', 'sales_date', 'sales_qty', 'stock_qty', 'stock_amt']
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(final_df[cols_to_show])
    
    # 검증 포인트
    # 1. 총 행수가 3개여야 함
    # 2. 2026-03-30 행에는 stock_qty=100이 있어야 함
    # 3. 2026-03-15, 2026-03-01 행에는 stock_qty=0이어야 함
    # 4. SUM(sales_qty) == 17이어야 함
    # 5. SUM(stock_qty) == 100이어야 함
    
    row_latest = final_df[final_df['sales_date'] == '2026-03-30'].iloc[0]
    row_old = final_df[final_df['sales_date'] == '2026-03-15'].iloc[0]
    
    print("\n--- 검증 결과 ---")
    print(f"총 행수: {len(final_df)} (기대값: 3)")
    print(f"최신일(03-30) 재고량: {row_latest['stock_qty']} (기대값: 100)")
    print(f"과거일(03-15) 재고량: {row_old['stock_qty']} (기대값: 0)")
    print(f"전체 판매량 합계: {final_df['sales_qty'].sum()} (기대값: 17)")
    print(f"전체 재고량 합계: {final_df['stock_qty'].sum()} (기대값: 100)")
    
    if len(final_df) == 3 and row_latest['stock_qty'] == 100 and row_old['stock_qty'] == 0 and final_df['sales_qty'].sum() == 17 and final_df['stock_qty'].sum() == 100:
        print("\n✅ 모든 검증 성공!")
    else:
        print("\n❌ 검증 실패!")

if __name__ == "__main__":
    test_timeseries_merge()
