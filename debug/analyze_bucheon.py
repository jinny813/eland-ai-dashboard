import pandas as pd
import sys
import os

# 프로젝트 경로 추가
sys.path.append('d:/AI Assortment Agent')

from database.gsheet_manager import GSheetManager

def analyze_bucheon_zeros():
    mgr = GSheetManager()
    df = pd.DataFrame(mgr.spreadsheet.worksheet('Records').get_all_records())
    
    # NC부천점 데이터 필터링
    bucheon_df = df[df['store_name'] == 'NC부천점']
    
    brands = ['폴햄키즈', '뉴발란스키즈', '스파오키즈', '프로젝트키즈']
    
    for brand in brands:
        print(f"\n[{brand}]")
        b_df = bucheon_df[bucheon_df['brand_name'] == brand]
        if b_df.empty:
            print("  No data found.")
            continue
            
        print(f"  총 레코드 수: {len(b_df)}")
        
        # 할인율 데이터
        dis_unique = b_df['discount_rate'].unique()
        print(f"  할인율 종류: {dis_unique}")
        
        # 연차 데이터
        year_unique = b_df['year'].unique()
        print(f"  연차(year) 종류: {year_unique}")
        
        # 신선도 데이터
        fresh_unique = b_df['freshness_type'].unique()
        print(f"  신선도 종류: {fresh_unique}")
        
        # BEST 데이터 (판매량, 재고량)
        sales_sum = b_df['sales_qty'].sum()
        stock_sum = b_df['stock_qty'].sum()
        print(f"  총 판매량: {sales_sum}, 총 재고량: {stock_sum}")

if __name__ == '__main__':
    analyze_bucheon_zeros()
