import json
import os
import sqlite3

def clean_json(file_path):
    print(f"\n--- Cleaning {file_path} ---")
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    with open(file_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
        
    keys_to_del = []
    for k, v in cache.items():
        if isinstance(v, dict):
            sn = str(v.get('style_name', ''))
            if sn == '정보 없음': continue
            
            # Extract brand from the JSON value if it exists
            bn = v.get('brand', '')
            
            # Some entries might not have 'brand' but we know the target brands
            if bn in ['발렌시아', '안지크']:
                if bn == '발렌시아' and '발렌시아' not in sn.replace('발렌시아가', ''):
                    keys_to_del.append(k)
                elif bn == '안지크' and '안지크' not in sn:
                    keys_to_del.append(k)
            else:
                # If brand is not explicitly saved in JSON, we can do a reverse check
                # If the style name contains Adidas/Naturehike but we know Anzick/Valencia uploaded it...
                # Actually, if 'brand' is missing, it's safer to just delete if it matches known bad patterns.
                if '아디다스' in sn or '네이처하이크' in sn or '샤넬' in sn or '스투시' in sn or '나이키' in sn:
                    keys_to_del.append(k)
                    
    print(f"Found {len(keys_to_del)} bad records in {file_path}")
    for k in keys_to_del:
        print(f"  - {k} -> {cache[k].get('style_name')}")
        del cache[k]
        
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
    print("Cleaned!")

clean_json('core/style_master.json')
clean_json('functions/core/style_master.json')

print("\n--- Cleaning product_master.db ---")
conn = sqlite3.connect('database/product_master.db')
cursor = conn.cursor()

try:
    cursor.execute("SELECT item_code, product_name, old_name FROM products_best")
    rows = cursor.fetchall()
        
    bad_codes = []
    for item_code, product_name, old_name in rows:
        sn = str(product_name)
        # Try to infer brand from old_name or if it has known bad keywords
        if '아디다스' in sn or '네이처하이크' in sn or '샤넬' in sn or '스투시' in sn or '나이키' in sn:
            bad_codes.append(item_code)
        
        # Or if we know the item_code is supposed to be Anzick/Valencia? 
        # products_best doesn't store the requested brand. 
        # But wait! If the crawler found "발렌시아", it would be in the title IF it was correct.
        # So we can just delete known bad titles.

    print(f"Found {len(bad_codes)} bad records in DB")
    if bad_codes:
        for code in bad_codes[:10]:
            print(f"  - bad code: {code}")
            
        qs = ','.join(['?']*len(bad_codes))
        cursor.execute(f"DELETE FROM products_best WHERE item_code IN ({qs})", bad_codes)
        conn.commit()
        print("Deleted bad records from DB.")
except Exception as e:
    print(f"DB Error: {e}")
finally:
    conn.close()
