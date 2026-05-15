import os, sys
sys.path.append(os.getcwd())
import pandas as pd
from database.gsheet_manager import GSheetManager

gsm = GSheetManager()
data = gsm.spreadsheet.worksheet("Records").get_all_records()
df = pd.DataFrame(data)

print("Unique Store Names in Records:")
print(df['store_name'].unique())

print("\nBrands at 뉴코아부천점 (or similar):")
possible_stores = [s for s in df['store_name'].unique() if '부천' in str(s) or 'NC' in str(p) or ps in str(s)] # Fixed ps usage
for ps in df['store_name'].unique():
    if '부천' in str(ps):
        print(f"\n--- Store: {ps} ---")
        brands = df[df['store_name'] == ps]['brand_name'].unique()
        print(brands)
