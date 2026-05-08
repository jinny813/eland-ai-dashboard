"""
AI Assortment Dashboard - 통합 테스트 스위트
=========================================
실행 방법: python scratch/test_suite.py [suite 이름]

suite 이름:
  best_names    - style_master 기반 BEST 상품명 조회 테스트
  baba_parser   - BabaGroupParser 재고/판매 파싱 테스트
  gas           - GAS (Google Apps Script) 연결 및 CRUD 테스트
  api           - 로컬 API 텍스트 업로드 테스트
  ai_agent      - AI 진단 리포트 생성 테스트
  timeseries    - 시계열 병합 로직 테스트
  all           - 전체 테스트 (기본값)
"""
import sys
import os
import json
import requests
import pandas as pd

# 프로젝트 루트 경로를 sys.path에 추가 (어느 위치에서 실행해도 동작)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SEP = "=" * 60


# ──────────────────────────────────────────────────────────
# [1] BEST 상품명 조회 테스트 (style_master 정합성 검증)
# ──────────────────────────────────────────────────────────
def test_best_names():
    """style_master.json 기반 상품명 보강 로직이 정상 동작하는지 검증한다."""
    print(f"\n{SEP}\n[1] BEST 상품명 조회 테스트\n{SEP}")
    from core.html_generator import _build_best_items

    data = [
        {"style_code": "A261PWC102", "item_name": "—", "style_name": "—",
         "sales_qty": 10, "stock_qty": 50, "stock_amt": 5000000, "normal_price": 499000, "store_type": "상설"},
        {"style_code": "A262PWT305", "item_name": "", "style_name": "",
         "sales_qty": 8,  "stock_qty": 30, "stock_amt": 1500000, "normal_price": 59000,  "store_type": "상설"},
        {"style_code": "UNKNOWN_CODE", "item_name": "—", "style_name": "—",
         "sales_qty": 5,  "stock_qty": 10, "stock_amt": 1000000, "normal_price": 100000, "store_type": "상설"},
    ]
    items = _build_best_items(pd.DataFrame(data)).get("store", [])

    ok = True
    for it in items:
        print(f"  [{it['style_code']}] 아이템: {it['item_name']}, 스타일: {it['style_name']}")
    if not any(it["style_code"] == "A261PWC102"   and it["item_name"] != "—"    for it in items): ok = False
    if not any(it["style_code"] == "A262PWT305"   and it["item_name"] == "티셔츠" for it in items): ok = False
    if not any(it["style_code"] == "UNKNOWN_CODE" and it["item_name"] == "—"    for it in items): ok = False
    print("✅ 통과" if ok else "❌ 실패")
    return ok


# ──────────────────────────────────────────────────────────
# [2] BabaGroupParser 파싱 테스트
# ──────────────────────────────────────────────────────────
def test_baba_parser():
    """BabaGroupParser가 재고·판매 데이터를 올바르게 파싱하는지 검증한다."""
    print(f"\n{SEP}\n[2] BabaGroupParser 파싱 테스트\n{SEP}")
    from parsers.babagroup_parser import BabaGroupParser

    parser = BabaGroupParser()
    inv_data = pd.DataFrame([
        {"모델명": "JJW1A123", "제조년": "2024", "계절": "봄", "부서": "여성", "재고": "10", "금액": "1,200,000", "TAG금액": "150,000", "매가": "120,000"},
        {"모델명": "JJW1A456", "제조년": "24",   "계절": "여름","부서": "여성", "재고": "5",  "금액": "600,000",  "TAG금액": "200,000", "매가": "100,000"},
    ])
    sales_data = pd.DataFrame([
        {"상품코드": "JJW1A123", "판매수": "2", "매출액": "240,000", "매출일자": "2024-04-01"},
        {"상품코드": "JJW1A456", "판매수": "1", "매출액": "100,000", "매출일자": "2024-04-02"},
    ])

    df_inv   = parser.parse_inventory(inv_data)
    df_sales = parser.parse_sales(sales_data)
    print("  [재고 파싱 결과]")
    print(df_inv[["style_code", "year", "stock_qty", "stock_amt"]].to_string(index=False))
    print("  [판매 파싱 결과]")
    print(df_sales.to_string(index=False))
    ok = len(df_inv) == 2 and len(df_sales) == 2
    print("✅ 통과" if ok else "❌ 실패")
    return ok


# ──────────────────────────────────────────────────────────
# [3] GAS 연결 및 CRUD 테스트
# ──────────────────────────────────────────────────────────
def test_gas_connection():
    """GAS 엔드포인트에 테스트 행을 삽입하고, 조회 후 삭제하는 전체 흐름을 검증한다."""
    print(f"\n{SEP}\n[3] GAS 연결 테스트\n{SEP}")
    import base64

    GAS_URL = "https://script.google.com/macros/s/AKfycbyc8GhVf0wbYs7vheF8VfGu1l7Z-XqnuVCXlu7ELnSqiF1oVqtKSUaTXDGnSzUF7trMng/exec"

    def gas_get(params):
        params["sheetName"] = "AI_Assortment_DB"
        r = requests.get(GAS_URL, params=params, timeout=30, allow_redirects=True)
        return r.status_code, r.text

    # 1) append_chunk
    test_row = [["DIAG_CHECK", 2024, 2, "TEST001", "진단테스트", "AB", "테스트",
                 "정상", 1, 10000, 0, 0, 9900, "", "진단브랜드", "NC신구로점", "여성", "상설", "4월", "", 0, ""]]
    encoded = base64.b64encode(json.dumps(test_row, ensure_ascii=False).encode("utf-8")).decode("ascii")
    s, b = gas_get({"action": "append_chunk", "data": encoded})
    print(f"  [insert] status={s}, ok={'success' in b and 'inserted' in b}")

    # 2) read_all 확인
    s2, b2 = gas_get({"action": "read_all"})
    found = "DIAG_CHECK" in b2
    print(f"  [read]   DIAG_CHECK 존재={'✅' if found else '❌'}")

    # 3) delete 정리
    s3, b3 = gas_get({"action": "delete", "store_name": "NC신구로점", "brand_name": "진단브랜드", "data_month": "4월"})
    print(f"  [delete] status={s3}, body={b3[:80]}")

    ok = found
    print("✅ 통과" if ok else "❌ 실패")
    return ok


