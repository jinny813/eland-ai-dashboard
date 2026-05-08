import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.data_loader import _try_float, _is_outlet_type
from database.gsheet_manager import GSheetManager

mgr = GSheetManager()
records = mgr.spreadsheet.worksheet("Records").get_all_records()
df = pd.DataFrame(records)

b_df = df[(df['brand_name'] == '뉴발란스') & (df['store_name'] == 'NC신구로점')].copy()
num_cols = ['stock_amt', 'stock_qty', 'sales_qty', 'sales_amt', 'normal_price']
for c in num_cols:
    if c in b_df.columns:
        b_df[c] = pd.to_numeric(b_df[c].astype(str).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)

b_name = '뉴발란스'
normals = ["로엠", "미쏘", "더아이잗", "에잇컨셉"]
outlets = ["지오지아", "지오지아팩토리", "인동팩토리(리스트,쉬즈미스)"]

if b_name in normals:
    b_type = "정상"
elif b_name in outlets:
    b_type = "상설"
else:
    b_type = str(b_df.iloc[0].get('store_type', '상설')).strip() or '상설'

is_outlet_b = _is_outlet_type(b_type)

if 'inv_uid' in b_df.columns and b_df['inv_uid'].notna().any() and not (b_df['inv_uid'] == '').all():
    b_df = b_df.drop_duplicates(subset=['inv_uid'])
elif not is_outlet_b:
    b_df = b_df.drop_duplicates()
    sales_mask = b_df['sales_qty'] > 0
    sales_df = b_df[sales_mask].copy()
    zero_df = b_df[~sales_mask].copy()
    
    if not sales_df.empty:
        subset_cols = ['style_code', 'sales_qty', 'sales_amt']
        for c in ['color', 'size']:
            if c in b_df.columns: subset_cols.append(c)
        sales_df = sales_df.drop_duplicates(subset=subset_cols, keep='first')
    
    b_df = pd.concat([sales_df, zero_df], ignore_index=True)

if 'inv_uid' in b_df.columns and b_df['inv_uid'].notna().any() and not (b_df['inv_uid'] == '').all():
    stock_ref = b_df.drop_duplicates('inv_uid')
elif is_outlet_b:
    stock_ref = b_df
else:
    dedup_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
    stock_ref = b_df.drop_duplicates(subset=[c for c in dedup_cols if c in b_df.columns])

stock_amt = stock_ref['stock_amt'].apply(lambda x: max(0.0, _try_float(x))).sum()
print("stock_amt with max(0):", stock_amt)

total_amt = b_df['stock_amt'].apply(lambda x: max(0.0, float(str(x).replace(',','').strip()) if pd.notna(x) else 0.0)).sum()
print("total_amt with max(0):", total_amt)
