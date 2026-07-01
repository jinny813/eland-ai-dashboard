"""
config/scoring_config.py
========================
[버전] v5 — 최종 재고 로직 완결본 (목표 달성률 기반)

■ 구조:
  - _WOMEN_NORMAL_BASE : 여성/정상 매장 공통 파라미터
  - _WOMEN_OUTLET_BASE : 여성/상설 매장 공통 파라미터
  - SCORING_CONFIG     : 브랜드별 개별 설정 딕셔너리 (메인 진입점)

■ 조닝(Zoning) 체계:
  - Career(커리어), Casual(캐주얼), Character(캐릭터), Senior(시니어)
"""

from config.brand_metadata import get_brand_zoning

# ──────────────────────────────────────────────────────
# 조닝별 아이템별 목표 비중 (inv_weights.item 용)
# ──────────────────────────────────────────────────────
_ITEM_CAREER    = {"Outer": 0.45, "Top": 0.25, "Dress": 0.15, "Bottom": 0.10, "Skirt": 0.05}
_ITEM_CASUAL    = {"Outer": 0.35, "Top": 0.25, "Dress": 0.15, "Bottom": 0.10, "Skirt": 0.15}
_ITEM_CHARACTER = {"Dress": 0.35, "Outer": 0.25, "Top": 0.15, "Bottom": 0.15, "Skirt": 0.10}
_ITEM_SENIOR    = {"Dress": 0.35, "Outer": 0.30, "Top": 0.15, "Bottom": 0.15, "Skirt": 0.05}
_ITEM_MENS = {"Suits": 0.40, "Shirts": 0.20, "Casual": 0.20, "Knit": 0.10, "Bottom": 0.10}
_ITEM_KIDS = {"Outer": 0.30, "Top": 0.30, "Bottom": 0.25, "Dress": 0.05, "Set": 0.10}

# ──────────────────────────────────────────────────────
# 공통: 여성/정상 매장 파라미터
# ──────────────────────────────────────────────────────
_WOMEN_NORMAL_BASE = {
    # BP 건강구간 (기존 v4 잔재 - 차후 정리 가능)
    "bp_discount_50_70": [0.0,  0.1],
    "bp_discount_30_50": [2.6,  14.9],
    "bp_discount_0_30":  [42.0, 50.6],
    "bp_freshness_target": 70.0,
    "bp_season_target":  [21.0, 22.3],
    "bp_best_target":    [25.0, 29.4],
    "year_base": 2026,

    # ── 최종 재고 로직 목표 비중 (이미지 최종판 기준)
    # 시즌: 봄(SS)=0.25, 여름(당시즌)=0.50 → sum=0.75 → 봄 max 5점, 여름 max 10점 정확히 산출
    "inv_weights": {
        "dis":    {"s0": 0.70, "s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.15},
        "fresh":  {"new": 0.70},           # 기획 0% → 점수 산출 제외
        "best":   {"store10": 0.35},       # 정상 BEST 재고비중 35%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   {"Outer": 0.30, "Top": 0.30, "Bottom": 0.20, "Skirt": 0.10, "Dress": 0.10}
    },

    # 지표별 최종 가중치 (총점 산출용): dis=30점, fresh=20점, sea=15점, best=35점
    "weight_discount":  0.30,
    "weight_freshness": 0.20,
    "weight_season":    0.15,
    "weight_best":      0.35,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────
# 공통: 여성/상설 매장 파라미터
# ──────────────────────────────────────────────────────
_WOMEN_OUTLET_BASE = {
    "bp_freshness_target": 10.0,
    "year_base": 2026,

    # ── 최종 재고 로직 목표 비중 (이미지 최종판 기준)
    # best store10: 25% (이미지 상설 25%), 시즌: 봄=0.25, 여름=0.50 → 봄 5점, 여름 10점
    "inv_weights": {
        "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10},
        "fresh":  {"new": 0.10, "plan": 0.20},
        "best":   {"store10": 0.30},       # 상설 BEST 재고비중 30%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   {"Outer": 0.30, "Top": 0.30, "Bottom": 0.20, "Skirt": 0.10, "Dress": 0.10}
    },

    # 지표별 최종 가중치 (총점 산출용): dis=40점, fresh=15점, sea=15점, best=30점
    "weight_discount":  0.40,
    "weight_freshness": 0.15,
    "weight_season":    0.15,
    "weight_best":      0.30,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────
# 신규: 스포츠/정상 매장 파라미터
# ──────────────────────────────────────────────────────
_SPORTS_NORMAL_BASE = {
    "zoning": "스포츠",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.15},
        "fresh":  {"new": 0.70},           # 기획 0% → 점수 산출 제외
        "best":   {"store10": 0.35},       # 정상 BEST 재고비중 35%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   {"RunningShoes": 0.45, "CasualShoes": 0.30, "OtherShoes": 0.10, "Top": 0.10, "Bottom": 0.05}
    },
    "weight_discount":  0.30,
    "weight_freshness": 0.20,
    "weight_season":    0.15,
    "weight_best":      0.35,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────
# 신규: 스포츠/상설 매장 파라미터
# ──────────────────────────────────────────────────────
_SPORTS_OUTLET_BASE = {
    "zoning": "스포츠",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10},
        "fresh":  {"new": 0.10, "plan": 0.20},
        "best":   {"store10": 0.30},       # 상설 BEST 재고비중 30%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   {"Top": 0.55, "Bottom": 0.25, "RunningShoes": 0.12, "CasualShoes": 0.05, "OtherShoes": 0.03}
    },
    "weight_discount":  0.40,
    "weight_freshness": 0.15,
    "weight_season":    0.15,
    "weight_best":      0.30,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────
# 신규: 아웃도어/정상 매장 파라미터 (블랙야크 정상 등)
# ──────────────────────────────────────────────────────
_OUTDOOR_NORMAL_BASE = {
    "zoning": "아웃도어",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.15},
        "fresh":  {"new": 0.70},           # 정상 신상 목표 비중 70%
        "best":   {"store10": 0.35},       # 정상 BEST 재고비중 35%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   {"Outer": 0.40, "Top": 0.40, "Bottom": 0.20}
    },
    "weight_discount":  0.30,
    "weight_freshness": 0.20,
    "weight_season":    0.15,
    "weight_best":      0.35,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────
