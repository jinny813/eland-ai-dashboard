import sqlite3

conn = sqlite3.connect('database/product_master.db')
cursor = conn.cursor()

def clean_table(table_name):
    try:
        # Check if table exists
        cursor.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone()[0] == 0:
            print(f"Table {table_name} does not exist.")
            return

        cursor.execute(f"SELECT style_code, product_name FROM {table_name}")
        rows = cursor.fetchall()
        
        bad_codes = []
        for style_code, product_name in rows:
            sn = str(product_name)
            if '아디다스' in sn or '네이처하이크' in sn or '샤넬' in sn or '스투시' in sn or '나이키' in sn:
                bad_codes.append(style_code)
        
        if bad_codes:
            print(f"Found {len(bad_codes)} bad records in {table_name}")
            for code in bad_codes:
                print(f"  - bad code: {code}")
            
            qs = ','.join(['?']*len(bad_codes))
            cursor.execute(f"DELETE FROM {table_name} WHERE style_code IN ({qs})", bad_codes)
            conn.commit()
            print(f"Deleted bad records from {table_name}.")
        else:
            print(f"No bad records found in {table_name}.")
    except Exception as e:
        print(f"Error in {table_name}: {e}")

clean_table('products')
clean_table('products_best')

conn.close()
