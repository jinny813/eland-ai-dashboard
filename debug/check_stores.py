import os
import sys
sys.path.append(os.getcwd())
import pandas as pd
from database.gsheet_manager import GSheetManager

print("Initializing GSheetManager...")
gsm = GSheetManager()
if not gsm.is_connected:
    print("Connection failed!")
    sys.exit(1)

print("Loading Records sheet...")
data = gsm.spreadsheet.worksheet("Records").get_all_records()
df = pd.DataFrame(data)

print("\n================ UNIQUE STORES IN RECORDS ================")
print(df['store_name'].unique().tolist() if 'store_name' in df.columns else "store_name column NOT found!")

print("\n================ COLUMN NAMES IN RECORDS ================")
print(df.columns.tolist())
