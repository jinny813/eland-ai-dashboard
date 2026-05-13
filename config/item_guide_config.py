# config/item_guide_config.py

"""
아이템 구색 가이드라인 설정 파일
- 각 카테고리(여성, 남성, 아동 등) 및 조닝별 최적 재고 비중 기준 정의
- '기타' 항목을 제외한 주요 5개 그룹(Outer, Top, Bottom, Skirt, Dress)에 대한 목표치
"""

ITEM_GUIDE_CONFIG = {
    "여성": {
        "캐릭터": {
            "Dress": 0.35,
            "Outer": 0.25,
            "Top": 0.15,
            "Bottom": 0.15,
            "Skirt": 0.0,  # 명시되지 않은 경우 0
        },
        "커리어": {
            "Outer": 0.45,
            "Top": 0.25,
            "Dress": 0.15,
            "Bottom": 0.10,
            "Skirt": 0.0,
        },
        "캐주얼": {
            "Outer": 0.35,
            "Top": 0.25,
            "Dress": 0.15,
            "Skirt": 0.15,
            "Bottom": 0.0,
        },
        "시니어": {
            "Dress": 0.35,
            "Outer": 0.30,
            "Top": 0.15,
            "Bottom": 0.15,
            "Skirt": 0.0,
        }
    },
    # 향후 확장 예시
    "남성": {
        "정장": {
            "Outer": 0.40,
            "Top": 0.30,
            "Bottom": 0.30,
            "Skirt": 0.0,
            "Dress": 0.0,
        }
    }
}

# 기본 매핑 그룹 (DB item_code -> UI 그룹명)
ITEM_UI_LABELS = {
    "Outer": "아우터",
    "Top": "상의",
    "Bottom": "하의",
    "Skirt": "스커트",
    "Dress": "원피스"
}
