
with open(r'd:\AI Assortment Agent\core\scoring_logic.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i in range(220, 235):
        if i < len(lines):
            line = lines[i]
            print(f"{i+1:3}: {repr(line)}")
