import sys

def fix_data_loader(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # fix line 180 (indexed 179)
        if "if b_df.empty: continue # 도달 불가능한 코드" in line:
            # Check indentation
            indent = line[:line.find("if")]
            new_lines.append(f"{indent}if b_df.empty: # 도달 불가능한 코드\n")
            i += 1
            continue
            
        new_lines.append(line)
        i += 1

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    fix_data_loader(r"d:\AI Assortment Agent\core\data_loader.py")
