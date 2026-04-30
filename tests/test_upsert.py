from database.gsheet_manager import GSheetManager
import pandas as pd

mgr = GSheetManager()

# Dummy data 1 (로엠)
df_roem = pd.DataFrame([{
    'year': '26년', 'season_code': '1', 'style_code': 'RM01',
    'stock_qty': 100, 'stock_amt': 5000000, 
    'store_name': '신구로점', 'brand_name': '로엠', 'data_month': '3월'
}])

# Dummy data 2 (미쏘)
df_mixxo = pd.DataFrame([{
    'year': '26년', 'season_code': '1', 'style_code': 'MI01',
    'stock_qty': 200, 'stock_amt': 8000000, 
    'store_name': '신구로점', 'brand_name': '미쏘', 'data_month': '3월'
}])

# 기존 모든 데이터 클리어 (테스트 목적)
try:
    mgr.spreadsheet.worksheet("Records").clear()
except: pass

print("1. 로엠 데이터 업로드 시도...")
mgr.overwrite_record(df_roem, '신구로점', '로엠', '3월')

print("2. 미쏘 데이터 업로드 시도 (누적 테스트)...")
mgr.overwrite_record(df_mixxo, '신구로점', '미쏘', '3월')

# 결과 확인
res = mgr.spreadsheet.worksheet("Records").get_all_records()
print(f"최종 DB 레코드 수: {len(res)}건")
for r in res:
    print(f"no:{r.get('no')} / 브랜드:{r.get('brand_name')} / 스타일:{r.get('style_code')}")
