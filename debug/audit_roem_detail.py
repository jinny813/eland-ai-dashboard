
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
target['sales_qty'] = pd.to_numeric(target['sales_qty'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

top_style = 'RMCKF23R98'
top_rows = target[target['style_code'] == top_style]
print(f"\n--- Raw Data for {top_style} (10 rows) ---")
print(top_rows[['style_code', 'sales_qty', 'stock_qty', 'data_month', 'store_type']])

# Check if there are other brands mixed in? No, we filtered.
# Check if there are multiple dates/months?
print("\n--- Value Counts for data_month ---")
print(top_rows['data_month'].value_counts())
