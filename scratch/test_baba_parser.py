import pandas as pd
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

from parsers.babagroup_parser import BabaGroupParser

def test_baba_parser():
    parser = BabaGroupParser()
    
    # 1. 재고 데이터 (헤더 명칭 변형 + 순서 뒤섞임)
    # 표준: NO, 년도, 시즌, 상품코드, 아이템명, ...
    # 변형: 모델명(style_code), 제조년(year), 계절(season_code), 재고(stock_qty), 금액(stock_amt)
    inv_data = pd.DataFrame([
        {'모델명': 'JJW1A123', '제조년': '2024', '계절': '봄', '부서': '여성', '재고': '10', '금액': '1,200,000', 'TAG금액': '150,000', '매가': '120,000'},
        {'모델명': 'JJW1A456', '제조년': '24', '계절': '여름', '부서': '여성', '재고': '5', '금액': '600,000', 'TAG금액': '200,000', '매가': '100,000'},
    ])
    
    print("--- 재고 데이터 파싱 테스트 ---")
    df_inv_parsed = parser.parse_inventory(inv_data)
    print(df_inv_parsed[['style_code', 'year', 'stock_qty', 'stock_amt', 'discount_rate']])
    
    # 2. 판매 데이터 (전혀 다른 헤더 + 컬럼 부족)
    # 변형: 상품코드(style_code), 판매수(sales_qty), 매출액(sales_amt), 매출일자(sales_date)
    sales_data = pd.DataFrame([
        {'상품코드': 'JJW1A123', '판매수': '2', '매출액': '240,000', '매출일자': '2024-04-01'},
        {'상품코드': 'JJW1A456', '판매수': '1', '매출액': '100,000', '매출일자': '2024-04-02'},
    ])
    
    print("\n--- 판매 데이터 파싱 테스트 ---")
    df_sales_parsed = parser.parse_sales(sales_data)
    print(df_sales_parsed)

if __name__ == "__main__":
    test_baba_parser()
