import pandas as pd
from database.gsheet_manager import GSheetManager

try:
    gsm = GSheetManager()
    # Read all records
    data = gsm.spreadsheet.worksheet("Records").get_all_records()
    df = pd.DataFrame(data)
    
    # Filter for 2025 March sales
    # year might be '2025' or '25년'
    # data_month might be '3월'
    df['y_str'] = df['year'].astype(str)
    df['m_str'] = df['data_month'].astype(str)
    
    mask_2025 = df['y_str'].str.contains('2025') | df['y_str'].str.contains('25')
    mask_march = df['m_str'].str.contains('3월')
    
    df_2025_03 = df[mask_2025 & mask_march].copy()
    
    if not df_2025_03.empty:
        # Group by store and brand
        res = df_2025_03.groupby(['store_name', 'brand_name'])['sales_amt'].sum().reset_index()
        print("HISTORICAL_DATA_START")
        for _, row in res.iterrows():
            print(f"{row['store_name']} | {row['brand_name']} | {row['sales_amt']}")
        print("HISTORICAL_DATA_END")
    else:
        print("No 2025-03 data found in Records sheet.")
        
except Exception as e:
    print(f"Error: {e}")
