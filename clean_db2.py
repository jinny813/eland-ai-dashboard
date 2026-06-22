import sqlite3

print("--- Cleaning product_master.db ---")
conn = sqlite3.connect('database/product_master.db')
cursor = conn.cursor()

cursor.execute("SELECT item_code, product_name FROM products_best")
rows = cursor.fetchall()
    
bad_codes = []
for item_code, product_name in rows:
    sn = str(product_name).replace('발렌시아가', '')
    bn = ''
    if '발렌시아_' in str(item_code): bn = '발렌시아'
    elif '안지크_' in str(item_code): bn = '안지크'
    
    if bn and bn not in sn:
        bad_codes.append(item_code)

print(f"Found {len(bad_codes)} bad records in DB")
if bad_codes:
    for code in bad_codes[:10]:
        print(f"  - bad code: {code}")
        
    qs = ','.join(['?']*len(bad_codes))
    cursor.execute(f"DELETE FROM products_best WHERE item_code IN ({qs})", bad_codes)
    conn.commit()
    print("Deleted bad records from DB.")
conn.close()
