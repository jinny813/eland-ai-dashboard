import os
import sys
import pandas as pd
from core.data_loader import load_dashboard_data

# Mock GSheetManager if needed, or just let it connect
try:
    data = load_dashboard_data()
    if 'error' in data:
        print(f"ERROR: {data['error']}")
        if 'traceback' in data:
            print(data['traceback'])
    else:
        print("SUCCESS: Data loaded.")
        print(f"Brands: {len(data.get('BRANDS', []))}")
except Exception as e:
    import traceback
    print(f"CRASH: {e}")
    traceback.print_exc()
