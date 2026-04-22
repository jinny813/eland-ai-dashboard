import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def debug_sisley_columns():
    gsm = GSheetManager()
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed")
        return
        
    df = pd.DataFrame(results)
    sisley_df = df[df['brand_name'] == "시슬리"].copy()
    if sisley_df.empty:
        print("Empty Sisley")
        return
        
    print("\nColumns:", sisley_df.columns.tolist())
    print("\nSample row (Sisley):")
    print(sisley_df[['style_code', 'sales_qty', 'sales_amt', 'normal_price', 'stock_qty', 'stock_amt']].iloc[0].to_dict())

if __name__ == "__main__":
    debug_sisley_columns()
