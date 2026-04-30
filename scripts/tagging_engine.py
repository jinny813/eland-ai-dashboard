import json
import sqlite3
import os

def migrate_and_tag():
    json_path = "core/style_master.json"
    db_path = "database/product_master.db"
    
    if not os.path.exists(json_path):
        print("JSON file not found.")
        return

    # 유저 제공 [유형/형태/느낌] 프레임워크 완벽 반영
    framework = {
        "item_detail": [
            "자켓", "블레이저", "코트", "트렌치코트", "점퍼", "파카", "가디건", "베스트", 
            "블라우스", "셔츠", "니트", "폴로", "티셔츠", "맨투맨", "후드", "나시", "탑",
            "슬랙스", "트라우저", "데님", "팬츠", "레깅스", "타이츠", "숏팬츠", "반바지",
            "캐주얼원피스", "드레시 원피스", "셔츠원피스", "니트원피스",
            "플레어스커트", "플리츠스커트", "타이트스커트", "H라인스커트", "미니스커트"
        ],
        "fit": [
            "슬림", "레귤러", "오버핏", "루즈", "와이드", "스트레이트", "A라인", "H라인", 
            "플레어", "크롭", "피트앤플레어"
        ],
        "material": [
            "트위드", "데님", "울", "캐시미어", "린넨", "코튼", "쉬폰", "새틴", "실키", 
            "니트", "폴리", "혼방", "레더", "패딩", "퀼팅", "레이스", "오간자", "벨벳"
        ],
        "detail": [
            "금장버튼", "벨트", "플리츠", "셋업", "리본", "셔링", "포켓", "라펠", "레이스", 
            "밴딩", "지퍼", "후드", "핀턱", "버튼", "워싱", "스트링"
        ],
        "color": [
            "블랙", "화이트", "아이보리", "베이지", "브라운", "그레이", "네이비", "블루", 
            "데님블루", "핑크", "레드", "와인", "카키", "그린", "옐로우", "체크", "패턴", "멀티"
        ]
    }

    with open(json_path, "r", encoding="utf-8") as f:
        master = json.load(f)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    count = 0
    for sc, info in master.items():
        name = str(info.get("style_name", ""))
        item_n = str(info.get("item_name", ""))
        brand = str(info.get("brand", ""))
        
        tags = []
        # 프레임워크 키워드 추출
        extracted = {}
        for category, keywords in framework.items():
            found = [kw for kw in keywords if kw in name]
            extracted[category] = ", ".join(found) if found else None
            tags.extend(found)
        
        # 중복 제거 및 정리
        tags = sorted(list(set(tags + ([item_n] if item_n and item_n != "nan" else []))))
        keywords_str = ", ".join(tags)

        cursor.execute("""
        INSERT OR REPLACE INTO products 
        (style_code, product_name, category, fit, material, detail, color, brand, keywords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sc, 
            name, 
            item_n if item_n != "nan" else None,
            extracted["fit"],
            extracted["material"],
            extracted["detail"],
            extracted["color"],
            brand,
            keywords_str
        ))
        count += 1

    conn.commit()
    conn.close()
    print(f"Migrated & Tagged {count} styles into product_master.db using 3-layer Framework.")

if __name__ == "__main__":
    migrate_and_tag()
