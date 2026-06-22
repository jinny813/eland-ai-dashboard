import json
import os

print("--- Cleaning style_master.json (core) ---")
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
