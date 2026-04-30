import gspread
from google.oauth2.service_account import Credentials
import sys
import json
from pathlib import Path

def test_sheets():
    try:
        client = gspread.service_account(filename="credentials.json")
        ss = client.open("AI_Assortment_DB")
        print(f"Spreadsheet ID: {ss.id}")
    except Exception as e:
        print(e)
        
test_sheets()
