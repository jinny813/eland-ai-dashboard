import sqlite3
import pandas as pd
import json
import os

print("--- Cleaning DB ---")
conn = sqlite3.connect('database/product_master.db')
df = pd.read_sql("SELECT no, brand_name, style_code, style_name FROM products WHERE brand_name IN ('발렌시아', '안지크')", conn)
print(f"Total {len(df)} records for 발렌시아/안지크")

def is_bad(r):
    bn = str(r['brand_name']).strip()
    sn = str(r['style_name']).replace('발렌시아가', '')
    return bn not in sn

bad = df[df.apply(is_bad, axis=1)]
print(f"Found {len(bad)} bad records in DB:")
for _, r in bad.iterrows():
    print(f"  - [{r['brand_name']}] {r['style_code']}: {r['style_name']}")

if len(bad) > 0:
    bad_nos = bad['no'].astype(str).tolist()
    conn.execute(f"DELETE FROM products WHERE no IN ({','.join(bad_nos)})")
    conn.commit()
    print("Deleted bad records from DB.")
conn.close()

print("\n--- Cleaning style_master.json (core) ---")
if os.path.exists('core/style_master.json'):
    with open('core/style_master.json', 'r', encoding='utf-8') as f:
        core_cache = json.load(f)
    keys_to_del = []
    for k, v in core_cache.items():
        if isinstance(v, dict):
            sn = str(v.get('style_name', ''))
            if sn == '정보 없음': continue
            bn = ''
            if '발렌시아_' in k: bn = '발렌시아'
            elif '안지크_' in k: bn = '안지크'
            if bn and bn not in sn.replace('발렌시아가', ''):
                keys_to_del.append(k)
    print(f"Found {len(keys_to_del)} bad records in core/style_master.json")
    for k in keys_to_del:
        print(f"  - {k} -> {core_cache[k]['style_name']}")
        del core_cache[k]
    with open('core/style_master.json', 'w', encoding='utf-8') as f:
        json.dump(core_cache, f, ensure_ascii=False, indent=4)
        
print("\n--- Cleaning style_master.json (functions) ---")
if os.path.exists('functions/core/style_master.json'):
    with open('functions/core/style_master.json', 'r', encoding='utf-8') as f:
        func_cache = json.load(f)
    keys_to_del = []
    for k, v in func_cache.items():
        if isinstance(v, dict):
            sn = str(v.get('style_name', ''))
            if sn == '정보 없음': continue
            bn = ''
            if '발렌시아_' in k: bn = '발렌시아'
            elif '안지크_' in k: bn = '안지크'
            if bn and bn not in sn.replace('발렌시아가', ''):
                keys_to_del.append(k)
    print(f"Found {len(keys_to_del)} bad records in functions/core/style_master.json")
    for k in keys_to_del:
        print(f"  - {k} -> {func_cache[k]['style_name']}")
        del func_cache[k]
    with open('functions/core/style_master.json', 'w', encoding='utf-8') as f:
        json.dump(func_cache, f, ensure_ascii=False, indent=4)
