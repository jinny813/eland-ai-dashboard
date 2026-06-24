import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
prompt = """너는 10년차 경영컨설턴트이다. 
아래 데이터를 분석해서 4가지 액션을 도출해. 각 액션은 최소 500자 이상 아주 길고 구체적으로 적어.

데이터: 매출 1억, 전월 5천만. 

출력 규칙:
무조건 아래 JSON 구조로만 출력. 
"""

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "maxOutputTokens": 8000,
        "temperature": 0.3,
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "actions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "STRING"
                    }
                }
            },
            "required": ["actions"]
        }
    }
}

req_data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")

try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        text_resp = res["candidates"][0]["content"]["parts"][0]["text"]
        print("RAW:")
        print(text_resp)
        parsed = json.loads(text_resp)
        print("PARSED SUCCESS:", len(parsed.get("actions", [])))
except Exception as e:
    print("ERROR:", e)
