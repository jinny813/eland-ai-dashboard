
import pandas as pd
from database.gsheet_manager import GSheetManager

mgr = GSheetManager()
if not mgr.is_connected:
    print("Not connected")
    exit()

sheet = mgr.spreadsheet.worksheet("Records")
all_recs = sheet.get_all_records()
df = pd.DataFrame(all_recs)

target = df[(df['brand_name'] == '로엠') & (df['store_name'] == '동아쇼핑점')]
print(f"Total rows for Roem @ Dong-A: {len(target)}")

# 수치 변환
target['sales_qty'] = pd.to_numeric(target['sales_qty'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

print("\n--- TOP 5 Styles by Sales Qty (Sum) ---")
best = target.groupby('style_code')['sales_qty'].sum().sort_values(ascending=False).head(5)
print(best)

print("\n--- Raw Data for Top Style ---")
top_style = best.index[0]
top_rows = target[target['style_code'] == top_style]
print(f"Rows for {top_style}: {len(top_rows)}")
print(top_rows[['style_code', 'inv_uid', 'sales_qty', 'stock_qty']].head(10))

# Check for duplicates by inv_uid
if 'inv_uid' in target.columns:
    dupes = target[target.duplicated(subset=['inv_uid'], keep=False)]
    if not dupes.empty:
        print(f"\nFound {len(dupes)} rows with duplicate inv_uid")
        print(dupes[['inv_uid', 'style_code', 'sales_qty']].head(10))
