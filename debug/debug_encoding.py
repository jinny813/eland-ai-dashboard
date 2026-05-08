import os, sys
sys.path.append(os.getcwd())
import pandas as pd
from database.gsheet_manager import GSheetManager

gsm = GSheetManager()
data = gsm.spreadsheet.worksheet("Records").get_all_records()
df = pd.DataFrame(data)

print("Unique Store Names (Raw & Hex):")
for s in df['store_name'].unique():
    try:
        raw = str(s)
        hex_val = raw.encode('utf-8').hex()
        print(f"Name: {raw} | Hex: {hex_val}")
    except:
        print(f"Error printing name")

# Let's check for Bucheon brands specifically
bucheon_brands = ["컬리수", "페리미츠", "베네통키즈", "아가방", "모이몰른", "뉴발란스키즈", "탑텐키즈", "스파오키즈", "행텐틴즈", "NBA키즈", "폴햄키즈", "MLB키즈"]
for b in bucheon_brands:
    sub = df[df['brand_name'].str.contains(b, na=False)]
    if not sub.empty:
        print(f"\nBrand: {b} found in stores: {sub['store_name'].unique()}")