# ──────────────────────────────────────────────────────────
# [4] API 텍스트 업로드 테스트
# ──────────────────────────────────────────────────────────
def test_api_text_upload():
    """로컬 Streamlit API 서버에 텍스트 형식 데이터를 업로드하는 흐름을 검증한다."""
    print(f"\n{SEP}\n[4] API 텍스트 업로드 테스트\n{SEP}")

    URL = "http://localhost:8000/api/upload"
    inv_text  = "스타일\t현재고\t재고금액\t생산년도\t시즌코드\nRMTEST01\t10\t1000000\t2024\t2\nRMTEST02\t5\t500000\t2024\t4"
    sales_text = "스타일\t판매수량\t판매금액\nRMTEST01\t2\t200000\nRMTEST02\t1\t100000"
    data = {"store_name": "NC신구로점", "category_group": "여성",
            "brand_name": "로엠|정상", "data_month": "4월",
            "inv_text": inv_text, "sales_text": sales_text}
    try:
        r = requests.post(URL, data=data, timeout=10)
        ok = r.status_code == 200
        print(f"  status={r.status_code}, body={r.text[:120]}")
    except Exception as e:
        print(f"  ❌ API 서버 연결 불가: {e}")
        ok = False
    print("✅ 통과" if ok else "❌ 실패 (로컬 서버가 실행 중인지 확인)")
    return ok


# ──────────────────────────────────────────────────────────
# [5] AI 진단 리포트 생성 테스트
# ──────────────────────────────────────────────────────────
def test_ai_agent():
    """AIAgent가 Claude API를 호출하여 진단 리포트를 정상 반환하는지 검증한다."""
    print(f"\n{SEP}\n[5] AI 진단 리포트 생성 테스트\n{SEP}")
    from ai_agent import AIAgent

    agent = AIAgent()
    print(f"  모델: {agent.MODEL}")
    scores      = {"total": 85, "dis": 90, "fresh": 80, "best": 85, "season": 90}
    data_summary = {"item": "jacket", "pct": 45}
    bp_summary   = {"item": "jacket", "pct": 50}
    try:
        result = agent.generate_report("나이스클랍", scores, data_summary, bp_summary, "item")
        ok = "진단 준비 중" not in result.get("core_title", "")
        print(f"  title={result.get('core_title', '')[:60]}")
    except Exception as e:
        print(f"  ❌ 예외: {e}")
        ok = False
    print("✅ 통과" if ok else "❌ 실패 (API 키 또는 네트워크 확인)")
    return ok


# ──────────────────────────────────────────────────────────
# [6] 시계열 병합 로직 테스트
# ──────────────────────────────────────────────────────────
def test_timeseries():
    """DataManager의 시계열 병합 시 재고량이 최신 날짜에만 할당되는지 검증한다."""
    print(f"\n{SEP}\n[6] 시계열 병합 로직 테스트\n{SEP}")
    from core.data_manager import DataManager

    dm = DataManager()
    inv_data = pd.DataFrame([
        {"매장명": "NC신구로", "품번": "BABA-001", "판매구분": "정상", "총재고_수량": "100", "총재고_매가": "1,000,000"},
    ])
    sales_data = pd.DataFrame([
        {"품번": "BABA-001", "판매수량": "5",  "판매액": "50,000",  "판매일자": "2026-03-01"},
        {"품번": "BABA-001", "판매수량": "10", "판매액": "100,000", "판매일자": "2026-03-15"},
        {"품번": "BABA-001", "판매수량": "2",  "판매액": "20,000",  "판매일자": "2026-03-30"},
    ])
    try:
        final = dm.process_and_merge(
            brand_name="JJ지고트", store_name="NC신구로", category_group="여성",
            store_type="상설", data_month="3월", inv_data=inv_data, sales_data=sales_data
        )
        latest = final[final["sales_date"] == "2026-03-30"].iloc[0]
        old    = final[final["sales_date"] == "2026-03-15"].iloc[0]
        ok = (len(final) == 3 and latest["stock_qty"] == 100
              and old["stock_qty"] == 0 and final["sales_qty"].sum() == 17)
        print(f"  행수={len(final)}, 최신재고={latest['stock_qty']}, 이전재고={old['stock_qty']}, 판매합계={final['sales_qty'].sum()}")
    except Exception as e:
        print(f"  ❌ 예외: {e}")
        ok = False
    print("✅ 통과" if ok else "❌ 실패")
    return ok


# ──────────────────────────────────────────────────────────
# 메인 디스패처
# ──────────────────────────────────────────────────────────
SUITES = {
    "best_names":  test_best_names,
    "baba_parser": test_baba_parser,
    "gas":         test_gas_connection,
    "api":         test_api_text_upload,
    "ai_agent":    test_ai_agent,
    "timeseries":  test_timeseries,
}

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = {}
    if target == "all":
        for name, fn in SUITES.items():
            results[name] = fn()
    elif target in SUITES:
        results[target] = SUITES[target]()
    else:
        print(f"알 수 없는 suite: '{target}'. 사용 가능: {list(SUITES.keys()) + ['all']}")
        sys.exit(1)

    print(f"\n{SEP}\n최종 결과\n{SEP}")
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")
