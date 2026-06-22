import sqlite3
import re

conn = sqlite3.connect('database/product_master.db')
cursor = conn.cursor()

def clean_mismatches(table_name):
    try:
        cursor.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone()[0] == 0:
            return

        cursor.execute(f"SELECT style_code, product_name FROM {table_name}")
        rows = cursor.fetchall()
        
        bad_codes = []
        for style_code, product_name in rows:
            if not product_name: continue
            
            norm_sc = re.sub(r'[^a-zA-Z0-9]', '', str(style_code)).upper()
            
            # Extract all alphanumeric words from product_name
            words = re.findall(r'[a-zA-Z0-9]+', str(product_name))
            
            # If there's an alphanumeric word that looks like a style code (e.g. length >= 6)
            # but doesn't match our norm_sc, it's a mismatch!
            has_mismatch = False
            for w in words:
                w_upper = w.upper()
                if len(w_upper) >= 6:
                    if norm_sc not in w_upper and w_upper not in norm_sc:
                        # Allow partial match of first 6 chars (sometimes last digit drops)
                        if norm_sc[:6] not in w_upper:
                            has_mismatch = True
                            break
                            
            if has_mismatch:
                bad_codes.append(style_code)
                print(f"Mismatch in {table_name}: SC={style_code}, Name={product_name}")
                
        if bad_codes:
            qs = ','.join(['?']*len(bad_codes))
            cursor.execute(f"DELETE FROM {table_name} WHERE style_code IN ({qs})", bad_codes)
            conn.commit()
            print(f"Deleted {len(bad_codes)} mismatched records from {table_name}.")
    except Exception as e:
        print(f"Error in {table_name}: {e}")

clean_mismatches('products')
clean_mismatches('products_best')

conn.close()
