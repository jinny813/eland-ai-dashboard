from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import sys
import pandas as pd
from io import BytesIO

from core.data_manager import DataManager
from database.gsheet_manager import GSheetManager
from config.brand_targets import get_tm

from fastapi.middleware.cors import CORSMiddleware
from core.data_loader import load_dashboard_data

# [v100.1] Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import time
import logging

logger = logging.getLogger(__name__)

# [v17.14] API 전역 캐시 정의 (600초 TTL)
_API_CACHE = {
    "data": None,
    "expire_at": 0
}

# 상품 이미지 in-memory 캐시 {brand|code: (img_url, timestamp)}
_IMG_CACHE: dict = {}
_IMG_CACHE_TTL = 3600 * 6  # 6시간


def _fetch_product_image(brand: str, code: str) -> str:
    """네이버 쇼핑 검색으로 상품 이미지 URL을 on-demand 크롤링."""
    import re, urllib.parse, urllib.request, gzip as _gzip

    clean_code = re.sub(r'[-\s]', '', code)
    norm_code = re.sub(r'[^A-Z0-9]', '', clean_code.upper())
    if not norm_code:
        return ''

    _HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'https://www.naver.com/',
    }

    def _get(url: str) -> str:
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=8) as r:
                raw = r.read()
                enc = r.headers.get('Content-Encoding', '')
                if enc == 'gzip':
                    raw = _gzip.decompress(raw)
                return raw.decode('utf-8', errors='ignore')
        except Exception:
            return ''

    def _find_image(html: str) -> str:
        if not html:
            return ''
        # 방법 1: productName 매칭 후 근접 imageUrl 추출
        for m in re.finditer(r'"productName"\s*:\s*"([^"]*)"', html):
            raw_name = m.group(1)
            if norm_code not in re.sub(r'[^A-Z0-9]', '', raw_name.upper()):
                continue
            # 매칭된 productName 이후 3000자 안에서 이미지 키 탐색
            window = html[m.start(): m.start() + 3000]
            for key in ('imageUrl', 'thumbnailUrl', 'image', 'thumbnail', 'imgUrl'):
                img_m = re.search(r'"' + key + r'"\s*:\s*"(https?://[^"\\]+)"', window)
                if img_m:
                    return img_m.group(1).replace('\\/', '/')
        # 방법 2: 네이버 쇼핑 이미지 CDN URL 직접 추출
        m2 = re.search(r'https://shopping-phinf\.pstatic\.net/[^\s"\'<>&\\]+', html)
        if m2:
            return m2.group(0)
        # 방법 3: 일반 pstatic.net 이미지
        m3 = re.search(r'https://[a-z0-9.-]+\.pstatic\.net/[^\s"\'<>&\\]+', html)
        if m3:
            return m3.group(0)
        return ''

    queries = [f"{brand} {clean_code}".strip() if brand else clean_code, clean_code]
    seen: set = set()
    for q in queries:
        if q in seen:
            continue
        seen.add(q)
        enc = urllib.parse.quote(q)
        # 네이버 쇼핑 검색
        img = _find_image(_get(f"https://search.naver.com/search.naver?where=shop&query={enc}"))
        if img:
            return img
        # 네이버 통합 검색 (쇼핑 카드 포함)
        img = _find_image(_get(f"https://search.naver.com/search.naver?query={enc}"))
        if img:
            return img
    return ''

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/product-image")
async def get_product_image(brand: str = "", code: str = ""):
    """버튼 클릭 시 on-demand로 네이버에서 상품 이미지 URL을 크롤링해 반환."""
    if not code:
        return JSONResponse({"image_url": "", "ok": False})
    try:
        from core.html_generator import _crawl_naver_shopping_title, _NAME_SEARCH_CACHE, _NAME_SEARCH_TTL
        import time as _t

        # 세션 캐시에 이미지가 이미 있으면 즉시 반환
        cached = _NAME_SEARCH_CACHE.get(code)
        if cached is not None and len(cached) == 3:
            _, img, ts = cached
            if _t.time() - ts < _NAME_SEARCH_TTL and img:
                return JSONResponse({"image_url": img, "ok": True})

        # 브랜드+품번으로 크롤링 시도
        _, image_url = _crawl_naver_shopping_title(brand, code)
        # 결과 없으면 품번만으로 재시도
        if not image_url and brand:
            _, image_url = _crawl_naver_shopping_title('', code)

        return JSONResponse({"image_url": image_url, "ok": bool(image_url)})
    except Exception:
        return JSONResponse({"image_url": "", "ok": False})


