"""
config/brand_metadata.py
========================
브랜드별 마스터 메타데이터 정보 (조닝, ENESS 매핑명 등)
"""

BRAND_METADATA = {
    # [브랜드명]: { "eness_name": "ENESS 매핑명", "zoning": "조닝(등급)" }
    # ── 커리어 (Career)
    "비씨비지": {"eness_name": "비씨비지", "zoning": "커리어"},
    "발렌시아": {"eness_name": "발렌시아", "zoning": "커리어"},
    "베스띠벨리": {"eness_name": "베스띠벨리", "zoning": "커리어"},
    "올리비아로렌": {"eness_name": "올리비아로렌", "zoning": "커리어"},
    "제시뉴욕": {"eness_name": "제시뉴욕", "zoning": "커리어"},
    "안지크": {"eness_name": "안지크", "zoning": "커리어"},

    # ── 캐주얼 (Casual)
    "리스트": {"eness_name": "리스트", "zoning": "캐주얼"},
    "시슬리": {"eness_name": "시슬리(영캐주얼)", "zoning": "캐주얼"},
    "에잇컨셉": {"eness_name": "에잇컨셉", "zoning": "캐주얼"},
    "샤틴": {"eness_name": "샤틴", "zoning": "캐주얼"},
    "플라스틱아일랜드": {"eness_name": "플라스틱아일랜드", "zoning": "캐주얼"},

    # ── 캐릭터 (Character)
    "쉬즈미스": {"eness_name": "쉬즈미스", "zoning": "캐릭터"},
    "미샤": {"eness_name": "-", "zoning": "캐릭터"},
    "로엠": {"eness_name": "로엠(ROEM)", "zoning": "캐릭터"},
    "베네통": {"eness_name": "베네통(영캐주얼)", "zoning": "캐릭터"},
    "JJ지고트": {"eness_name": "JJ지고트", "zoning": "캐릭터"},
    "나이스클랍": {"eness_name": "나이스클랍", "zoning": "캐릭터"},
    "보브": {"eness_name": "-", "zoning": "캐릭터"},
    "톰보이": {"eness_name": "-", "zoning": "캐릭터"},
    "클라비스": {"eness_name": "클라비스(CLOVIS)", "zoning": "캐릭터"},
    "더아이잗": {"eness_name": "더아이잗", "zoning": "캐릭터"},
    "보니스팍스": {"eness_name": "보니스팍스", "zoning": "캐릭터"},

    # ── 시니어 (Senior)
    "바바팩토리": {"eness_name": "바바팩토리", "zoning": "시니어"},
}

def get_brand_zoning(name: str) -> str:
    """브랜드명을 입력받아 조닝 등급을 반환합니다."""
    # 정확히 일치하는 경우
    if name in BRAND_METADATA:
        return BRAND_METADATA[name]['zoning']
    
    # ENESS 명칭 포함 여부로 유사성 체크 (예: 로엠 -> 로엠(ROEM))
    for b_name, meta in BRAND_METADATA.items():
        if name in meta['eness_name'] or meta['eness_name'] in name:
            return meta['zoning']
            
    return "미분류" # 기본값

def get_eness_name(name: str) -> str:
    """원본 브랜드명의 ENESS 매핑 이름을 반환합니다."""
    return BRAND_METADATA.get(name, {}).get("eness_name", name)
