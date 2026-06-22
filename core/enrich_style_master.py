import json
import sqlite3
import os
import re
import urllib.request
import time
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "style_master.json")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "product_master.db")

# 키워드 프레임워크 딕셔너리
FRAMEWORK = {
    "type": ["자켓", "팬츠", "원피스", "스커트", "니트", "블라우스", "셔츠", "티셔츠", "가디건", "코트", "점퍼", "패딩", "슬랙스"],
    "fit": ["슬림", "오버핏", "루즈핏", "레귤러", "부츠컷", "와이드", "테이퍼드", "H라인", "A라인", "스트레이트", "크롭", "미디", "롱", "숏"],
    "material": ["레더", "린넨", "트위드", "데님", "울", "캐시미어", "쉬폰", "새틴", "코듀로이", "자카드", "스판"],
    "detail": ["브이넥", "라운드넥", "하프넥", "벨티드", "포켓", "더블", "싱글", "노카라", "오픈카라", "프릴", "레이스", "밴딩", "핀턱", "투턱", "원턱", "슬릿", "패턴"],
    "color": ["블랙", "화이트", "아이보리", "베이지", "네이비", "그레이", "차콜", "브라운", "카키", "핑크", "레드", "블루", "스카이블루", "옐로우", "민트", "그린"]
}

def extract_specs(text):
    text = text.replace(" ", "")
    specs = { "type": [], "fit": [], "material": [], "detail": [], "color": [] }
    
    for category, keywords in FRAMEWORK.items():
        for kw in keywords:
            if kw in text:
                specs[category].append(kw)
    
    return {k: ",".join(v) if v else "" for k, v in specs.items()}

def search_naver_shopping(query, brand=""):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return None
    
    # 검색어에 브랜드를 포함시켜 검색 정확도를 높입니다.
    search_query = f"{brand} {query}".strip()
    encText = urllib.parse.quote(search_query)
    
    # 브랜드 교차 검증을 위해 여유 있게 5개 항목을 요청합니다.
    url = f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=5"
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if rescode == 200:
            response_body = response.read()
            data = json.loads(response_body.decode('utf-8'))
            if data['items']:
                # 브랜드가 명시된 경우, 타이틀/브랜드/몰 이름 등에 포함되어 있는지 확인
                if brand:
                    def check_brand(tb, txt):
                        if tb == '발렌시아': return '발렌시아' in txt.replace('발렌시아가', '')
                        return tb in txt

                    for item in data['items']:
                        title = re.sub(r'<[^>]*>', '', item['title'])
                        
                        if check_brand(brand, title):
                            category = item.get('category3', item.get('category2', item.get('category1', '')))
                            return {"title": title, "category": category}
                    # If brand is provided but none match, return None to prevent wrong brand association
                    return None
                else:
                    item = data['items'][0]
                    title = re.sub(r'<[^>]*>', '', item['title'])
                    category = item.get('category3', item.get('category2', item.get('category1', '')))
                    return {"title": title, "category": category}
    except Exception as e:
        print(f"API Error for {query}: {e}")
    return None

def main():
    print("Loading style_master.json...")
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Total items in json: {len(data)}")
    
    # DB Connect
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Drop existing products table and create new one with correct schema
    cur.execute("DROP TABLE IF EXISTS products_best;")
    cur.execute('''
        CREATE TABLE products_best (
            item_code TEXT PRIMARY KEY,
            product_name TEXT,
            category TEXT,
            fit TEXT,
            material TEXT,
            detail TEXT,
            color TEXT,
            is_best INTEGER,
            old_name TEXT
        )
    ''')
    
    migrated_count = 0
    samples = []
    
    print("Processing items...")
    # 100개만 우선 테스트/진행할지, 전체 진행할지 결정 (일단 전체 루프, API 제한 주의)
    # 전체 진행 시 시간이 오래 걸릴 수 있으므로 50개만 샘플로 진행합니다. (요청에 따라 변경 가능)
    # 여기서는 모두 진행하되, API Key가 없을 경우를 대비합니다.
    items = list(data.items())
    
    for idx, (item_code, info) in enumerate(items):
        old_name = info.get("style_name", info.get("item_name", ""))
        category = info.get("item_name", "")
        brand = info.get("brand", "")
        
        # 1. API 호출
        api_data = search_naver_shopping(item_code, brand)
        
        if api_data:
            product_name = api_data['title']
            category = api_data['category'] if api_data['category'] else category
        else:
            product_name = old_name
            
        # 2. 스펙 추출
        specs = extract_specs(product_name)
        
        # 3. DB 삽입
        cur.execute('''
            INSERT INTO products_best (item_code, product_name, category, fit, material, detail, color, is_best, old_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item_code,
            product_name,
            category,
            specs['fit'],
            specs['material'],
            specs['detail'],
            specs['color'],
            1, # is_best
            old_name
        ))
        
        migrated_count += 1
        
        if len(samples) < 5:
            samples.append({
                "item_code": item_code,
                "product_name": product_name,
                "old_name": old_name,
                "specs": specs
            })
            
        # API 호출 속도 조절 (네이버 서버 차단 방지)
        if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
            time.sleep(0.1)
            
        # 100건 단위 배치 커밋
        if migrated_count % 100 == 0:
            print(f"Processed {migrated_count} items... Committing batch.")
            conn.commit()
            
    # 최종 남은 데이터 커밋
    conn.commit()
    conn.close()
    
    print(f"\nMigration Complete! Total records migrated: {migrated_count}")
    print("\n--- 5 Sample Extracted Specs ---")
    for s in samples:
        print(f"Item Code: {s['item_code']}")
        print(f"Product Name (API/New): {s['product_name']}")
        print(f"Old Name (JSON Backup): {s['old_name']}")
        print(f"Extracted Specs: {s['specs']}")
        print("-" * 30)

if __name__ == "__main__":
    main()