@app.get("/api/dashboard")
async def get_dashboard():
    global _API_CACHE
    now = time.time()
    if _API_CACHE["data"] is not None and _API_CACHE["expire_at"] > now:
        return _API_CACHE["data"]
        
    try:
        mgr = GSheetManager(sheet_name="Records")
        sheet = mgr.spreadsheet.worksheet("Records")
        
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        try:
            raw_recs = await asyncio.wait_for(
                loop.run_in_executor(None, sheet.get_all_records),
                timeout=8.0
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Google Sheets read operation timed out after 8 seconds due to large data rows (320k+)")
            
        if not raw_recs:
            return JSONResponse(status_code=500, content={"error": "Records sheet is empty"})
            
        from core.data_loader import preprocess_raw_records
        cleaned_df, brand_zoning_map, sorted_months = preprocess_raw_records(mgr, raw_recs)
        
        if not sorted_months:
            return JSONResponse(status_code=500, content={"error": "No available months found in data"})
            
        all_data = {}
        for m in sorted_months:
            res = load_dashboard_data(
                mgr=mgr,
                selected_month=m,
                _preprocessed=(cleaned_df, brand_zoning_map, sorted_months)
            )
            if res and "error" not in res:
                all_data[m] = res
                
        if not all_data:
            return JSONResponse(status_code=500, content={"error": "Failed to build dashboard data for any month"})
            
        _API_CACHE["data"] = all_data
        _API_CACHE["expire_at"] = now + 600
        return all_data
    except Exception as e:
        import traceback
        logger.warning(f"API Dashboard GSheet load failed: {e} — Attempting fallback to local dashboard_backup.json")
        import json
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(os.path.dirname(curr_dir), "data", "dashboard_backup.json"),
            os.path.join(os.path.dirname(os.path.dirname(curr_dir)), "data", "dashboard_backup.json"),
            os.path.join(curr_dir, "data", "dashboard_backup.json"),
            os.path.join("data", "dashboard_backup.json"),
        ]
        backup_path = None
        for cand in candidates:
            if os.path.exists(cand):
                backup_path = cand
                break
        
        if backup_path and os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                if backup_data:
                    logger.info(f"✅ [API Fallback] Local dashboard backup loaded successfully from {backup_path}!")
                    _API_CACHE["data"] = backup_data
                    _API_CACHE["expire_at"] = time.time() + 600
                    return backup_data
            except Exception as fe:
                logger.error(f"[API Fallback] Failed to load local backup file: {fe}")
        
        return JSONResponse(status_code=500, content={"error": f"GSheet load failed ({str(e)}) and fallback failed.", "traceback": traceback.format_exc()})

import io
from typing import Optional

@app.post("/api/upload")
async def upload_data(
    store_name: str = Form(...),
    category_group: str = Form(...),
    brand_raw: str = Form(..., alias="brand_name"),  # "로엠|정상" 형태 수신
    data_month: str = Form(...),
    inv_file: Optional[UploadFile] = File(None),
    sales_file: Optional[UploadFile] = File(None),
    inv_text: Optional[str] = Form(None),
    sales_text: Optional[str] = Form(None)
):
    try:
        # 브랜드명과 매장유형 분리
        if "|" in brand_raw:
            brand_name, store_type = brand_raw.split("|")
        else:
            brand_name, store_type = brand_raw, "상설"

        # 1. 재고 데이터 처리
        if inv_file and inv_file.filename:
            inv_data = BytesIO(await inv_file.read())
            inv_data.name = inv_file.filename
        elif inv_text and inv_text.strip():
            inv_data = pd.read_csv(io.StringIO(inv_text), sep='\t')
        else:
            return JSONResponse(status_code=400, content={"error": "재고 데이터(파일 또는 텍스트)가 누락되었습니다."})
        
        # 2. 판매 데이터 처리
        sales_data = None
        if sales_file and sales_file.filename:
            sales_content = await sales_file.read()
            if sales_content:
                sales_data = BytesIO(sales_content)
                sales_data.name = sales_file.filename
        elif sales_text and sales_text.strip():
            sales_data = pd.read_csv(io.StringIO(sales_text), sep='\t')
        
        dm = DataManager()
        # DataManager.process_and_merge가 sales_data=None을 처리할 수 있어야 함
        final_df = dm.process_and_merge(brand_name, store_name, category_group, store_type, data_month, inv_data, sales_data)
        
        if final_df is None or final_df.empty:
            return JSONResponse(status_code=400, content={"error": "병합된 엑셀 데이터가 없습니다. 양식이 맞는지 확인해주세요."})
            
        mgr = GSheetManager(sheet_name="Records")
        is_saved = mgr.overwrite_record(final_df, store_name, brand_name, data_month)
        
        if is_saved:
            # 캐시 무효화 (업로드 후 즉시 대시보드 반영)
            _API_CACHE["data"] = None
            _API_CACHE["expire_at"] = 0
            return {"status": "success", "message": "성공적으로 업로드 및 병합되었습니다.", "rows": len(final_df)}
        else:
            return JSONResponse(status_code=500, content={"error": f"DB 저장 중 오류가 발생했습니다. ({mgr.error_msg})"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"서버 오류: {str(e)}"})

from pydantic import BaseModel
from typing import Dict, Any
from core.ai_agent import AIAgent

class DiagnoseRequest(BaseModel):
    brand_name: str
    indicator_id: str
    scores: Dict[str, Any]
    data_summary: Dict[str, Any]
    bp_summary: Dict[str, Any] = {}

@app.post("/api/diagnose")
async def diagnose(req: DiagnoseRequest):
    try:
        agent = AIAgent()
        result = agent.generate_report(req.brand_name, req.scores, req.data_summary, req.bp_summary, req.indicator_id)
        return {"status": "success", "result": result}
    except Exception as e:
        # [v100.1] repr()를 활용하여 인코딩 문제를 방지하며 상세 에러 내용 반환
        return JSONResponse(status_code=500, content={"error": f"진단 도중 예외 발생: {repr(e)}"})

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ui', 'dashboard_template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    return html

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