# 신규: 아웃도어/상설 매장 파라미터 (네파, 블랙야크 등)
# ──────────────────────────────────────────────────────
_OUTDOOR_OUTLET_BASE = {
    "zoning": "아웃도어",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10},
        "fresh":  {"new": 0.10, "plan": 0.20},
        "best":   {"store10": 0.30},       # 상설 BEST 재고비중 30%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   {"Outer": 0.40, "Top": 0.40, "Bottom": 0.20}
    },
    "weight_discount":  0.40,
    "weight_freshness": 0.15,
    "weight_season":    0.15,
    "weight_best":      0.30,
    "weight_item":      0.00,
}


# ──────────────────────────────────────────────────────
# 신규: 아동/상설 매장 파라미터
# ──────────────────────────────────────────────────────
_KIDS_OUTLET_BASE = {
    "zoning": "아동",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10},
        "fresh":  {"new": 0.10, "plan": 0.20},
        "best":   {"store10": 0.30},       # 상설 BEST 재고비중 30%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   _ITEM_KIDS
    },
    "weight_discount":  0.40,
    "weight_freshness": 0.15,
    "weight_season":    0.15,
    "weight_best":      0.30,
    "weight_item":      0.00,
}

_KIDS_NORMAL_BASE = {
    "zoning": "아동",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s0": 0.70, "s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.15},
        "fresh":  {"new": 0.70},           # 기획 0% → 점수 산출 제외
        "best":   {"store10": 0.35},       # 정상 BEST 재고비중 35%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   _ITEM_KIDS
    },
    "weight_discount":  0.30,
    "weight_freshness": 0.20,
    "weight_season":    0.15,
    "weight_best":      0.35,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────

