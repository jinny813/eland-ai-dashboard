import base64
import json
import logging
import pandas as pd
import requests
import time
import random
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

class GSheetManager:
    """
    [v100.3] Google Apps Script (GAS) 기반 데이터 매니저 (Functions Sync Version)
    - database/gsheet_manager.py와 동기화됨
    - 시트 이름 오류(AI_Assortment_DB) 해결을 위해 'Records'를 기본값으로 설정
    """
    def __init__(self, credentials_filename: str = None, sheet_name: str = "Records"):
        # 서비스 계정 대신 GAS Deployment ID 사용
        # [v82.0] 사용자가 제공한 최신 배포 ID 적용
        self.gas_id = "AKfycbxbO5tUGfAENxX24nyQELlfDwZondvv9xFkjdje9jrNm-NkJyj3USNT3Ji5IKZ6OYuSsQ"
        self.gas_url = f"https://script.google.com/macros/s/{self.gas_id}/exec"
        self.sheet_master_name = sheet_name
        self.is_connected = True
        self.error_msg = ""
        self.client_email = "GAS_WEB_APP" # 호환용 더미 데이터
        
        # 하이브리드 호환성을 위해 Mock 객체 구성
        self.spreadsheet = GASSpreadsheetMock(self)
        self._setup_session()

    def _setup_session(self):
        """네트워크 안정성을 위한 재시도 로직 설정"""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_target_cols(self):
        return [
            "no", "year", "season_code", "style_code", "style_name", "item_code", "item_name", "price_type",
            "stock_qty", "stock_amt", "sales_qty", "sales_amt", "normal_price", "sales_date",
            "brand_name", "store_name", "category_group", "store_type", "data_month", 
            "freshness_type", "discount_rate", "inv_uid"
        ]

    def _parse_response(self, response):
        """GAS 응답 공통 파싱"""
        raw_text = response.text.strip()
        logger.info(f"[GAS] status={response.status_code} preview={raw_text[:120]}")

        if response.status_code != 200:
            self.error_msg = f"HTTP {response.status_code}: {raw_text[:100]}"
            return None
        if not raw_text:
            self.error_msg = "GAS 응답이 비어 있습니다."
            return None
        try:
            result = response.json()
        except Exception as je:
            self.error_msg = f"JSON 파싱 실패 (응답: {raw_text[:100]})"
            logger.error(f"GAS JSON parse error: {je} | body: {raw_text[:300]}")
            return None

        if isinstance(result, dict):
            if result.get("status") == "error":
                self.error_msg = result.get("message", "GAS 오류")
                return None
            return result.get("data") or result
        return result

    def _get(self, params: dict, timeout: int = 180):
        """소량 데이터용 GET 요청 (v7.0 Fresh Connection)"""
        try:
            logger.info(f"[GAS] GET request start (action={params.get('action')})")
            params["sheetName"] = self.sheet_master_name
            headers = {'Connection': 'close', 'User-Agent': 'AI-Assortment-Agent'}
            
            # [v7.0] 세션 재사용 없이 직접 호출
            response = requests.get(self.gas_url, params=params,
                                   headers=headers, timeout=(5, timeout), 
                                   allow_redirects=True)
            return self._parse_response(response)
        except Exception as e:
            self.error_msg = str(e)
            logger.error(f"GAS GET Error: {e}")
            return None

    def _post(self, form_data: dict, timeout: int = 180):
        """대용량 데이터용 POST 요청 (v7.0 Fresh Connection)"""
        try:
            logger.info(f"[GAS] POST request start (action={form_data.get('action')})")
            form_data["sheetName"] = self.sheet_master_name
            headers = {'Connection': 'close', 'User-Agent': 'AI-Assortment-Agent'}
            
            # [v7.0] 1단계: POST 전송 (새로운 연결)
            r1 = requests.post(self.gas_url, data=form_data,
                               headers=headers, timeout=(5, timeout), 
                               allow_redirects=False)
            logger.info(f"[GAS] POST status={r1.status_code}")

            if r1.status_code in (301, 302, 303, 307, 308):
                redirect_url = r1.headers.get("Location", self.gas_url)
                logger.info(f"[GAS] redirect -> {redirect_url}")
                # 2단계: 리다이렉트를 GET으로 추적 (새로운 연결)
                r2 = requests.get(redirect_url, headers=headers, 
                                  timeout=(5, timeout), allow_redirects=True)
                return self._parse_response(r2)

            return self._parse_response(r1)
        except Exception as e:
            self.error_msg = f"네트워크 오류: {str(e)}"
            logger.error(f"GAS POST Error: {e}")
            return None

    def call_gas(self, action, payload=None):
        """하위 호환용 — read_all / check_exists 전용"""
        params = {"action": action}
        if payload and isinstance(payload, dict):
            params.update(payload)
        return self._get(params)

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

    def _get_max_no(self) -> int:
        """DB의 현재 최대 no 값 조회"""
        res = self._get({"action": "max_no"})
        if isinstance(res, dict) and "max_no" in res:
            try:
                return int(res["max_no"])
            except (ValueError, TypeError):
                self.error_msg = f"max_no 데이터 타입 오류: {res.get('max_no')}"
                return 0
        self.error_msg = f"max_no 조회 실패: {self.error_msg or '응답 데이터 부재'}"
        return 0

    def _append_chunks(self, brand_name: str, payload_list: list) -> bool:
        """데이터를 청크 단위로 나누어 GAS에 전송 (최종 고속 최적화 v8.5)"""
        chunk_size = 100  # [속도 최적화] 5 -> 100행으로 상향
        total_rows = len(payload_list)
        total_chunks = (total_rows + chunk_size - 1) // chunk_size
        
        logger.info(f"[GSheet] 고속 전송 모드: 총 {total_rows}행 업로드 ({total_chunks}회 분할, 크기={chunk_size})")
        
        headers = {
            'Connection': 'close',
            'User-Agent': 'Mozilla/5.0 (AI Assortment Agent) Python/requests',
            'Accept': 'application/json'
        }
        
        for i in range(0, total_rows, chunk_size):
            chunk = payload_list[i:i + chunk_size]
            current_chunk_idx = (i // chunk_size) + 1
            start_row = i + 1
            end_row = min(i + chunk_size, total_rows)
            
            chunk_json = json.dumps(chunk, ensure_ascii=False)
            b64_payload = base64.b64encode(chunk_json.encode('utf-8')).decode('utf-8')
            
            data = {
                'action': 'append_bulk_b64',
                'brand_name': brand_name,
                'sheetName': self.sheet_master_name,
                'payload_b64': b64_payload
            }
            
            success = False
            for attempt in range(1, 6):
                try:
                    resp = requests.post(
                        self.gas_url, 
                        data=data, 
                        headers=headers,
                        timeout=(10, 180),
                        allow_redirects=True
                    )
                    
                    parsed = self._parse_response(resp)
                    if parsed is not None:
                        success = True
                        logger.info(f"[GSheet] 전송 성공: {end_row}/{total_rows} 행 완료")
                        break
                except Exception as e:
                    logger.error(f"[GSheet] 통신 오류: {e}. (시도 {attempt}/5)")
                
                if attempt < 5:
                    # [v8.5] 신속한 재시도 (1초 고정)
                    time.sleep(1.0)
            
            if not success:
                detailed_err = self.error_msg if self.error_msg else "응답 없음 또는 알 수 없는 오류"
                err = f"{start_row}-{end_row}번 행 업로드 최종 실패 (사유: {detailed_err})"
                self.error_msg = err
                return False
                
            # [v8.5] 요청 간 최소 지연 (0.5~1초)
            if end_row < total_rows:
                time.sleep(random.uniform(0.5, 1.0))
            
        return True

    def overwrite_record(self, upload_df: pd.DataFrame, store_name: str, brand_name: str, data_month: str) -> bool:
        if upload_df.empty: return False

        target_cols = self._get_target_cols()
        df = upload_df.copy().reindex(columns=target_cols, fill_value="").fillna("")

        res = self._post({"action": "delete", "store_name": store_name,
                          "brand_name": brand_name, "data_month": data_month})
        if res is None:
            return False

        max_no = self._get_max_no()
        df['no'] = range(max_no + 1, max_no + 1 + len(df))

        return self._append_chunks(brand_name, df.values.tolist())

    def append_record(self, upload_df: pd.DataFrame) -> bool:
        if upload_df.empty: return False
        target_cols = self._get_target_cols()
        df = upload_df.copy().reindex(columns=target_cols, fill_value="").fillna("")
        brand_name = upload_df['brand_name'].iloc[0] if 'brand_name' in upload_df.columns else "Unknown"
        return self._append_chunks(brand_name, df.values.tolist())

# ── Mock Classes ──
class GASSpreadsheetMock:
    def __init__(self, manager): self.manager = manager
    def worksheet(self, name): return GASWorksheetMock(self.manager, name)

class GASWorksheetMock:
    def __init__(self, manager, name): self.manager = manager; self.name = name
    def get_all_records(self): return self.manager.call_gas("read_all") or []
    def get_all_values(self): return self.manager.call_gas("read_raw") or []
    def clear(self): pass
    def update(self, values, range_val=None): pass
    def append_rows(self, rows): pass