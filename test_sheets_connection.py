"""
test_sheets_connection.py — Google Sheets 연결 테스트
=====================================================
실행: python test_sheets_connection.py

체크 항목:
  1) 서비스 계정 키 파일 존재 여부
  2) Google Sheets API 인증 성공 여부
  3) 스프레드시트 접근 및 Records 탭 존재 여부
  4) 마스터 헤더 정합성
  5) 현재 DB 데이터 현황 리포트
"""

import sys
import json
from pathlib import Path

def check_packages():
    missing = []
    for pkg in ['gspread', 'google.oauth2']:
        try: __import__(pkg)
        except ImportError: missing.append(pkg)
    if missing:
        print(f"❌ 누락 패키지: {missing}")
        print("   → pip install gspread google-auth 실행 후 재시도")
        sys.exit(1)
    print("✅ 패키지 확인 완료 (gspread, google-auth)")

check_packages()

import gspread
from google.oauth2.service_account import Credentials

# ── 설정 (실제 값으로 수정 됨)
CREDENTIALS_PATH = "credentials.json"
SPREADSHEET_ID   = "1HAXYDbqp4IJk34qSFiK2NvFNaaebUFwkWFRhjjw-OOM"   
SHEET_NAME       = "Records"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
MASTER_COLUMNS = [
    "no", "year", "season_code", "style_code", "item_name",
    "price_type", "stock_qty", "stock_amt", "sales_qty", "sales_amt",
    "normal_price", "brand_name", "store_name", "category_group",
    "store_type", "data_month", "sales_date",
]


def test_1_credentials_file():
    print("\n[TEST 1] 서비스 계정 키 파일 확인")
    path = Path(CREDENTIALS_PATH)
    if not path.exists():
        print(f"  ❌ 파일 없음: {CREDENTIALS_PATH}")
        print("     → Google Cloud Console에서 서비스 계정 키(JSON) 발급 후")
        print(f"       {CREDENTIALS_PATH} 경로에 배치하세요")
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        email = data.get('client_email', '미확인')
        print(f"  ✅ 파일 확인 완료 — 서비스 계정: {email}")
        return True
    except Exception as e:
        print(f"  ❌ JSON 파싱 실패: {e}")
        return False


def test_2_auth():
    print("\n[TEST 2] Google Sheets API 인증")
    try:
        creds  = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        print("  ✅ 인증 성공")
        return client
    except Exception as e:
        print(f"  ❌ 인증 실패: {e}")
        return None


def test_3_spreadsheet(client):
    print("\n[TEST 3] 스프레드시트 접근")
    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        print("  ⚠️  SPREADSHEET_ID가 기본값입니다.")
        print("     → Google Sheets URL에서 /d/{ID}/edit 부분의 ID를 복사해 입력하세요")
        return None
    try:
        ss    = client.open_by_key(SPREADSHEET_ID)
        names = [ws.title for ws in ss.worksheets()]
        print(f"  ✅ 스프레드시트 접근 성공 — 시트 탭: {names}")
        if SHEET_NAME not in names:
            print(f"  ⚠️  '{SHEET_NAME}' 탭 없음 — 자동 생성")
            ss.add_worksheet(title=SHEET_NAME, rows=5000, cols=len(MASTER_COLUMNS))
            print(f"  ✅ '{SHEET_NAME}' 탭 생성 완료")
        return ss.worksheet(SHEET_NAME)
    except Exception as e:
        print(f"  ❌ 접근 실패: {e}")
        print("     → 서비스 계정 이메일을 Google Sheets 편집자로 공유했는지 확인하세요")
        return None


def test_4_header(sheet):
    print("\n[TEST 4] 마스터 헤더 정합성 확인")
    try:
        current = sheet.row_values(1)
        if not current:
            print("  ⚠️  1행 비어있음 — 마스터 헤더 자동 기록")
            sheet.update("A1", [MASTER_COLUMNS])
            print("  ✅ 헤더 기록 완료")
        elif current == MASTER_COLUMNS:
            print(f"  ✅ 헤더 정상 — {len(MASTER_COLUMNS)}개 컬럼 완전 일치")
        else:
            missing = [c for c in MASTER_COLUMNS if c not in current]
            extra   = [c for c in current if c not in MASTER_COLUMNS]
            print("  ⚠️  헤더 불일치 감지")
            if missing: print(f"     누락 컬럼: {missing}")
            if extra:   print(f"     추가 컬럼: {extra}")
            print("  → action2_upsert.py의 ensure_master_header() 실행 시 자동 보정됩니다")
        return True
    except Exception as e:
        print(f"  ❌ 헤더 확인 실패: {e}")
        return False


def test_5_data_count(sheet):
    print("\n[TEST 5] 현재 DB 데이터 현황")
    try:
        all_vals = sheet.get_all_values()
        total = len(all_vals) - 1
        print(f"  ✅ 총 데이터: {total}행")
        if total > 0:
            import pandas as pd
            df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
            if 'brand_name' in df.columns:
                grp = df[df['brand_name'].str.strip() != ''].groupby(
                    ['brand_name', 'store_name', 'data_month']
                ).size().reset_index(name='행수')
                print("  브랜드별 데이터 현황:")
                for _, row in grp.iterrows():
                    print(f"    {row['brand_name']} | {row['store_name']} | {row['data_month']} → {row['행수']}행 ✓")
        else:
            print("  (아직 데이터 없음 — 업로드 후 재확인)")
        return True
    except Exception as e:
        print(f"  ❌ 데이터 확인 실패: {e}")
        return False


if __name__ == "__main__":
    print("=" * 55)
    print("  E·LAND AI 상품관리 — Google Sheets 연결 테스트")
    print("=" * 55)

    if not test_1_credentials_file():
        sys.exit(1)

    client = test_2_auth()
    if not client:
        sys.exit(1)

    sheet = test_3_spreadsheet(client)
    if not sheet:
        sys.exit(1)

    test_4_header(sheet)
    test_5_data_count(sheet)

    print("\n" + "=" * 55)
    print("  모든 테스트 완료 ✅")
    print("  다음 단계: uvicorn api.main:app --reload --port 8000")
    print("=" * 55)
