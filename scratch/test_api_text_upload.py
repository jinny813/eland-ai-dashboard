import requests

url = "http://localhost:8000/api/upload"

# 1. 테스트용 탭 구분 텍스트 데이터 (로엠 스타일)
inv_text = """스타일\t현재고\t재고금액\t생산년도\t시즌코드
RMTEST01\t10\t1000000\t2024\t2
RMTEST02\t5\t500000\t2024\t4"""

sales_text = """스타일\t판매수량\t판매금액
RMTEST01\t2\t200000
RMTEST02\t1\t100000"""

# 2. 폼 데이터 구성
data = {
    "store_name": "NC신구로점",
    "category_group": "여성",
    "brand_name": "로엠|정상",
    "data_month": "4월",
    "inv_text": inv_text,
    "sales_text": sales_text
}

# 3. API 요청
print(f"Sending text upload request to {url}...")
try:
    response = requests.post(url, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
