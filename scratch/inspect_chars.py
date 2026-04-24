
with open(r'd:\AI Assortment Agent\core\scoring_logic.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    line_227 = lines[226]
    print(f"Line 227 length: {len(line_227)}")
    for char in line_227:
        print(f"Char: {repr(char)} Code: {ord(char)}")
