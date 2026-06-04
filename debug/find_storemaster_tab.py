import os
import sys
sys.path.append(os.getcwd())
from database.gsheet_manager import GSheetManager

gsm = GSheetManager()

candidates = [
    "storemaster", "storemaster ", "Storemaster", "StoreMaster", "store_master",
    "매장마스터", "점포마스터", "매장마스터 ", "storemasterDB", "storemaster_db"
]

print("Scanning sheet names for storemaster data...")

for cand in candidates:
    print(f"Trying sheetName='{cand}'...")
    params = {"action": "read_raw", "sheetName": cand}
    res = gsm._get(params)
    if res and isinstance(res, list) and len(res) >= 2:
        print(f"\n🎉 SUCCESS! Found valid tab name: '{cand}'")
        print("Columns:", res[0])
        print("First row preview:", res[1])
        break
else:
    print("\n❌ Could not find any valid tab for storemaster with standard candidates.")
