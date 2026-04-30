import sqlite3
import os
from typing import List, Dict

# 프레임워크 정의
FRAMEWORK = {
    "fit": ["슬림", "레귤러", "오버핏", "루즈", "와이드", "스트레이트", "A라인", "H라인", "플레어", "크롭", "피트앤플레어"],
    "material": ["트위드", "데님", "울", "캐시미어", "린넨", "코튼", "쉬폰", "새틴", "실키", "니트", "폴리", "혼방", "레더", "패딩", "퀼팅", "레이스", "오간자", "벨벳"],
    "detail": ["금장버튼", "벨트", "플리츠", "셋업", "리본", "셔링", "포켓", "라펠", "레이스", "밴딩", "지퍼", "후드", "핀턱", "버튼", "워싱", "스트링"],
    "color": ["블랙", "화이트", "아이보리", "베이지", "브라운", "그레이", "네이비", "블루", "데님블루", "핑크", "레드", "와인", "카키", "그린", "옐로우", "체크", "패턴", "멀티"]
}

def enrich_from_search_results(style_code: str, brand: str, search_text: str):
    """검색 결과 텍스트에서 프레임워크 기반 키워드 추출 및 DB 업데이트"""
    db_path = "database/product_master.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    extracted = {}
    all_tags = []
    for category, keywords in FRAMEWORK.items():
        found = [kw for kw in keywords if kw in search_text]
        extracted[category] = ", ".join(found) if found else None
        all_tags.extend(found)
    
    keywords_str = ", ".join(sorted(list(set(all_tags))))
    
    cursor.execute("""
    UPDATE products 
    SET fit = ?, material = ?, detail = ?, color = ?, keywords = ?
    WHERE style_code = ?
    """, (extracted["fit"], extracted["material"], extracted["detail"], extracted["color"], keywords_str, style_code))
    
    conn.commit()
    conn.close()
    print(f"Enriched {style_code} with keywords: {keywords_str}")

if __name__ == "__main__":
    # 이 스크립트는 외부(AIAgent)에서 검색된 텍스트를 전달받아 처리하는 용도로 설계됨
    import sys
    if len(sys.argv) > 3:
        enrich_from_search_results(sys.argv[1], sys.argv[2], " ".join(sys.argv[3:]))