# 신규: 남성복/정상 매장 파라미터 (스포츠와 가중치 동일 설정)
# ──────────────────────────────────────────────────────
_MENS_NORMAL_BASE = {
    "zoning": "남성",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s0": 0.70, "s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.15},
        "fresh":  {"new": 0.70},
        "best":   {"store10": 0.35},       # 정상 BEST 재고비중 35%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   _ITEM_MENS
    },
    "weight_discount":  0.30,
    "weight_freshness": 0.20,
    "weight_season":    0.15,
    "weight_best":      0.35,
    "weight_item":      0.00,
}

# ──────────────────────────────────────────────────────
# 신규: 남성복/상설 매장 파라미터
# ──────────────────────────────────────────────────────
_MENS_OUTLET_BASE = {
    "zoning": "남성",
    "year_base": 2026,
    "inv_weights": {
        "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10},
        "fresh":  {"new": 0.10, "plan": 0.20},
        "best":   {"store10": 0.30},       # 상설 BEST 재고비중 30%
        "season": {"spring": 0.50, "summer": 0.25, "autumn": 0.00, "winter": 0.00},
        "item":   _ITEM_MENS
    },
    "weight_discount":  0.40,
    "weight_freshness": 0.15,
    "weight_season":    0.15,
    "weight_best":      0.30,
    "weight_item":      0.00,
}

