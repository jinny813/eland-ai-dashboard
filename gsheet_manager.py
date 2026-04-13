import pandas as pd
import requests
import json
import logging

logger = logging.getLogger(__name__)

class GSheetManager:
    """
    [v80.2] Google Apps Script (GAS) 기반 데이터 매니저
    - 기존 gspread(Direct API) 방식에서 GAS Web App 호출 방식으로 전환
    - 속도 향상 및 인증 절차 간소화 (credentials.json 불필요)
    """
    def __init__(self, credentials_filename: str = None, sheet_name: str = "AI_Assortment_DB"):
        # 서비스 계정 대신 GAS Deployment ID 사용
        self.gas_id = "AKfycbz4gMtvIik1yzCEKU-je0bWVUXhYvYp9qpWaSunpdUiePAJmlmkWtxmtigP-w5CgTrEEg"
        self.gas_url = f"https://script.google.com/macros/s/{self.gas_id}/exec"
        self.sheet_master_name = sheet_name
        self.is_connected = True
        self.error_msg = ""
        self.client_email = "GAS_WEB_APP" # 호환용 더미 데이터
        
        # 하이브리드 호환성을 위해 Mock 객체 구성
        self.spreadsheet = GASSpreadsheetMock(self)

    def _get_target_cols(self):
        return [
            "no", "year", "season_code", "style_code", "style_name", "item_code", "item_name", "price_type",
            "stock_qty", "stock_amt", "sales_qty", "sales_amt", "normal_price", "sales_date",
            "brand_name", "store_name", "category_group", "store_type", "data_month", 
            "freshness_type", "discount_rate", "inv_uid"
        ]

    def call_gas(self, action, payload=None):
        """GAS 웹 앱에 요청을 보냅니다 (GET/POST)"""
        try:
            if payload:
                # 데이터가 있으면 POST (JSON)
                response = requests.post(self.gas_url, json={
                    "action": action,
                    "sheetName": self.sheet_master_name,
                    "data": payload
                }, timeout=120)
            else:
                # 데이터가 없으면 GET
                response = requests.get(self.gas_url, params={
                    "action": action,
                    "sheetName": self.sheet_master_name
                }, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list):
                    return result
                elif isinstance(result, dict):
                    if result.get("status") == "success":
                        return result.get("data")
                    elif "exists" in result: # check_exists 대응
                        return result 
                    return result
                return result
            else:
                self.error_msg = f"HTTP {response.status_code}"
                logger.error(f"GAS HTTP Error: {response.status_code}")
                return None
        except Exception as e:
            self.error_msg = str(e)
            logger.error(f"GAS Connection Error: {e}")
            return None

    def check_existing_data(self, store_name: str, category_group: str, brand_name: str, data_month: str) -> bool:
        """GAS를 통해 기존 데이터 존재 여부 확인"""
        params = {
            "action": "check_exists",
            "store_name": store_name,
            "brand_name": brand_name,
            "data_month": data_month,
            "category_group": category_group
        }
        res = self.call_gas("check_exists", params)
        if isinstance(res, dict) and "exists" in res:
            return res["exists"]
        return False

    def overwrite_record(self, upload_df: pd.DataFrame, store_name: str, brand_name: str, data_month: str) -> bool:
        """[Hard Reset] 특정 조건의 데이터를 삭제하고 신규 데이터로 교체 (GAS 방식)"""
        if upload_df.empty: return False
        
        target_cols = self._get_target_cols()
        df = upload_df.copy()
        df = df.reindex(columns=target_cols, fill_value="")
        df = df.fillna("")
        
        payload = {
            "store_name": store_name,
            "brand_name": brand_name,
            "data_month": data_month,
            "rows": df.values.tolist()
        }
        
        res = self.call_gas("upsert", payload)
        return res is not None

    def append_record(self, upload_df: pd.DataFrame) -> bool:
        """데이터 단순 추가 (GAS 방식)"""
        if upload_df.empty: return False
        
        target_cols = self._get_target_cols()
        df = upload_df.copy()
        df = df.reindex(columns=target_cols, fill_value="")
        df = df.fillna("")
        
        payload = {
            "rows": df.values.tolist()
        }
        
        res = self.call_gas("append", payload)
        return res is not None

# ── Mock Classes for backward compatibility ──

class GASSpreadsheetMock:
    def __init__(self, manager):
        self.manager = manager
    def worksheet(self, name):
        return GASWorksheetMock(self.manager, name)

class GASWorksheetMock:
    def __init__(self, manager, name):
        self.manager = manager
        self.name = name
    def get_all_records(self):
        """gspread.get_all_records() 호환성 유지"""
        return self.manager.call_gas("read_all") or []
    
    def get_all_values(self):
        """gspread.get_all_values() 호환성 유지 (헤더 포함)"""
        return self.manager.call_gas("read_raw") or []

    def clear(self):
        pass

    def update(self, values, range_val=None):
        pass

    def append_rows(self, rows):
        pass