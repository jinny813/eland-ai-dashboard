import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def get_more_best():
    gsm = GSheetManager()
    print("Fetching records for more brands...")
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
    
    # 베네통, 시슬리 외 주요 브랜드 필터링
    target_brands = ["인동팩토리(리스트,쉬즈미스)", "바바팩토리", "JJ지고트", "나이스클럽"]
    
    for brand in target_brands:
        print(f"\n[{brand}] Best 10 Codes:")
        brand_df = df[df['brand_name'] == brand].copy()
        if brand_df.empty:
            print("No data found for brand.")
            continue
            
        brand_df['sales_qty'] = pd.to_numeric(brand_df['sales_qty'], errors='coerce').fillna(0)
        max_date = brand_df['sales_date'].max()
        cutoff = max_date - pd.Timedelta(days=14)
        agg = brand_df[brand_df['sales_date'] >= cutoff].groupby("style_code")["sales_qty"].sum().reset_index()
            
        top10 = agg.sort_values("sales_qty", ascending=False).head(10)
        for _, row in top10.iterrows():
            print(f"- {row['style_code']} ({row['sales_qty']} EA)")

if __name__ == "__main__":
    get_more_best()
