import sys
import os
import pandas as pd

# 프로젝트 루트를 경로에 추가하여 gsheet_manager 임포트 가능하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.gsheet_manager import GSheetManager

def migrate():
    print("=== 구글 시트 마이그레이션 시작 (v55.0) ===")
    mgr = GSheetManager()
    if not mgr.is_connected:
        print(f"Error: {mgr.error_msg}")
        return

    try:
        sheet = mgr.spreadsheet.worksheet("Records")
        all_values = sheet.get_all_values()
        if not all_values:
            print("시트에 데이터가 없습니다. 마이그레이션을 중단합니다.")
            return

        old_headers = all_values[0]
        new_headers = mgr._get_target_cols()

        if len(old_headers) == len(new_headers):
            print("이미 컬럼 수가 일치합니다. 마이그레이션이 필요하지 않거나 이미 완료되었습니다.")
            return

        print(f"컬럼 변경 감지: {len(old_headers)}열 -> {len(new_headers)}열")
        
        # 데이터 재배치 (기존 데이터 보존)
        data_rows = all_values[1:]
        new_data = []

        for row in data_rows:
            # 딕셔너리 형태로 변환하여 매핑 준비
            row_dict = {old_headers[i]: row[i] for i in range(len(row)) if i < len(old_headers)}
            
            # 새로운 스키마에 맞춰 새 행 생성 (없는 값은 빈 문자열)
            new_row = [row_dict.get(col, "") for col in new_headers]
            new_data.append(new_row)

        # 시트 업데이트
        print("시트 데이터 업데이트 중...")
        sheet.clear()
        
        # 헤더와 데이터 결합하여 한 번에 업데이트
        final_payload = [new_headers] + new_data
        
        try:
            sheet.update(final_payload, 'A1') # gspread v6+
        except:
            sheet.update('A1', final_payload) # gspread v5

        # 포맷팅 적용
        mgr._apply_master_format(sheet)
        
        print(f"마이그레이션 성공! 총 {len(new_data)}개의 행이 재정렬되었습니다.")
        print(f"새로운 컬럼: {new_headers}")

    except Exception as e:
        print(f"Migration Error: {e}")

if __name__ == "__main__":
    migrate()
