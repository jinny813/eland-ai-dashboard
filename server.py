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

# 루트 레벨에서 static 폴더 연결
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/dashboard")
async def get_dashboard():
    # GSheetManager가 루트의 credentials.json을 찾을 수 있도록 함
    data = load_dashboard_data()
    if "error" in data:
        return JSONResponse(status_code=500, content=data)
    return data

@app.post("/api/upload")
async def upload_data(
    store_name: str = Form(...),
    category_group: str = Form(...),
    brand_raw: str = Form(..., alias="brand_name"),
    data_month: str = Form(...),
    inv_file: UploadFile = File(...),
    sales_file: UploadFile = None
):
    try:
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
        final_df = dm.process_and_merge(brand_name, store_name, category_group, store_type, data_month, inv_data, sales_data)
        
        if final_df is None or final_df.empty:
            return JSONResponse(status_code=400, content={"error": "병합된 엑셀 데이터가 없습니다."})
            
        mgr = GSheetManager()
        is_saved = mgr.overwrite_record(final_df, store_name, brand_name, data_month)
        
        if is_saved:
            return {"status": "success", "message": "성공적으로 업로드되었습니다.", "rows": len(final_df)}
        else:
            return JSONResponse(status_code=500, content={"error": "DB 저장 실패"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"서버 오류: {str(e)}"})

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    # 루트 레벨에서 ui 폴더 내 템플릿 참조
    template_path = os.path.join(os.getcwd(), 'ui', 'dashboard_template.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return html
    return "<h1>Dashboard Template Not Found</h1>"

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
