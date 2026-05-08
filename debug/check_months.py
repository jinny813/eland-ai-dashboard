import os, sys
sys.path.append(os.getcwd())
import pandas as pd
from database.gsheet_manager import GSheetManager

gsm = GSheetManager()
data = gsm.spreadsheet.worksheet("Records").get_all_records()
df = pd.DataFrame(data)

bucheon_brands = ["폴햄키즈", "뉴발란스키즈", "스파오키즈", "프로젝트키즈"]
for b in bucheon_brands:
    sub = df[(df['brand_name'].str.contains(b, na=False)) & (df['store_name'].str.contains('부천', na=False))]
    if not sub.empty:
        print(f"\nBrand: {b}")
        print(sub[['year', 'data_month', 'sales_qty', 'sales_amt']].to_string())
    else:
        print(f"\nBrand: {b} NOT FOUND in Bucheon")
