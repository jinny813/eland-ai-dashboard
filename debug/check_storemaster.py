import os
import sys
sys.path.append(os.getcwd())
import pandas as pd
from database.gsheet_manager import GSheetManager

print("Connecting GSheetManager...")
gsm = GSheetManager()
if not gsm.is_connected:
    print(f"Connection failed! Error: {gsm.error_msg}")
    sys.exit(1)

print("Loading storemaster raw data...")
params = {"action": "read_raw", "sheetName": "storemaster"}
res = gsm._get(params)
print(f"Raw API result: {res}")
if gsm.error_msg:
    print(f"GSheetManager error_msg: {gsm.error_msg}")

if not res or not isinstance(res, list) or len(res) < 2:
    print("Failed to load storemaster or empty!")
    sys.exit(1)

headers = res[0]
data = res[1:]
df = pd.DataFrame(data, columns=headers)

print("\n================ storemaster columns ================")
print(df.columns.tolist())

print("\n================ storemaster preview ================")
print(df.head(10))
