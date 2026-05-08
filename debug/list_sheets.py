import requests
import json

gas_id = "AKfycbxbO5tUGfAENxX24nyQELlfDwZondvv9xFkjdje9jrNm-NkJyj3USNT3Ji5IKZ6OYuSsQ"
gas_url = f"https://script.google.com/macros/s/{gas_id}/exec"

try:
    params = {"action": "list_sheets"}
    resp = requests.get(gas_url, params=params, timeout=30)
    print(resp.text)
except Exception as e:
    print(f"Error: {e}")
