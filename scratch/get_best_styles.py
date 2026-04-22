import os
import sys
import pandas as pd

# d:\AI Assortment Agent 경로를 sys.path에 추가하여 모듈 로드 가능하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.gsheet_manager import GSheetManager

def get_best_codes():
    gsm = GSheetManager()
    print("Loading all records from GSheet...")
    results = gsm._get({"action": "read_all"})
    if not results:
        print("Failed to load records:", gsm.error_msg)
        return
    
    df = pd.DataFrame(results)
    if df.empty:
        print("No data found in Records sheet.")
        return

    # 최근 2주(14일) 데이터 필터링 (sales_date 기준)
    try:
        df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
        recent_date = df['sales_date'].max() - pd.Timedelta(days=14)
        recent_df = df[df['sales_date'] >= recent_date].copy()
    except Exception as e:
        print("Date filtering failed, using all data matching brands:", e)
        recent_df = df.copy()

    brands = ["베네통", "시슬리"]
    for brand in brands:
        print(f"\n--- Best Styles for {brand} ---")
        brand_df = recent_df[recent_df['brand_name'] == brand].copy()
        if brand_df.empty:
            print(f"No records found for {brand} in the last 14 days.")
            continue
            
        # 판매량 집계
        brand_agg = brand_df.groupby("style_code")["sales_qty"].sum().reset_index()
        top10 = brand_agg.sort_values("sales_qty", ascending=False).head(10)
        
        for i, row in top10.iterrows():
            print(f"Code: {row['style_code']}, Qty: {row['sales_qty']}")

if __name__ == "__main__":
    get_best_codes()
