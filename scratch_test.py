import requests
import json

req_body = {
    "brand_name": "로엠",
    "indicator_id": "item",
    "scores": {"total": 100, "dis": 10, "fresh": 10, "best": 10, "season": 10},
    "data_summary": {"some": "data"}
}

try:
    resp = requests.post("http://localhost:8000/api/diagnose", json=req_body)
    print("Status Code:", resp.status_code)
    print("Response JSON:", resp.json())
except Exception as e:
    print("Error:", e)
