import os
import sys
import json
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def extract_all_brand_styles():
    gsm = GSheetManager()
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    
    # [v100.99] 데이터 전처리
    df['sales_qty'] = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
    df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
    
    # 최근 30일 데이터 우선
    max_date = df['sales_date'].max()
    cutoff = max_date - pd.Timedelta(days=30)
    recent_df = df[df['sales_date'] >= cutoff].copy()
    
    if recent_df.empty:
        recent_df = df # 데이터가 너무 없으면 전체 대상
        
    report = []
    brands = df['brand_name'].unique()
    
    for brand in brands:
        if not brand: continue
        b_df = recent_df[recent_df['brand_name'] == brand].copy()
        if b_df.empty: continue
            
        agg = b_df.groupby("style_code").agg({
            'sales_qty': 'sum',
            'item_name': 'first',
            'style_name': 'first'
        }).reset_index()
        
        top_list = agg.nlargest(10, "sales_qty")
        
        brand_data = {"brand": brand, "styles": []}
        for _, row in top_list.iterrows():
            brand_data["styles"].append({
                "code": row['style_code'],
                "sales": int(row['sales_qty']),
                "item": str(row['item_name']),
                "style": str(row['style_name'])
            })
        report.append(brand_data)
        
    output_path = os.path.join(os.path.dirname(__file__), "all_brand_styles.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {output_path}")

if __name__ == "__main__":
    extract_all_brand_styles()