# ══════════════════════════════════════════════════════
# 메인 설정 딕셔너리
# 키 형식: "{카테고리}_{매장유형}_{브랜드명}" 또는 "{카테고리}_{매장유형}"
# ══════════════════════════════════════════════════════
SCORING_CONFIG = {
    "여성_정상": _WOMEN_NORMAL_BASE,
    "여성_상설": _WOMEN_OUTLET_BASE,
    "기본_설정": _WOMEN_OUTLET_BASE,   # None 반환 방지용 최종 fallback

    # ── 로엠
    "여성_정상_로엠": {**_WOMEN_NORMAL_BASE, "brand_name": "로엠", "zoning": "캐릭터", "eness_name": "로엠(ROEM)", "inv_weights": {**_WOMEN_NORMAL_BASE["inv_weights"], "item": _ITEM_CHARACTER}},
    "여성_상설_로엠": {**_WOMEN_OUTLET_BASE, "brand_name": "로엠", "zoning": "캐릭터", "eness_name": "로엠(ROEM)", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},

    # ── 미쏘
    "여성_정상_미쏘": {**_WOMEN_NORMAL_BASE, "brand_name": "미쏘", "zoning": "캐주얼", "eness_name": "미쏘", "inv_weights": {**_WOMEN_NORMAL_BASE["inv_weights"], "item": _ITEM_CASUAL}},

    # ── 인동팩토리(리스트,쉬즈미스)
    "여성_상설_인동팩토리(리스트,쉬즈미스)": {
        **_WOMEN_OUTLET_BASE,
        "brand_name": "인동팩토리(리스트,쉬즈미스)",
        "zoning": "캐주얼",
        "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CASUAL}
    },

    # ── JJ지고트
    "여성_상설_JJ지고트": {**_WOMEN_OUTLET_BASE, "brand_name": "JJ지고트", "zoning": "캐릭터", "eness_name": "JJ지고트", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},

    # ── 나이스클랍
    "여성_상설_나이스클랍": {**_WOMEN_OUTLET_BASE, "brand_name": "나이스클랍", "zoning": "캐릭터", "eness_name": "나이스클랍", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},

    # ── 바바팩토리
    "여성_상설_바바팩토리": {**_WOMEN_OUTLET_BASE, "brand_name": "바바팩토리", "zoning": "시니어", "eness_name": "바바팩토리", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_SENIOR}},

    # ── 미샤팩토리
    "여성_상설_미샤팩토리": {**_WOMEN_OUTLET_BASE, "brand_name": "미샤팩토리", "zoning": "캐릭터", "eness_name": "-", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},

    # ── 베네통
    "여성_상설_베네통": {**_WOMEN_OUTLET_BASE, "brand_name": "베네통", "zoning": "캐릭터", "eness_name": "베네통(영캐주얼)", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},

    # ── 시슬리
    "여성_상설_시슬리": {**_WOMEN_OUTLET_BASE, "brand_name": "시슬리", "zoning": "캐주얼", "eness_name": "시슬리(영캐주얼)", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CASUAL}},

    # ── 신규 신구로점 브랜드
    "여성_정상_클라비스": {**_WOMEN_NORMAL_BASE, "brand_name": "클라비스", "zoning": "캐릭터", "eness_name": "클라비스(CLOVIS)", "inv_weights": {**_WOMEN_NORMAL_BASE["inv_weights"], "item": _ITEM_CHARACTER}},
    "여성_상설_더아이잗": {**_WOMEN_OUTLET_BASE, "brand_name": "더아이잗", "zoning": "캐릭터", "eness_name": "더아이잗", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},
    "여성_상설_비씨비지": {**_WOMEN_OUTLET_BASE, "brand_name": "비씨비지", "zoning": "커리어", "eness_name": "비씨비지", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CAREER}},
    "여성_상설_발렌시아": {**_WOMEN_OUTLET_BASE, "brand_name": "발렌시아", "zoning": "커리어", "eness_name": "발렌시아", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CAREER}},
    "여성_상설_베스띠벨리": {**_WOMEN_OUTLET_BASE, "brand_name": "베스띠벨리", "zoning": "커리어", "eness_name": "베스띠벨리", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CAREER}},
    "여성_상설_올리비아로렌": {**_WOMEN_OUTLET_BASE, "brand_name": "올리비아로렌", "zoning": "커리어", "eness_name": "올리비아로렌", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CAREER}},
    "여성_상설_제시뉴욕": {**_WOMEN_OUTLET_BASE, "brand_name": "제시뉴욕", "zoning": "커리어", "eness_name": "제시뉴욕", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CAREER}},
    "여성_상설_에잇컨셉": {**_WOMEN_OUTLET_BASE, "brand_name": "에잇컨셉", "zoning": "캐주얼", "eness_name": "에잇컨셉", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CASUAL}},
    "여성_상설_샤틴": {**_WOMEN_OUTLET_BASE, "brand_name": "샤틴", "zoning": "캐주얼", "eness_name": "샤틴", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CASUAL}},
    "여성_상설_보니스팍스": {**_WOMEN_OUTLET_BASE, "brand_name": "보니스팍스", "zoning": "캐릭터", "eness_name": "보니스팍스", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},
    "여성_상설_안지크": {**_WOMEN_OUTLET_BASE, "brand_name": "안지크", "zoning": "커리어", "eness_name": "안지크", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CAREER}},
    "여성_상설_플라스틱아일랜드": {**_WOMEN_OUTLET_BASE, "brand_name": "플라스틱아일랜드", "zoning": "캐주얼", "eness_name": "플라스틱아일랜드", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CASUAL}},
    
    # ── 추가 지점 브랜드
    "여성_상설_리스트": {**_WOMEN_OUTLET_BASE, "brand_name": "리스트", "zoning": "캐주얼", "eness_name": "리스트", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CASUAL}},
    "여성_상설_쉬즈미스": {**_WOMEN_OUTLET_BASE, "brand_name": "쉬즈미스", "zoning": "캐릭터", "eness_name": "쉬즈미스", "inv_weights": {**_WOMEN_OUTLET_BASE["inv_weights"], "item": _ITEM_CHARACTER}},

    # ── 지오지아
    "남성_상설_지오지아": {**_MENS_OUTLET_BASE, "brand_name": "지오지아", "zoning": "남성", "eness_name": "지오지아", "inv_weights": {**_MENS_OUTLET_BASE["inv_weights"], "item": _ITEM_MENS}},
    "남성_상설_지오지아팩토리": {**_MENS_OUTLET_BASE, "brand_name": "지오지아팩토리", "zoning": "남성", "eness_name": "지오지아팩토리", "inv_weights": {**_MENS_OUTLET_BASE["inv_weights"], "item": _ITEM_MENS}},

    # ── 스케쳐스
    "스포츠_상설_스케쳐스": {**_SPORTS_OUTLET_BASE, "brand_name": "스케쳐스", "zoning": "스포츠", "eness_name": "스케쳐스"},

    # ── 폴햄키즈
    "아동_정상_폴햄키즈": {**_KIDS_NORMAL_BASE, "brand_name": "폴햄키즈", "zoning": "아동", "eness_name": "폴햄키즈"},
}

