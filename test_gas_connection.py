import requests
import json
import sys

# Windows console encoding fix
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_gas_connection():
    print("="*60)
    print("  Google Apps Script (GAS) Connection Test")
    print("="*60)
    
    GAS_ID = "AKfycbz4gMtvIik1yzCEKU-je0bWVUXhYvYp9qpWaSunpdUiePAJmlmkWtxmtigP-w5CgTrEEg"
    GAS_URL = f"https://script.google.com/macros/s/{GAS_ID}/exec"
    
    # 1. READ TEST
    print("\n[TEST 1] Read All Records")
    try:
        res = requests.get(GAS_URL, params={"action": "read_all", "sheetName": "Records"}, timeout=30)
        print(f"  HTTP Status: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            print(f"  Data Type: {type(data)}")
            
            if isinstance(data, list):
                print(f"  SUCCESS: Retrieved {len(data)} records (direct list).")
                if data:
                    print(f"  Sample Record: {data[0]}")
            elif isinstance(data, dict):
                if data.get("status") == "success":
                    records = data.get("data", [])
                    print(f"  SUCCESS: Retrieved {len(records)} records (dict wrapper).")
                else:
                    print(f"  API ERROR: {data.get('message')}")
            else:
                print(f"  UNKNOWN FORMAT: {data}")
        else:
            print(f"  HTTP ERROR: {res.status_code}")
            print(f"  Response: {res.text[:500]}")
    except Exception as e:
        print(f"  FATAL ERROR: {e}")

if __name__ == "__main__":
    test_gas_connection()
