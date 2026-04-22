"""
GAS append_chunk / delete 동작 진단 스크립트
실행: python scratch/test_gas_connection.py
"""
import base64
import json
import requests

GAS_URL = "https://script.google.com/macros/s/AKfycbyc8GhVf0wbYs7vheF8VfGu1l7Z-XqnuVCXlu7ELnSqiF1oVqtKSUaTXDGnSzUF7trMng/exec"
SEP = "-" * 60

def gas_get(params):
    params["sheetName"] = "AI_Assortment_DB"
    r = requests.get(GAS_URL, params=params, timeout=30, allow_redirects=True)
    return r.status_code, r.text

# ── 1. append_chunk — base64 테스트 행 1개 ─────────────────
print(SEP)
print("[1] GET append_chunk (Base64 인코딩 테스트 행)")
test_row = [["DIAG_CHECK", 2024, 2, "TEST001", "진단테스트", "AB", "테스트",
             "정상", 1, 10000, 0, 0, 9900, "", "진단브랜드",
             "NC신구로점", "여성", "상설", "4월", "", 0, ""]]
encoded = base64.b64encode(json.dumps(test_row, ensure_ascii=False).encode("utf-8")).decode("ascii")
status, body = gas_get({"action": "append_chunk", "data": encoded})
print(f"  Status : {status}")
print(f"  Body   : {body[:300]}")
print(f"  → 예상: {{\"status\":\"success\",\"inserted\":1}}")
print(f"  → 실제 일치 여부: {'success' in body and 'inserted' in body}")

# ── 2. read_all로 실제 기록 여부 확인 ──────────────────────
print(SEP)
print("[2] GET read_all — DIAG_CHECK 행 존재 여부 확인")
status2, body2 = gas_get({"action": "read_all"})
print(f"  Status: {status2}")
if "DIAG_CHECK" in body2:
    print("  ✅ DIAG_CHECK 행이 DB에 있음 → append_chunk 정상 동작")
else:
    print("  ❌ DIAG_CHECK 행 없음 → GAS가 실제로 쓰지 않는 중")
    print(f"  Body preview: {body2[:200]}")

# ── 3. delete 테스트 ────────────────────────────────────────
print(SEP)
print("[3] GET delete (진단브랜드 / NC신구로점 / 4월)")
status3, body3 = gas_get({"action": "delete", "store_name": "NC신구로점",
                           "brand_name": "진단브랜드", "data_month": "4월"})
print(f"  Status: {status3}")
print(f"  Body  : {body3[:200]}")

print(SEP)
print("진단 완료.")

