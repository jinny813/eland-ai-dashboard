import pandas as pd
from database.gsheet_manager import GSheetManager

try:
    gsm = GSheetManager()
    data = gsm.spreadsheet.worksheet("Records").get_all_records()
    df = pd.DataFrame(data)
    
    # Filter for year 2025 and data_month 3월
    df['y_str'] = df['year'].astype(str)
    df['m_str'] = df['data_month'].astype(str)
    mask = (df['y_str'].str.contains('2025') | df['y_str'].str.contains('25')) & df['m_str'].str.contains('3월')
    df_hist = df[mask]
    
    targets = [
        ('동아쇼핑점', '로엠'),
        ('2001중계점', '리스트'),
        ('2001중계점', '나이스클랍'),
        ('NC송파점', '쉬즈미스'),
        ('NC평촌점', '바바팩토리')
    ]
    
    print("SEARCH_RESULTS_START")
    for store, brand in targets:
        match = df_hist[(df_hist['store_name'] == store) & (df_hist['brand_name'] == brand)]
        if not match.empty:
            sales = match['sales_amt'].sum()
            print(f"{store} | {brand} | {sales}")
        else:
            print(f"{store} | {brand} | NOT_FOUND")
    print("SEARCH_RESULTS_END")

except Exception as e:
    print(f"Error: {e}")
