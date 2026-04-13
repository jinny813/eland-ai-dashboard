"""
config/scoring_config.py
========================
[버전] v5 — 최종 재고 로직 완결본 (목표 달성률 기반)

■ 구조:
  - _WOMEN_NORMAL_BASE : 여성/정상 매장 공통 파라미터
  - _WOMEN_OUTLET_BASE : 여성/상설 매장 공통 파라미터
  - SCORING_CONFIG     : 브랜드별 개별 설정 딕셔너리 (메인 진입점)

■ 핵심 진단 원칙:
  - 목표 재고액(Target) = 목표 매출 * 2.0
  - 점수(Score) = (실제 재고액 / 목표 재고액) * 100 (Max 100)
"""

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

    # ── 최종 재고 로직 (v5) 목표 비중
    "inv_weights": {
        "dis":    {"s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.05, "normal": 0.10}, # 5단계 할인율 (총 합 0.30 대비 비중)
        "fresh":  {"new": 0.70, "off":  0.30, "plan": 0.00},
        "best":   {"store10": 0.25},
        "season": {"current": 0.70},
    },

    # 지표별 최종 가중치 (총점 산출용 - 사용자 확정)
    "weight_discount":  0.30,
    "weight_freshness": 0.20,
    "weight_season":    0.20,
    "weight_best":      0.30,
}

# ──────────────────────────────────────────────────────
# 공통: 여성/상설 매장 파라미터
# ──────────────────────────────────────────────────────
_WOMEN_OUTLET_BASE = {
    "bp_freshness_target": 10.0,
    "year_base": 2026,

    # ── 최종 재고 로직 (v5) 목표 비중
    "inv_weights": {
        "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10}, 
        "fresh":  {"new": 0.10, "off":  0.70, "plan": 0.20},
        "best":   {"store10": 0.25, },
        "season": {"current": 0.70},
    },

    # 지표별 최종 가중치 (총점 산출용)
    "weight_discount":  0.45,
    "weight_freshness": 0.15,
    "weight_season":    0.15,
    "weight_best":      0.25,
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
    "여성_정상_로엠": {**_WOMEN_NORMAL_BASE, "brand_name": "로엠"},
    "여성_상설_로엠": {**_WOMEN_OUTLET_BASE, "brand_name": "로엠"},

    # ── 미쏘 — 정상 매장
    "여성_정상_미쏘": {**_WOMEN_NORMAL_BASE, "brand_name": "미쏘"},

    # ── 인동팩토리(리스트,쉬즈미스) — 상설 매장
    "여성_상설_인동팩토리(리스트,쉬즈미스)": {
        **_WOMEN_OUTLET_BASE,
        "brand_name": "인동팩토리(리스트,쉬즈미스)",
    },

    # ── JJ지고트 — 상설 매장
    "여성_상설_JJ지고트": {**_WOMEN_OUTLET_BASE, "brand_name": "JJ지고트"},

    # ── 나이스클랍 — 상설 매장
    "여성_상설_나이스클랍": {**_WOMEN_OUTLET_BASE, "brand_name": "나이스클랍"},

    # ── 바바팩토리 — 상설 매장
    "여성_상설_바바팩토리": {**_WOMEN_OUTLET_BASE, "brand_name": "바바팩토리"},

    # ── 미샤팩토리 — 상설 매장
    "여성_상설_미샤팩토리": {**_WOMEN_OUTLET_BASE, "brand_name": "미샤팩토리"},

    # ── 베네통 — 상설 매장
    "여성_상설_베네통": {**_WOMEN_OUTLET_BASE, "brand_name": "베네통"},

    # ── 시슬리 — 상설 매장
    "여성_상설_시슬리": {**_WOMEN_OUTLET_BASE, "brand_name": "시슬리"},
}
