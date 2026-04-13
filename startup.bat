@echo off
echo ==============================================
echo E-LAND AI Assortment Agent - FastAPI Server
echo ==============================================
echo Starting Uvicorn backend...
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
