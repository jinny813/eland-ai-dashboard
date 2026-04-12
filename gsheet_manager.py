import gspread
from gspread_formatting import cellFormat, color, textFormat, format_cell_range, set_frozen
import pandas as pd
from datetime import datetime
import os
import json

class GSheetManager:
    def __init__(self, credentials_filename: str = "credentials.json", sheet_name: str = "AI_Assortment_DB"):
        self.scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.abs_path = os.path.join(project_root, credentials_filename)
        
        self.client_email = "알 수 없음 (파일 없음)"
        self.error_msg = ""
        
        if os.path.exists(self.abs_path):
            try:
                with open(self.abs_path, 'r', encoding='utf-8') as f:
                    key_data = json.load(f)
                    self.client_email = key_data.get("client_email", "이메일 정보 없음")
            except Exception:
                pass

        try:
            self.client = gspread.service_account(filename=self.abs_path)
            self.spreadsheet = self.client.open(sheet_name)
            self.is_connected = True
        except Exception as e:
            self.error_msg = str(e)
            self.is_connected = False
            self.client = None
            self.spreadsheet = None

    def _get_target_cols(self):
        # [v65.0] 22개 마스터 컬럼 규격 정의 (DataManager와 100% 동기화)
        # 이 순서는 절대적이며, 시트의 1행 헤더와 100% 일치해야 함
        return [
            "no", "year", "season_code", "style_code", "style_name", "item_code", "item_name", "price_type",
            "stock_qty", "stock_amt", "sales_qty", "sales_amt", "normal_price", "sales_date",
            "brand_name", "store_name", "category_group", "store_type", "data_month", 
            "freshness_type", "discount_rate", "inv_uid"
        ]

    def _apply_master_format(self, sheet):
        """1행 마스터 헤더 보호 및 양식 강제 고정 (A1:V1)"""
        if not self.is_connected: return
        try:
            fmt = cellFormat(backgroundColor=color(0.9, 0.9, 0.9), textFormat=textFormat(bold=True))
            format_cell_range(sheet, 'A1:V1', fmt)
            set_frozen(sheet, rows=1)
        except Exception as e:
            print(f"Format Apply Error: {e}")

    def check_existing_data(self, store_name: str, category_group: str, brand_name: str, data_month: str) -> bool:
        if not self.is_connected: return False
        try:
            sheet = self.spreadsheet.worksheet("Records")
            records = sheet.get_all_records()
            for r in records:
                if str(r.get('store_name', '')).strip() == store_name and \
                   str(r.get('brand_name', '')).strip() == brand_name and \
                   str(r.get('data_month', '')).strip() == data_month:
                    return True
            return False
        except Exception:
            return False

    def overwrite_record(self, upload_df: pd.DataFrame, store_name: str, brand_name: str, data_month: str) -> bool:
        """[Hard Reset 강화 버전] 규격 불일치 시 무조건 초기화 후 재작성"""
        if not self.is_connected or upload_df.empty:
            return False
            
        try:
            sheet = self.spreadsheet.worksheet("Records")
            # 모든 값을 가져와서 헤더와 데이터 분리
            all_values = sheet.get_all_values()
            target_cols = self._get_target_cols()
            
            # 1. 헤더 동기화 로직 (Hard Reset)
            # - 시트가 비어있거나, 헤더 내용이 단 하나라도 다르면 전체 초기화
            should_reset = False
            if not all_values or not all_values[0]:
                should_reset = True
            else:
                current_headers = [str(h).strip() for h in all_values[0]]
                # 22개 컬럼이 정확히 일치하는지 내용 검증
                if current_headers != target_cols:
                    print(f"[v65.0] 규격 불일치 감지. 시트 초기화 진행 ({len(current_headers)} vs {len(target_cols)})")
                    should_reset = True
            
            if should_reset:
                sheet.clear()
                # 헤더 강제 이입
                try: sheet.update([target_cols], 'A1')
                except: sheet.update('A1', [target_cols])
                self._apply_master_format(sheet)
                # 데이터가 모두 날아갔으므로 all_values 초기화
                all_values = [target_cols]

            headers = all_values[0]
            data_rows = all_values[1:]
            
            # 컬럼 인덱스 안전 추출
            try:
                sn_idx = headers.index('store_name')
                bn_idx = headers.index('brand_name')
                dm_idx = headers.index('data_month')
                no_idx = headers.index('no')
            except ValueError:
                # 인덱스 추출 실패 시 로직 중단 후 재진입 유도 (안전장치)
                sheet.update([target_cols], 'A1')
                return self.append_record(upload_df)

            # 2. 유지할 데이터 선별
            preserved_rows = []
            max_no = 0
            
            for r in data_rows:
                r_pad = r + [''] * (max(len(headers), len(target_cols)) - len(r))
                cur_sn = str(r_pad[sn_idx]).strip()
                cur_bn = str(r_pad[bn_idx]).strip()
                cur_dm = str(r_pad[dm_idx]).strip()
                
                # 덮어쓰기 대상이 아닌 행만 유지
                if not (cur_sn == store_name and cur_bn == brand_name and cur_dm == data_month):
                    # 유지되는 행도 22열 최신 규격에 맞춰서 자름
                    r_clean = r + [''] * (len(target_cols) - len(r))
                    preserved_rows.append(r_clean[:len(target_cols)])
                    
                    try:
                        cur_no = int(r_pad[no_idx])
                        if cur_no > max_no: max_no = cur_no
                    except: pass

            old_total_count = len(data_rows)
            
            # 3. 신규 데이터 준비 (reindex를 통해 컬럼 순서 절대 고정)
            df = upload_df.copy()
            df = df.reindex(columns=target_cols, fill_value="")
            df = df.fillna("")
            df['no'] = range(max_no + 1, max_no + 1 + len(df))
            
            new_rows = df.values.tolist()
            final_payload = preserved_rows + new_rows
            
            # 4. 시트 덮어쓰기 (A2부터)
            if final_payload:
                try: sheet.update(final_payload, 'A2')
                except: sheet.update('A2', final_payload)
            
            # 5. 잔여물 청소 (이전 데이터가 더 많았을 경우 대응)
            if len(final_payload) < old_total_count:
                residue_count = old_total_count - len(final_payload)
                empty_block = [[''] * len(target_cols)] * residue_count
                start_row = 2 + len(final_payload)
                sheet.update(empty_block, f'A{start_row}')
                
            return True
            
        except Exception as e:
            print(f"Hard Reset Upsert Error: {e}")
            return False

    def append_record(self, upload_df: pd.DataFrame) -> bool:
        """기존 데이터 하단에 추가 (규격 검증 포함)"""
        if not self.is_connected or upload_df.empty:
            return False

        try:
            sheet = self.spreadsheet.worksheet("Records")
            all_values = sheet.get_all_values()
            target_cols = self._get_target_cols()
            
            # 헤더 불일치 시 무조건 초기화
            if not all_values or not all_values[0] or [str(h).strip() for h in all_values[0]] != target_cols:
                sheet.clear()
                try: sheet.update([target_cols], 'A1')
                except: sheet.update('A1', [target_cols])
                self._apply_master_format(sheet)
                all_values = [target_cols]

            headers = all_values[0]
            data_rows = all_values[1:]
            
            max_no = 0
            try:
                no_idx = headers.index('no')
                for r in data_rows:
                    if len(r) > no_idx:
                        try:
                            val = int(r[no_idx])
                            if val > max_no: max_no = val
                        except: pass
            except: pass

            df = upload_df.copy()
            df = df.reindex(columns=target_cols, fill_value="")
            df = df.fillna("")
            df['no'] = range(max_no + 1, max_no + 1 + len(df))
            
            sheet.append_rows(df.values.tolist())
            return True

        except Exception as e:
            print(f"Hard Reset Append Error: {e}")
            return False