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
    "바바팩토리": {"eness_name": "바바팩토리", "zoning": "시니어", "category": "여성"},

    # ── 캐주얼 (Casual Category)
    "SPAO(캐주얼)": {"eness_name": "SPAO(캐주얼)", "zoning": "캐주얼", "category": "캐주얼"},
    "행텐": {"eness_name": "행텐", "zoning": "캐주얼", "category": "캐주얼"},
    "후아유": {"eness_name": "후아유", "zoning": "캐주얼", "category": "캐주얼"},
    "폴햄": {"eness_name": "폴햄", "zoning": "캐주얼", "category": "캐주얼"},
    "마인드브릿지": {"eness_name": "마인드브릿지", "zoning": "캐주얼", "category": "캐주얼"},
    "프로젝트M": {"eness_name": "프로젝트M", "zoning": "캐주얼", "category": "캐주얼"},
    "멤버헐리데이": {"eness_name": "멤버헐리데이", "zoning": "캐주얼", "category": "캐주얼"},
    "JEEP": {"eness_name": "JEEP", "zoning": "캐주얼", "category": "캐주얼"},
    "탑텐": {"eness_name": "탑텐", "zoning": "캐주얼", "category": "캐주얼"},
    "더블에이트": {"eness_name": "더블에이트", "zoning": "캐주얼", "category": "캐주얼"},
    "그루브라임플레이": {"eness_name": "그루브라임플레이", "zoning": "캐주얼", "category": "캐주얼"},

    # ── 잡화
    "엘레강스(핸드백)": {"eness_name": "엘레강스(핸드백)", "zoning": "핸드백", "category": "잡화"},
    "헤지스(핸드백)": {"eness_name": "헤지스(핸드백)", "zoning": "핸드백", "category": "잡화"},
    "아메리칸투어리스트": {"eness_name": "아메리칸투어리스트", "zoning": "핸드백", "category": "잡화"},
    "오야니": {"eness_name": "오야니", "zoning": "핸드백", "category": "잡화"},
    "발리스윗": {"eness_name": "발리스윗", "zoning": "핸드백", "category": "잡화"},
    "소다": {"eness_name": "소다", "zoning": "제화", "category": "잡화"},
    "미셸BY탠디": {"eness_name": "미셸BY탠디", "zoning": "제화", "category": "잡화"},
    "베디베로": {"eness_name": "베디베로", "zoning": "일용잡화", "category": "잡화"},
    "금강아울렛": {"eness_name": "금강아울렛", "zoning": "제화", "category": "잡화"},

    # ── 남성의류
    "크로커다일(CROCODILE)": {"eness_name": "크로커다일(CROCODILE)", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "지오지아팩토리": {"eness_name": "지오지아팩토리", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "웰메이드": {"eness_name": "웰메이드", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "올젠": {"eness_name": "올젠", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "피에르가르뎅(신사캐주얼)": {"eness_name": "피에르가르뎅(신사캐주얼)", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "헤지스(신사캐주얼)": {"eness_name": "헤지스(신사캐주얼)", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "앤드지": {"eness_name": "앤드지", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "에디션": {"eness_name": "에디션", "zoning": "신사캐쥬얼", "category": "남성의류"},
    "슈페리어": {"eness_name": "슈페리어", "zoning": "골프", "category": "남성의류"},
    "엘르골프": {"eness_name": "엘르골프", "zoning": "골프", "category": "남성의류"},
    "PING(핑)": {"eness_name": "PING(핑)", "zoning": "골프", "category": "남성의류"},
    "루이까스텔": {"eness_name": "루이까스텔", "zoning": "골프", "category": "남성의류"},
    "파사디골프": {"eness_name": "파사디골프", "zoning": "골프", "category": "남성의류"},
    "와이드앵글": {"eness_name": "와이드앵글", "zoning": "골프", "category": "남성의류"},
    "까스텔바작": {"eness_name": "까스텔바작", "zoning": "골프", "category": "남성의류"},
    "삼성패션아울렛": {"eness_name": "삼성패션아울렛", "zoning": "신사정장", "category": "남성의류"},
    "트레몰로": {"eness_name": "트레몰로", "zoning": "신사정장", "category": "남성의류"},
    "코오롱종합관": {"eness_name": "코오롱종합관", "zoning": "신사정장", "category": "남성의류"},
    "예작": {"eness_name": "예작", "zoning": "셔츠/타이", "category": "남성의류"},

    # ── 아동의류
    "아가방": {"eness_name": "아가방", "zoning": "유아", "category": "아동의류"},
    "휠라키즈": {"eness_name": "휠라키즈", "zoning": "아동", "category": "아동의류"},
    "베네통키즈": {"eness_name": "베네통키즈", "zoning": "토들러", "category": "아동의류"},
    "에스핏": {"eness_name": "에스핏", "zoning": "아동", "category": "아동의류"},
    "소이": {"eness_name": "소이", "zoning": "아동", "category": "아동의류"},
    "에꼴리에": {"eness_name": "에꼴리에", "zoning": "아동", "category": "아동의류"},
    "에어워크주니어": {"eness_name": "에어워크주니어", "zoning": "아동", "category": "아동의류"},
    "뉴발란스키즈": {"eness_name": "뉴발란스키즈", "zoning": "아동", "category": "아동의류"},
    "블랙야크키즈": {"eness_name": "블랙야크키즈", "zoning": "아동", "category": "아동의류"},
    "래핑차일드": {"eness_name": "래핑차일드", "zoning": "아동", "category": "아동의류"},
    "앙팡스(압소바)": {"eness_name": "앙팡스(압소바)", "zoning": "아동", "category": "아동의류"},
    "스타일노리터": {"eness_name": "스타일노리터", "zoning": "아동", "category": "아동의류"},
    "폴햄키즈": {"eness_name": "폴햄키즈", "zoning": "아동", "category": "아동의류"},
    "탑텐키즈": {"eness_name": "탑텐키즈", "zoning": "아동", "category": "아동의류"},
    "에스마켓키즈": {"eness_name": "에스마켓키즈", "zoning": "아동", "category": "아동의류"},
    "NBA키즈": {"eness_name": "NBA키즈", "zoning": "아동", "category": "아동의류"},
    "아이러브제이": {"eness_name": "아이러브제이", "zoning": "아동", "category": "아동의류"},
    "스파오키즈": {"eness_name": "스파오키즈", "zoning": "아동", "category": "아동의류"},
    "스케쳐스키즈": {"eness_name": "스케쳐스키즈", "zoning": "아동잡화", "category": "아동의류"},
    "모이몰른": {"eness_name": "모이몰른", "zoning": "아동잡화", "category": "아동의류"},
    "행텐틴즈": {"eness_name": "행텐틴즈", "zoning": "토들러", "category": "아동의류"},
    "프로젝트키즈": {"eness_name": "프로젝트키즈", "zoning": "토들러", "category": "아동의류"},

    # ── 스포츠
    "아디다스(ADIDAS)": {"eness_name": "아디다스(ADIDAS)", "zoning": "스포츠", "category": "스포츠"},
    "프로스펙스": {"eness_name": "프로스펙스", "zoning": "스포츠", "category": "스포츠"},
    "뉴발란스": {"eness_name": "뉴발란스", "zoning": "스포츠", "category": "스포츠"},
    "노스페이스(THENORTHFACE)": {"eness_name": "노스페이스(THENORTHFACE)", "zoning": "아웃도어", "category": "스포츠"},
    "크록스(CROCS)": {"eness_name": "크록스(CROCS)", "zoning": "신발", "category": "스포츠"},
    "젝시믹스": {"eness_name": "젝시믹스", "zoning": "애슬레저", "category": "스포츠"},
    "르꼬끄스포르티브": {"eness_name": "르꼬끄스포르티브", "zoning": "스포츠", "category": "스포츠"},
    "휠라(FILA)": {"eness_name": "휠라(FILA)", "zoning": "스포츠", "category": "스포츠"},
    "스케쳐스": {"eness_name": "스케쳐스", "zoning": "스포츠", "category": "스포츠"},
    "ABC마트": {"eness_name": "ABC마트", "zoning": "신발", "category": "스포츠"},
    "데상트": {"eness_name": "데상트", "zoning": "스포츠", "category": "스포츠"},
    "블랙야크": {"eness_name": "블랙야크", "zoning": "아웃도어", "category": "스포츠"},
    "아이더(EIDER)": {"eness_name": "아이더(EIDER)", "zoning": "아웃도어", "category": "스포츠"},
    "네파": {"eness_name": "네파", "zoning": "아웃도어", "category": "스포츠"},
    "디스커버리": {"eness_name": "디스커버리", "zoning": "아웃도어", "category": "스포츠"},
    "유나이티드 스포츠": {"eness_name": "유나이티드 스포츠", "zoning": "편집샵", "category": "스포츠"},
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
