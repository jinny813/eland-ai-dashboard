@echo off
echo ==============================================
echo E-LAND AI Assortment Agent - Dev Starter
echo ==============================================

:: 가상환경 활성화 및 백엔드 uvicorn 실행 (백그라운드)
echo 1. Starting Uvicorn backend...
start /b .venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload > logs\uvicorn.log 2>&1

:: 잠시 대기 (백엔드 포트 점유 대기)
timeout /t 2 >nul

:: 프론트엔드 streamlit 실행
echo 2. Starting Streamlit dashboard...
.venv\Scripts\streamlit.exe run main.py --server.port 8501

pause
