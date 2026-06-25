import base64
import json
import logging
import pandas as pd
import requests
import time
import random
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

class GSheetManager:
    """
    [v80.2] Google Apps Script (GAS) 기반 데이터 매니저
    - 기존 gspread(Direct API) 방식에서 GAS Web App 호출 방식으로 전환
    - 속도 향상 및 인증 절차 간소화 (credentials.json 불필요)
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
        self.session.verify = False  # SSL 인증 오류 우회
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_target_cols(self):
        return [
            "no", "year", "season_code", "style_code", "style_name", "item_code", "item_name", "price_type",
            "stock_qty", "stock_amt", "sales_qty", "sales_amt", "normal_price", "sales_date",
            "brand_name", "store_name", "category_group", "store_type", "data_month", 
            "freshness_type", "discount_rate", "inv_uid",
            "tag_price", "predicted_online_price", "predicted_discount_rate"
        ]

    def _parse_response(self, response):
        """GAS 응답 공통 파싱"""
        response.encoding = 'utf-8'
        raw_text = response.text.strip()

        if response.status_code != 200:
            self.error_msg = f"HTTP {response.status_code}: {raw_text[:200]}"
            logger.error(f"[GAS] HTTP 오류 {response.status_code}: {raw_text[:200]}")
            return None
        if not raw_text:
            self.error_msg = "GAS 응답이 비어 있습니다."
            logger.error("[GAS] 응답이 비어 있습니다.")
            return None
        try:
            result = response.json()
        except Exception as je:
            self.error_msg = f"JSON 파싱 실패 (응답: {raw_text[:200]})"
            logger.error(f"[GAS] JSON parse error: {je} | body: {raw_text[:300]}")
            return None

        if isinstance(result, dict):
            if result.get("status") == "error":
                self.error_msg = result.get("message") or "GAS 오류 (message 없음)"
                logger.warning(f"[GAS] error: {self.error_msg}")
                return None
            data = result.get("data")
            if data is not None:
                return data
            return result
        return result

    def _get(self, params: dict, timeout: int = 120):
        """데이터 GET 요청"""
        try:
            if "sheetName" not in params:
                params["sheetName"] = self.sheet_master_name
            response = self.session.get(self.gas_url, params=params,
                                   timeout=(15, timeout),
                                   allow_redirects=True)
            return self._parse_response(response)
        except Exception as e:
            self.error_msg = str(e)
            logger.error(f"[GAS] GET 예외 action={params.get('action')}: {e}")
            return None

    def _post(self, form_data: dict, timeout: int = 180):
        """대용량 데이터용 POST 요청 (v7.0 Fresh Connection)
        GAS 동작: POST -> doPost 실행 -> 302 리다이렉트 -> GET 추적"""
        try:
            logger.info(f"[GAS] POST request start (action={form_data.get('action')})")
            form_data["sheetName"] = self.sheet_master_name
            headers = {'Connection': 'close', 'User-Agent': 'AI-Assortment-Agent'}
            
            # [v7.0] 1단계: POST 전송 (새로운 연결)
            r1 = requests.post(self.gas_url, data=form_data,
                               headers=headers, timeout=(5, timeout), 
                               allow_redirects=False, verify=False)
            logger.info(f"[GAS] POST status={r1.status_code}")

            if r1.status_code in (301, 302, 303, 307, 308):
                redirect_url = r1.headers.get("Location", self.gas_url)
                logger.info(f"[GAS] redirect -> {redirect_url}")
                # 2단계: 리다이렉트를 GET으로 추적 (새로운 연결)
                r2 = requests.get(redirect_url, headers=headers, 
                                  timeout=(5, timeout), allow_redirects=True, verify=False)
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
        chunk_size = 100  # [속도 최적화] 5 -> 100행으로 상향 (500행 기준 5회 통신)
        total_rows = len(payload_list)
        total_chunks = (total_rows + chunk_size - 1) // chunk_size
        
        logger.info(f"[GSheet] 고속 전송 모드: 총 {total_rows}행 업로드 ({total_chunks}회 분할, 크기={chunk_size})")
        
        # [v6.0] 일회용 연결을 위한 표준 헤더
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
            # [v6.0] 매 요청마다 새로운 연결 수립
            for attempt in range(1, 6):
                try:
                    # 세션 재사용 없이 직접 post 호출 (Connect: 10s, Read: 180s)
                    resp = requests.post(
                        self.gas_url, 
                        data=data, 
                        headers=headers,
                        timeout=(10, 180),
                        allow_redirects=True,
                        verify=False
                    )
                    
                    # [v100.1] 대소문자 무시 및 정식 응답 파싱 적용
                    parsed = self._parse_response(resp)
                    if parsed is not None:
                        success = True
                        logger.info(f"[GSheet] 전송 성공: {end_row}/{total_rows} 행 완료")
                        break
                    else:
                        logger.warning(f"[GSheet] 응답 지연 또는 파싱 실패(시도 {attempt}/5): {resp.status_code}")
                except Exception as e:
                    logger.error(f"[GSheet] 통신 오류: {e}. (시도 {attempt}/5)")
                
                if attempt < 5:
                    # [v8.5] 신속한 재시도 (1초 고정)
                    time.sleep(1.0)
            
            if not success:
                # [v100.2] 구체적인 에러 메시지가 있다면 보존, 없다면 요약 메시지 생성
                detailed_err = self.error_msg if self.error_msg else "응답 없음 또는 알 수 없는 오류"
                err = f"{start_row}-{end_row}번 행 업로드 최종 실패 (사유: {detailed_err})"
                self.error_msg = err
                logger.error(f"[GSheet] {err}")
                return False
                
            # [v8.5] 요청 간 최소 지연 (0.5~1초)
            if end_row < total_rows:
                time.sleep(random.uniform(0.5, 1.0))
            
        return True

    def overwrite_record(self, upload_df: pd.DataFrame, store_name: str, brand_name: str, data_month: str) -> bool:
        """기존 데이터 삭제 후 GET 청크로 신규 삽입"""
        if upload_df.empty: return False

        target_cols = self._get_target_cols()
        df = upload_df.copy().reindex(columns=target_cols, fill_value="").fillna("")

        res = self._post({"action": "delete", "store_name": store_name,
                          "brand_name": brand_name, "data_month": data_month})
        if res is None:
            return False

        # delete 후 남은 DB 기준 max_no 조회 → no 연번 재할당
        # delete 후 남은 DB 기준 max_no 조회 → no 연번 재할당
        max_no = self._get_max_no()
        df['no'] = range(max_no + 1, max_no + 1 + len(df))

        return self._append_chunks(brand_name, df.values.tolist())

    def append_record(self, upload_df: pd.DataFrame) -> bool:
        """GET 청크로 데이터 추가"""
        if upload_df.empty: return False

        target_cols = self._get_target_cols()
        df = upload_df.copy().reindex(columns=target_cols, fill_value="").fillna("")
        
        # DataFrame에서 실제 브랜드명 안전하게 인출
        brand_name = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns and len(df) > 0 else "Generic"
        return self._append_chunks(brand_name, df.values.tolist())


    # ── Scored_Cache 탭 관련 메서드 ──────────────────────────────────────────

    def clear_sheet(self, sheet_name: str) -> bool:
        """지정 탭 초기화 (없으면 생성)"""
        result = self._get({"action": "clear_sheet", "sheetName": sheet_name})
        return result is not None

    def write_scored_cache(self, json_str: str, timestamp: str, version: str = "") -> bool:
        """직렬화된 대시보드 JSON을 gzip 압축 후 Scored_Cache 탭에 청크 단위로 저장 (1회 POST)"""
        import gzip as _gz
        import time as _time

        try:
            # 1. 압축 → base64
            compressed = _gz.compress(json_str.encode("utf-8"), compresslevel=6)
            b64_str = base64.b64encode(compressed).decode("ascii")

            # 2. 40,000자 청크 분할
            chunk_size = 40000
            chunks = [b64_str[i:i + chunk_size] for i in range(0, len(b64_str), chunk_size)]
            total_chunks = len(chunks)

            logger.info(
                f"[ScoredCache] 저장 시작: {total_chunks}청크 / "
                f"원본 {len(json_str) // 1024}KB → 압축 {len(b64_str) // 1024}KB"
            )

            # 3. 기존 시트 초기화 (없으면 생성)
            self.clear_sheet("Scored_Cache")

            # 4. 헤더 row + 데이터 rows 구성
            all_rows = (
                [[timestamp, version, str(total_chunks), "HEADER"]]
                + [[str(i), chunk, "", ""] for i, chunk in enumerate(chunks)]
            )

            # 5. append_bulk_b64로 한 번에 전송 (기존 GAS 액션 재사용)
            rows_json = json.dumps(all_rows, ensure_ascii=True)
            b64_payload = base64.b64encode(rows_json.encode("utf-8")).decode("utf-8")

            headers = {"Connection": "close", "User-Agent": "AI-Assortment-Agent"}
            for attempt in range(1, 4):
                try:
                    resp = requests.post(
                        self.gas_url,
                        data={
                            "action": "append_bulk_b64",
                            "sheetName": "Scored_Cache",
                            "brand_name": "cache",
                            "payload_b64": b64_payload,
                        },
                        headers=headers,
                        timeout=(10, 300),
                        allow_redirects=True,
                        verify=False,
                    )
                    if self._parse_response(resp) is not None:
                        logger.info(f"[ScoredCache] 저장 완료: {timestamp}")
                        return True
                except Exception as e:
                    logger.error(f"[ScoredCache] 저장 시도 {attempt}/3 실패: {e}")
                if attempt < 3:
                    _time.sleep(2)

            logger.error("[ScoredCache] 저장 최종 실패")
            return False

        except Exception as e:
            logger.error(f"[ScoredCache] 저장 전처리 실패: {e}")
            return False

    def read_scored_cache(self, expected_version: str = ""):
        """Scored_Cache 탭에서 gzip 복원 후 JSON 문자열 반환 → (timestamp, json_str) or (None, None)
        expected_version이 지정되면 저장된 버전과 불일치 시 None을 반환해 구버전 캐시를 거부한다."""
        import gzip as _gz

        res = self._get({"action": "read_raw", "sheetName": "Scored_Cache"}, timeout=60)

        # [Fallback 방어 로직] GAS에 read_raw가 배포되지 않은 경우 read_all로 우회 (L2 하이브리드 보완)
        if res is None and self.error_msg and "Unknown GET action: read_raw" in self.error_msg:
            logger.warning("[ScoredCache] read_raw 미지원 서버. read_all 우회 로드를 시도합니다.")
            fallback_res = self._get({"action": "read_all", "sheetName": "Scored_Cache"}, timeout=60)

            if isinstance(fallback_res, list) and len(fallback_res) > 0 and isinstance(fallback_res[0], dict):
                headers = list(fallback_res[0].keys())
                res = [headers] + [[row.get(h, "") for h in headers] for row in fallback_res]

        if not res or not isinstance(res, list) or len(res) < 2:
            return None, None

        try:
            header = res[0]
            if len(header) < 4 or str(header[3]).strip() != "HEADER":
                logger.warning("[ScoredCache] 헤더 형식 불일치 — 캐시 없음으로 처리")
                return None, None

            # 버전 불일치 시 구버전 캐시 거부
            stored_version = str(header[1]).strip() if len(header) > 1 else ""
            if expected_version and stored_version != expected_version:
                logger.warning(f"[ScoredCache] 버전 불일치 — 무시: 저장={stored_version!r}, 현재={expected_version!r}")
                return None, None

            timestamp = str(header[0])
            total_chunks = int(float(str(header[2])))

            chunks = {}
            for row in res[1:]:
                if len(row) >= 2 and row[1]:
                    try:
                        chunks[int(float(str(row[0])))] = str(row[1])
                    except (ValueError, TypeError):
                        continue

            if len(chunks) != total_chunks:
                logger.warning(f"[ScoredCache] 청크 불일치: 보유 {len(chunks)}/{total_chunks}")
                return None, None

            b64_full = "".join(chunks[i] for i in range(total_chunks))
            json_str = _gz.decompress(base64.b64decode(b64_full)).decode("utf-8")
            logger.info(f"[ScoredCache] 로드 완료: ts={timestamp}, {len(json_str) // 1024}KB")
            return timestamp, json_str

        except Exception as e:
            logger.error(f"[ScoredCache] 로드 실패: {e}")
            return None, None

    # ─────────────────────────────────────────────────────────────────────────

    def load_office_master(self) -> pd.DataFrame:
        """구글 시트의 'officemaster' 탭 데이터 로드"""
        params = {"action": "read_all", "sheetName": "officemaster"}
        res = self._get(params)
        if not res or not isinstance(res, list) or len(res) == 0:
            logger.warning("[GSheet] 'officemaster' 데이터를 읽지 못했거나 비어있습니다. 기본값을 로드합니다.")
            return pd.DataFrame(
                [["8242", "신구로점", "수도권"], ["8227", "강서점", "수도권"]],
                columns=["지점코드", "지점명", "지역"]
            )
        return pd.DataFrame(res)

    def load_store_master(self) -> pd.DataFrame:
        """data/storemaster_raw.txt 에서 매장 마스터 로드"""
        import os
        base_dir = os.path.dirname(os.path.dirname(__file__))
        raw_path = os.path.join(base_dir, "data", "storemaster_raw.txt")
        if not os.path.exists(raw_path):
            logger.warning("[GSheet] data/storemaster_raw.txt 없음 — 빈 DataFrame 반환")
            return pd.DataFrame()
        for enc in ('utf-8', 'cp949', 'utf-8-sig', 'euc-kr', 'utf-16'):
            try:
                with open(raw_path, 'r', encoding=enc, errors='strict') as f:
                    head = f.read(2048)
                delim = ',' if ',' in head and '\t' not in head else '\t'
                with open(raw_path, 'r', encoding=enc, errors='ignore') as f_in:
                    df = pd.read_csv(f_in, sep=delim, header=0,
                                     dtype=str, on_bad_lines='skip')
                
                import re
                new_cols = []
                for col in df.columns:
                    c = str(col).strip()
                    m1 = re.match(r'^(\d{2})년\s*(\d{1,2})월\s*매출$', c)
                    if m1:
                        new_cols.append(f"{m1.group(1)}_{int(m1.group(2)):02d}")
                        continue
                    m2 = re.match(r'^(\d{2})년\s*(\d{1,2})월\s*목표$', c)
                    if m2:
                        new_cols.append(f"목표_{int(m2.group(2)):02d}")
                        continue
                    new_cols.append(c)
                df.columns = new_cols
                
                logger.warning(f"[GSheet] storemaster_raw.txt 로드 완료: {len(df)}행 ({enc})")
                return df
            except Exception:
                continue
        logger.error("[GSheet] storemaster_raw.txt 읽기 실패 — 빈 DataFrame 반환")
        return pd.DataFrame()


    def load_brand_master(self) -> pd.DataFrame:
        """구글 시트의 'brandmaster' 탭 데이터 로드"""
        params = {"action": "read_all", "sheetName": "brandmaster"}
        res = self._get(params)
        if not res or not isinstance(res, list) or len(res) == 0:
            logger.warning("[GSheet] 'brandmaster' 데이터를 읽지 못했거나 비어있습니다. 빈 마스터를 반환합니다.")
            return pd.DataFrame(columns=["브랜드코드", "브랜드명", "카테고리", "조닝", "회사"])
        return pd.DataFrame(res)


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
        """gspread.get_all_records() 호환성 유지 — GAS read_all 직접 사용"""
        sheet_name = self.manager.sheet_master_name
        logger.warning(f"[GSheet] read_all 요청 (sheetName={sheet_name})")
        result = self.manager._get({"action": "read_all", "sheetName": sheet_name}, timeout=180)
        if result is None:
            logger.error(f"[GSheet] read_all 실패: {self.manager.error_msg!r}")
            return []
        if isinstance(result, list):
            logger.warning(f"[GSheet] read_all 완료: {len(result)}행")
            return result
        logger.error(f"[GSheet] read_all 응답 형식 오류: {type(result).__name__} / {str(result)[:200]}")
        return []
    
    def get_all_values(self):
        """gspread.get_all_values() 호환성 유지 (헤더 포함, 페이징 데이터 기반 재구성)"""
        recs = self.get_all_records()
        if not recs: return []
        headers = list(recs[0].keys())
        values = [headers]
        for r in recs:
            values.append([r.get(h, "") for h in headers])
        return values

    def clear(self):
        pass

    def update(self, values, range_val=None):
        pass

    def append_rows(self, rows):
        pass