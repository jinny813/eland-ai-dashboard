import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def debug_sisley_prices():
    gsm = GSheetManager()
    print("Fetching records for Sisley price debugging...")
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    sisley_df = df[df['brand_name'] == "시슬리"].copy()
    if sisley_df.empty:
        print("No Sisley data found.")
        return
    
    # 2주내 BEST 품번들 (이전 스크립트 결과 참조)
    best_codes = ["SAWSF3631", "SAJKC4531", "SATS81531", "SAWS06511", "SACT35461", "SADPC3631", "SATSC4631", "SAKC35531", "SAKPA1611", "SADK31461"]
    
    debug_df = sisley_df[sisley_df['style_code'].isin(best_codes)].copy()
    
    print("\n[Sisley BEST Items Price Debug]")
    cols = ['style_code', 'sales_qty', 'sales_amt', 'normal_price', 'stock_qty', 'stock_amt']
    # 겹치는 컬럼만 출력
    print(debug_df[[c for c in cols if c in debug_df.columns]].head(20))

if __name__ == "__main__":
    debug_sisley_prices()
