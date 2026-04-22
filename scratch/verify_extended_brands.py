import pandas as pd
import json
import os
import sys

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.html_generator import _build_best_items

def test_extended_brand_enrichment():
    # 1. 가상 데이터 생성 (타겟 브랜드 품번 포함, 이름 누락)
    data = [
        {"style_code": "SAWSF6431", "brand_name": "시슬리", "item_name": "—", "style_name": "—", "sales_qty": 10, "stock_qty": 50, "stock_amt": 5000000, "normal_price": 499000, "store_type": "상설"},
        {"style_code": "PQ1CL201", "brand_name": "플라스틱아일랜드", "item_name": "", "style_name": "", "sales_qty": 8, "stock_qty": 30, "stock_amt": 1500000, "normal_price": 59000, "store_type": "상설"},
        {"style_code": "S261K954A", "brand_name": "샤틴", "item_name": "—", "style_name": "—", "sales_qty": 5, "stock_qty": 10, "stock_amt": 1000000, "normal_price": 100000, "store_type": "상설"},
        {"style_code": "AK1BR5100", "brand_name": "안지크", "item_name": "—", "style_name": "—", "sales_qty": 7, "stock_qty": 15, "stock_amt": 2000000, "normal_price": 300000, "store_type": "상설"}
    ]
    df = pd.DataFrame(data)
    
    # 2. 로직 실행
    result = _build_best_items(df)
    items = result.get('store', [])
    
    # 3. 결과 검증
    print("Verification Results (Extended Brands):")
    for it in items:
        code = it['style_code']
        name = it['item_name']
        style = it['style_name']
        try:
            print(f"[{code}] Item: {name}, Style: {style}")
        except:
            print(f"[{code}] (Encoding Error)")
        
    # 기대하는 결과 확인
    assert any(it['style_code'] == "SAWSF6431" and "셔츠" in it['item_name'] for it in items), "Sisley enrichment failed"
    assert any(it['style_code'] == "PQ1CL201" and "티셔츠" in it['item_name'] for it in items), "Plastic Island enrichment failed"
    assert any(it['style_code'] == "S261K954A" and "니트" in it['item_name'] for it in items), "Satin enrichment failed"
    assert any(it['style_code'] == "AK1BR5100" and "코트" in it['item_name'] for it in items), "Anzicc enrichment failed"
    
    print("\nVerification successful! All target brands are correctly enriched.")

if __name__ == "__main__":
    test_extended_brand_enrichment()