def get_category_guide() -> dict:
    """대시보드 i버튼 로직 패널용 — 카테고리별 정상·상설 채점 가이드 반환."""
    def _sw(cfg):
        return {
            "dis":   round(cfg.get('weight_discount',  0) * 100),
            "fresh": round(cfg.get('weight_freshness', 0) * 100),
            "sea":   round(cfg.get('weight_season',    0) * 100),
            "best":  round(cfg.get('weight_best',      0) * 100),
            "item":  round(cfg.get('weight_item',      0) * 100),
        }
    def _iw(d):
        return {k: round(v * 100) for k, v in d.items() if v > 0}
    def _dw(cfg, key):
        return {k: round(v * 100) for k, v in cfg['inv_weights'].get(key, {}).items() if v > 0}
    def _bp(cfg):
        return round(cfg['inv_weights'].get('best', {}).get('store10', 0) * 100)

    def _store(cfg):
        return {
            "score_weights": _sw(cfg),
            "dis_w":   _dw(cfg, 'dis'),
            "fresh_w": _dw(cfg, 'fresh'),
            "sea_w":   _dw(cfg, 'season'),
            "best_pct": _bp(cfg),
        }

    guide = {
        "여성": {
            "normal": _store(_WOMEN_NORMAL_BASE),
            "outlet": _store(_WOMEN_OUTLET_BASE),
            "zonings": {
                "커리어": _iw(_ITEM_CAREER),
                "캐주얼": _iw(_ITEM_CASUAL),
                "캐릭터": _iw(_ITEM_CHARACTER),
                "시니어": _iw(_ITEM_SENIOR),
            },
        },
        "아동": {
            "normal": _store(_KIDS_NORMAL_BASE),
            "outlet": _store(_KIDS_OUTLET_BASE),
            "zonings": {"아동": _iw(_ITEM_KIDS)},
        },
        "신사": {
            "normal": _store(_MENS_NORMAL_BASE),
            "outlet": _store(_MENS_OUTLET_BASE),
            "zonings": {"남성": _iw(_ITEM_MENS)},
        },
        "스포츠": {
            "normal": _store(_SPORTS_NORMAL_BASE),
            "outlet": _store(_SPORTS_OUTLET_BASE),
            "zonings": {
                "스포츠(정상)": _iw(_SPORTS_NORMAL_BASE['inv_weights']['item']),
                "스포츠(상설)": _iw(_SPORTS_OUTLET_BASE['inv_weights']['item']),
            },
        },
    }
    for cat in ("캐주얼", "잡화", "전체"):
        guide[cat] = guide["여성"]
    return guide


def get_weights_by_category(category: str, store_type: str, brand_name: str = "") -> dict:
    """
    category_group 및 store_type에 따른 기본 가중치/설정 딕셔너리를 반환.
    브랜드 개별 설정(SCORING_CONFIG)이 없을 때 사용되는 베이스라인 설정입니다.
    """
    _st = str(store_type).strip().lower()
    is_outlet = any(k in _st for k in ("상설", "outlet", "아울렛", "팩토리", "factory", "복합")) or _st.startswith("상")
    
    if category == '스포츠':
        # [v3.6] 아웃도어 브랜드는 전용 가중치(Outer 포함) 적용
        from config.brand_metadata import get_brand_zoning
        zoning = get_brand_zoning(brand_name)
        if zoning == "아웃도어":
            return _OUTDOOR_OUTLET_BASE if is_outlet else _OUTDOOR_NORMAL_BASE
        return _SPORTS_OUTLET_BASE if is_outlet else _SPORTS_NORMAL_BASE
    elif '남성' in category:
        return _MENS_OUTLET_BASE if is_outlet else _MENS_NORMAL_BASE
    elif '아동' in category or '토들러' in category:
        return _KIDS_OUTLET_BASE if is_outlet else _KIDS_NORMAL_BASE
    else:
        return _WOMEN_OUTLET_BASE if is_outlet else _WOMEN_NORMAL_BASE
