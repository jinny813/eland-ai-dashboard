import sys
import os
import json
from datetime import datetime

# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

try:
    from core.data_loader import load_dashboard_data
    from database.gsheet_manager import GSheetManager
    
    print("데이터를 불러오는 중입니다 (구글 시트 연동)...")
    mgr = GSheetManager()
    if not mgr.is_connected:
        print("오류: 구글 시트 연동에 실패했습니다.")
        sys.exit(1)
        
    db_data = load_dashboard_data(mgr=mgr)
    
    if "error" in db_data:
        print(f"데이터 로드 오류: {db_data['error']}")
        sys.exit(1)
        
    template_path = "ui/dashboard_template.html"
    preview_path = "preview_dashboard.html"
    
    if not os.path.exists(template_path):
        print(f"오류: 템플릿 파일이 없습니다: {template_path}")
        sys.exit(1)
        
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()
        
    # 데이터 주입
    data_json = json.dumps(db_data, ensure_ascii=False)
    script_inject = f"<script>window.__INITIAL_DATA__ = {data_json};</script>"
    
    # <script> 태그 바로 앞에 데이터 주입
    final_html = html_template.replace('<script>', script_inject + '<script>', 1)
    
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    print(f"🎉 성공! 프리뷰 파일이 생성되었습니다: {os.path.abspath(preview_path)}")
    print("브라우저에서 이 파일을 열어 대시보드를 확인하세요.")

except Exception as e:
    import traceback
    print(f"오류 발생: {e}")
    traceback.print_exc()
