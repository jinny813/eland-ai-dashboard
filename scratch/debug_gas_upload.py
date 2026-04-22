import requests
import base64
import json

GAS_URL = "https://script.google.com/macros/s/AKfycbxbO5tUGfAENxX24nyQELlfDwZondvv9xFkjdje9jrNm-NkJyj3USNT3Ji5IKZ6OYuSsQ/exec"

def test_upload_debug():
    # 1. 10행 데이터 생성 (실제 데이터와 유사한 형식)
    sample_row = [1, 2024, 2, "STYLE1", "테스트상품", "A", "상품명", "정상", 10, 100000, 5, 50000, 20000, "2024-04-19", "로엠", "NC신구로", "여성", "상설", "4월", "NEW", 0.0, "UID_1"]
    payload_list = [sample_row[:] for _ in range(10)]
    for i, row in enumerate(payload_list):
        row[0] = i + 1
        row[-1] = f"UID_{i+1}"
        
    chunk_json = json.dumps(payload_list, ensure_ascii=False)
    b64_payload = base64.b64encode(chunk_json.encode('utf-8')).decode('utf-8')
    
    # 2. POST 요청 테스트 (Form Data 방식 - 현재 앱 방식)
    print(f"[TEST 1] POST with Form Data (action: append_bulk_b64)")
    data = {
        'action': 'append_bulk_b64',
        'brand_name': '로엠',
        'payload_b64': b64_payload,
        'sheetName': 'Records'
    }
    
    try:
        r = requests.post(GAS_URL, data=data, timeout=30)
        print(f"  Status: {r.status_code}")
        print(f"  Body (first 500): {r.text[:500]}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    test_upload_debug()
