from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import pandas as pd
from io import BytesIO

from core.data_manager import DataManager
from database.gsheet_manager import GSheetManager
from config.brand_targets import get_tm

from fastapi.middleware.cors import CORSMiddleware
from core.data_loader import load_dashboard_data

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Extract logic from html_generator into a pure JSON endpoint
@app.get("/api/dashboard")
async def get_dashboard():
    data = load_dashboard_data()
    if "error" in data:
        return JSONResponse(status_code=500, content=data)
    return data

@app.post("/api/upload")
async def upload_data(
    store_name: str = Form(...),
    category_group: str = Form(...),
    brand_raw: str = Form(..., alias="brand_name"),  # "로엠|정상" 형태 수신
    data_month: str = Form(...),
    inv_file: UploadFile = File(...),
    sales_file: UploadFile = None  # 선택적 업로드 지원
):
    try:
        # 브랜드명과 매장유형 분리
        if "|" in brand_raw:
            brand_name, store_type = brand_raw.split("|")
        else:
            brand_name, store_type = brand_raw, "상설"

        inv_data = BytesIO(await inv_file.read())
        inv_data.name = inv_file.filename
        
        sales_data = None
        if sales_file:
            sales_content = await sales_file.read()
            if sales_content:
                sales_data = BytesIO(sales_content)
                sales_data.name = sales_file.filename
        
        dm = DataManager()
        # DataManager.process_and_merge가 sales_data=None을 처리할 수 있어야 함
        final_df = dm.process_and_merge(brand_name, store_name, category_group, store_type, data_month, inv_data, sales_data)
        
        if final_df is None or final_df.empty:
            return JSONResponse(status_code=400, content={"error": "병합된 엑셀 데이터가 없습니다. 양식이 맞는지 확인해주세요."})
            
        mgr = GSheetManager()
        is_saved = mgr.overwrite_record(final_df, store_name, brand_name, data_month)
        
        if is_saved:
            return {"status": "success", "message": "성공적으로 업로드 및 병합되었습니다.", "rows": len(final_df)}
        else:
            return JSONResponse(status_code=500, content={"error": "DB 저장 중 오류가 발생했습니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"서버 오류: {str(e)}"})

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ui', 'dashboard_template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    return html

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
