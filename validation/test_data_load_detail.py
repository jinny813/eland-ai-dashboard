import os
import sys
import json
import pandas as pd
from core.data_loader import load_dashboard_data

try:
    data = load_dashboard_data()
    if 'error' in data:
        print(f"ERROR: {data['error']}")
    else:
        # Check a sample brand detail
        brands = data.get('BRANDS', [])
        if brands:
            b = brands[0]
            st = b['store']
            bn = b['name']
            bt = b['type_label']
            detail = data.get('DETAIL', {}).get(st, {}).get(bn, {}).get(bt, {})
            print(f"Brand: {bn}, Store: {st}, Type: {bt}")
            print(f"Detail keys: {detail.keys()}")
            if 'item' in detail:
                print(f"Item segments: {len(detail['item']['segs'])}")
                print(f"First item seg: {detail['item']['segs'][0] if detail['item']['segs'] else 'None'}")
        else:
            print("No brands found.")
except Exception as e:
    import traceback
    traceback.print_exc()
