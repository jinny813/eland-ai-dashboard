import pandas as pd
import json
import os
import sys

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.html_generator import _build_best_items

def test_nice_claup_enrichment():
    # 1. 가상 데이터 생성 (나이스클랍 품번 포함, 이름은 누락됨)
    data = [
        {"style_code": "A261PWC102", "item_name": "—", "style_name": "—", "sales_qty": 10, "stock_qty": 50, "stock_amt": 5000000, "normal_price": 499000, "store_type": "상설"},
        {"style_code": "A262PWT305", "item_name": "", "style_name": "", "sales_qty": 8, "stock_qty": 30, "stock_amt": 1500000, "normal_price": 59000, "store_type": "상설"},
        {"style_code": "UNKNOWN_CODE", "item_name": "—", "style_name": "—", "sales_qty": 5, "stock_qty": 10, "stock_amt": 1000000, "normal_price": 100000, "store_type": "상설"}
    ]
    df = pd.DataFrame(data)
    
    # 2. 로직 실행
    result = _build_best_items(df)
    items = result.get('store', [])
    
    # 3. 결과 검증
    print("Verification Results:")
    for it in items:
        code = it['style_code']
        name = it['item_name']
        style = it['style_name']
        try:
            print(f"[{code}] Item: {name}, Style: {style}")
        except:
            print(f"[{code}] (Printing failed due to encoding)")
        
    # 기대하는 결과 확인
    assert any(it['style_code'] == "A261PWC102" and it['item_name'] == "자켓" for it in items), "A261PWC102 enrichment failed"
    assert any(it['style_code'] == "A262PWT305" and it['item_name'] == "티셔츠" for it in items), "A262PWT305 enrichment failed"
    assert any(it['style_code'] == "UNKNOWN_CODE" and it['item_name'] == "—" for it in items), "Unknown code should remain '—'"
    
    print("\n✅ Verification successful! Styles are correctly enriched from style_master.json.")

if __name__ == "__main__":
    test_nice_claup_enrichment()
