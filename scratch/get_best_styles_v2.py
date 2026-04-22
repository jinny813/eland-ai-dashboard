import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def get_recent_best():
    gsm = GSheetManager()
    # read_all 대신 read_raw 등으로 시도해볼 수도 있으나 우선 read_all의 대안으로
    # 최근 데이터가 하단에 있다고 가정하고 뒷부분만 읽어오는 액션이 있는지 확인 필요.
    # 하지만 GAS side를 수정할 수 없으므로, read_all이 실패한다면 데이터 양이 많은 것임.
    
    print("Fetching records...")
    # read_all 대신 read_raw 시도 (때로는 이게 더 가벼움)
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
    
    # 베네통, 시슬리 필터링
    target_brands = ["베네통", "시슬리"]
    
    for brand in target_brands:
        print(f"\n[{brand}] Best 10 Codes:")
        brand_df = df[df['brand_name'] == brand].copy()
        if brand_df.empty:
            print("No data found for brand.")
            continue
            
        # 최근 14일치 판매량 합계
        max_date = brand_df['sales_date'].max()
        if pd.isna(max_date):
            # 날짜 파싱 실패 시 전체 데이터 기반
            agg = brand_df.groupby("style_code")["sales_qty"].sum().reset_index()
        else:
            cutoff = max_date - pd.Timedelta(days=14)
            agg = brand_df[brand_df['sales_date'] >= cutoff].groupby("style_code")["sales_qty"].sum().reset_index()
            
        top10 = agg.sort_values("sales_qty", ascending=False).head(10)
        for _, row in top10.iterrows():
            print(f"- {row['style_code']} ({row['sales_qty']} EA)")

if __name__ == "__main__":
    get_recent_best()
