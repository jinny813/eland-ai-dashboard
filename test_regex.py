import re

def clean_raw_product_name(name):
    if not name: return ""
    name = str(name).strip()
    # 1. '대일)', 'FD장인)', '비노)' 같은 여는 괄호 없는 닫는 괄호 접두사 제거
    # 문자열의 처음부터 탐색하여 '(' 없이 ')'가 먼저 나오는 패턴을 찾아 그 앞을 모두 날림
    while True:
        m = re.match(r'^[^()]*\)', name)
        if m:
            name = name[m.end():].strip()
        else:
            break
            
    # 2. ◆, ※, # 등 특수기호 단어 제거
    name = re.sub(r'[◆※#][^\s]+', '', name)
    name = name.strip()
    return name

cases = [
    "대일)민소매조직KPO",
    "데코 집업 니트가디건 P1G22KCD300DJ",
    "D1F22KPO500 비노)SET조직변형단추포인트 PO",
    "FD장인)아세나일론BL",
    "레토)헤미안PT-JP",
    "◆전략/#장인)린넨코튼체크(MI),다올)폴리링클 전략(BK,IV)",
    "※태우)폴리스판FD",
    "(JJ지고트) 셔츠 배색 브이넥 풀오버 니트"
]

for c in cases:
    print(f"[{c}] => [{clean_raw_product_name(c)}]")
