
with open(r'd:\AI Assortment Agent\core\scoring_logic.py', 'rb') as f:
    content = f.read().splitlines()
    line_227_raw = content[226] # 0-indexed
    print(f"Line 227 Raw Bytes: {line_227_raw}")
    print(f"Line 227 Text: {line_227_raw.decode('utf-8', errors='replace')}")
