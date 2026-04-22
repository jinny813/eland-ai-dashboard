import os
import sys
import json
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def identify_missing_styles():
    # 1. Load Master Cache
    master_path = os.path.join(os.path.dirname(__file__), "..", "core", "style_master.json")
    with open(master_path, "r", encoding="utf-8") as f:
        master = json.load(f)
    
    # 2. Fetch Records
    gsm = GSheetManager()
    print("Fetching records for scanning missing styles...")
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    
    # 상설(Outlet) 데이터만 대상 (정상은 데이터에 원래 이름이 있음)
    df = df[df['store_type'].astype(str).str.contains("상설")].copy()
    if df.empty:
        print("No outlet data found.")
        return

    # 최근 2주 데이터 타겟
    df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
    max_date = df['sales_date'].max()
    cutoff = max_date - pd.Timedelta(days=14)
    recent_df = df[df['sales_date'] >= cutoff].copy()
    
    brands = recent_df['brand_name'].unique()
    missing_all = []

    for brand in brands:
        brand_df = recent_df[recent_df['brand_name'] == brand].copy()
        # [v100.34] 수치형 변환 보장
        brand_df['sales_qty'] = pd.to_numeric(brand_df['sales_qty'], errors='coerce').fillna(0)
        # 브랜드별 BEST 품번 추출
        agg = brand_df.groupby("style_code")["sales_qty"].sum().reset_index()
        top10 = agg.nlargest(10, "sales_qty")
        
        for code in top10['style_code']:
            if code not in master:
                missing_all.append({"brand": brand, "code": code})
                
    if not missing_all:
        print("No missing styles found in current BEST lists.")
        return
        
    print(f"\nFound {len(missing_all)} missing style(s) across all brands:")
    for m in missing_all:
        print(f"[{m['brand']}] {m['code']}")

if __name__ == "__main__":
    identify_missing_styles()
