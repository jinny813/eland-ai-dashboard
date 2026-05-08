import os
import sys
import json
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def scan_specific_brands():
    target_brands = ["샤틴", "보니스팍스", "시슬리", "로엠", "플라스틱아일랜드", "제시뉴욕", "안지크"]
    
    # 1. Load Master Cache (to avoid re-searching)
    master_path = os.path.join(os.path.dirname(__file__), "..", "core", "style_master.json")
    with open(master_path, "r", encoding="utf-8") as f:
        master = json.load(f)
    
    # 2. Fetch Records
    gsm = GSheetManager()
    print("Fetching records for specific brands scan...")
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    
    # 최근 2주 데이터 타겟
    df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
    max_date = df['sales_date'].max()
    cutoff = max_date - pd.Timedelta(days=14)
    recent_df = df[(df['sales_date'] >= cutoff) & (df['brand_name'].isin(target_brands))].copy()
    
    if recent_df.empty:
        print("No recent data found for target brands.")
        return

    print(f"\nScanning TOP 5 styles for target brands (Missing in master or names are empty):")
    for brand in target_brands:
        b_df = recent_df[recent_df['brand_name'] == brand].copy()
        if b_df.empty:
            print(f"[{brand}] No recent data.")
            continue
            
        b_df['sales_qty'] = pd.to_numeric(b_df['sales_qty'], errors='coerce').fillna(0)
        agg = b_df.groupby("style_code").agg({
            'sales_qty': 'sum',
            'item_name': 'first',
            'style_name': 'first'
        }).reset_index()
        
        top_list = agg.nlargest(5, "sales_qty")
        
        print(f"\n--- {brand} TOP 5 ---")
        for _, row in top_list.iterrows():
            code = row['style_code']
            curr_item = str(row['item_name']).strip()
            curr_style = str(row['style_name']).strip()
            
            # 마스터에 없거나, 데이터상 명칭이 '—' 또는 빈값인 경우만 출력
            is_missing = code not in master or curr_item in ['—', '', 'None'] or curr_style in ['—', '', 'None']
            status = "[NEED SEARCH]" if is_missing else "[OK]"
            print(f"{status} {code} (Sales: {row['sales_qty']}, Name: {curr_item} / {curr_style})")

if __name__ == "__main__":
    scan_specific_brands()
