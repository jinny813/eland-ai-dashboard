import os
import sys
import json
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.gsheet_manager import GSheetManager

def debug_brand_data():
    target_brands_ko = ["샤틴", "보니스팍스", "시슬리", "로엠", "플라스틱아일랜드", "제시뉴욕", "안지크"]
    gsm = GSheetManager()
    results = gsm.call_gas("read_all")
    if not results:
        print("Failed to load records.")
        return
        
    df = pd.DataFrame(results)
    print(f"Total records: {len(df)}")
    
    # [v101.0] 모든 고유 브랜드명 출력 (인코딩 우회용 파일 저장)
    unique_brands = df['brand_name'].unique().tolist()
    with open("debug_brands.json", "w", encoding="utf-8") as f:
        json.dump(unique_brands, f, ensure_ascii=False, indent=2)
    
    # 데이터 전처리
    df['sales_qty'] = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
    df['sales_date'] = pd.to_datetime(df['sales_date'], errors='coerce')
    
    # 각 브랜드별로 전체 기간(필터 없이) TOP 5 추출
    report = []
    for brand in unique_brands:
        if not brand: continue
        b_df = df[df['brand_name'] == brand].copy()
        
        agg = b_df.groupby("style_code").agg({
            'sales_qty': 'sum',
            'item_name': 'first',
            'style_name': 'first',
            'sales_date': 'max'
        }).reset_index()
        
        top_list = agg.nlargest(5, "sales_qty")
        
        styles = []
        for _, row in top_list.iterrows():
            styles.append({
                "code": row['style_code'],
                "sales": int(row['sales_qty']),
                "item": str(row['item_name']),
                "style": str(row['style_name']),
                "last_sold": str(row['sales_date'])
            })
        
        report.append({
            "brand": brand,
            "count": len(b_df),
            "top_styles": styles
        })
        
    with open("full_brand_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Full report saved to full_brand_report.json")

if __name__ == "__main__":
    debug_brand_data()
