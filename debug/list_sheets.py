import requests

gas_id = "AKfycbxbO5tUGfAENxX24nyQELlfDwZondvv9xFkjdje9jrNm-NkJyj3USNT3Ji5IKZ6OYuSsQ"
gas_url = f"https://script.google.com/macros/s/{gas_id}/exec"

try:
    # 실존하는 officemaster 시트명을 넘겨주어 스프레드시트 락을 우회하여 전체 탭 리스트 확보 시도
    params = {"action": "list_sheets", "sheetName": "officemaster"}
    resp = requests.get(gas_url, params=params, timeout=30)
    print(resp.text)
except Exception as e:
    print(f"Error: {e}")
