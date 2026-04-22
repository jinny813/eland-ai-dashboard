import sys
import os

# core 디렉토리를 path에 추가
sys.path.append(r"d:\AI Assortment Agent")

try:
    from core.data_loader import load_dashboard_data
    print("SUCCESS: load_dashboard_data imported successfully.")
except Exception as e:
    import traceback
    print(f"FAILURE: Import failed.")
    print(traceback.format_exc())
