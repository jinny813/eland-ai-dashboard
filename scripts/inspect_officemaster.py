import os
import sys
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
from database.gsheet_manager import GSheetManager

logging.basicConfig(level=logging.INFO)

def inspect_officemaster():
    print("Connecting to GSheet GSheetManager...")
    mgr = GSheetManager()
    if not mgr.is_connected:
        print(f"Connection failed! Error: {mgr.error_msg}")
        return

    print("Loading officemaster DataFrame...")
    df_office = mgr.load_office_master()
    if mgr.error_msg:
        print(f"Error during loading officemaster: {mgr.error_msg}")
    print("\n=================== officemaster columns ===================")
    print(df_office.columns)
    print("\n=================== officemaster content ===================")
    print(df_office)

if __name__ == "__main__":
    inspect_officemaster()

