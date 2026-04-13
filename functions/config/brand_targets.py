"""
brand_targets.py — 브랜드별 목표 매출 설정
============================================
단위: 원 (raw) → get_tm() 호출 시 M(백만원)으로 자동 변환 (소수 1자리)

우선순위:
  1. 월별 + 지점별 설정  (MONTHLY_TM)
  2. 지점별 기본값       (STORE_BRAND_TM)
  3. 브랜드 기본값       (BRAND_DEFAULT_TM)
  4. 전체 기본값         (DEFAULT_TM)

월 키 형식: "YYYY_MM"  (예: "2026_04")
월 문자열 "4월", "26년 4월", "2026-04" 등을 자동 정규화합니다.
"""

import re
from datetime import datetime

# ══════════════════════════════════════════════════════
# 1. 월별 목표 매출 (단위: 원)
# ══════════════════════════════════════════════════════
MONTHLY_TM = {
    "NC신구로점": {
        "2026_04": {
            "인동팩토리(리스트,쉬즈미스)": 47_141_380,
            "미샤팩토리": 54_821_975,
            "로엠":        26_559_325,
            "미쏘":        48_364_615,
            "베네통":      81_901_950,
            "시슬리":      43_449_640,
            "JJ지고트":   57_408_754,
            "나이스클랍": 24_596_637,
            "바바팩토리": 59_040_540,
        },
        # 다음 달 데이터 추가 시 아래 블록을 복사해서 사용
        # "2026_05": {
        #     "브랜드명": 원단위_금액,
        # },
    },
    # 다른 지점 추가 시:
    # "NC강서점": {
    #     "2026_04": { ... },
    # },
}

# ══════════════════════════════════════════════════════
# 2. 지점별 기본값 (월 미지정 fallback, 단위: M 백만원)
# ══════════════════════════════════════════════════════
STORE_BRAND_TM = {
    "NC신구로점": {
        "로엠":        27,
        "미쏘":        48,
        "미샤팩토리":  55,
        "인동팩토리(리스트,쉬즈미스)":  47,
        "베네통":      82,
        "시슬리":      43,
        "JJ지고트":   57,
        "나이스클랍":  25,
        "바바팩토리":  59,
    },
    "NC강서점": {
        "로엠": 85,
        "미쏘": 70,
    },
}

# ══════════════════════════════════════════════════════
# 3. 브랜드 공통 기본값 (단위: M 백만원)
# ══════════════════════════════════════════════════════
BRAND_DEFAULT_TM = {
    "로엠":        27,
    "미쏘":        48,
    "미샤팩토리":  55,
    "인동팩토리(리스트,쉬즈미스)":  47,
    "베네통":      82,
    "시슬리":      43,
    "JJ지고트":   57,
    "나이스클랍":  25,
    "바바팩토리":  59,
}

# 최종 fallback
DEFAULT_TM = 50


# ══════════════════════════════════════════════════════
# 유틸 함수
# ══════════════════════════════════════════════════════

def _normalize_month_key(month: str) -> str | None:
    """
    다양한 월 표현을 "YYYY_MM" 키로 정규화합니다.
    예)  "4월"       → "2026_04"  (현재 연도 기준)
         "26년 4월"  → "2026_04"
         "2026-04"  → "2026_04"
         "2026_04"  → "2026_04"
    """
    if not month:
        return None

    s = str(month).strip()

    # 이미 YYYY_MM 형식
    m = re.fullmatch(r'(\d{4})_(\d{1,2})', s)
    if m:
        return f"{m.group(1)}_{int(m.group(2)):02d}"

    # YYYY-MM 또는 YYYY/MM
    m = re.fullmatch(r'(\d{4})[-/](\d{1,2})', s)
    if m:
        return f"{m.group(1)}_{int(m.group(2)):02d}"

    # YY년 M월 또는 YYYY년 M월
    m = re.search(r'(\d{2,4})년\s*(\d{1,2})월', s)
    if m:
        yr = int(m.group(1))
        if yr < 100:
            yr += 2000
        return f"{yr}_{int(m.group(2)):02d}"

    # M월 (연도 없음 → 현재 연도)
    m = re.fullmatch(r'(\d{1,2})월', s)
    if m:
        yr = datetime.now().year
        return f"{yr}_{int(m.group(1)):02d}"

    return None


def get_tm(brand_name: str, store_name: str = None, month: str = None) -> float:
    """
    브랜드 + 지점 + 월 조합으로 목표 매출(tM)을 반환합니다.
    반환 단위: 원 (Raw Won), 정밀 계산용
    """
    # 1순위: 월별 지점 설정 (원 단위 직접 반환)
    if store_name and month:
        key = _normalize_month_key(month)
        if key:
            val = MONTHLY_TM.get(store_name, {}).get(key, {}).get(brand_name)
            if val:
                return float(val)

    # 2순위: 지점별 기본값 (M 단위 → 원 변환)
    if store_name and store_name in STORE_BRAND_TM:
        val = STORE_BRAND_TM[store_name].get(brand_name)
        if val is not None:
            return float(val) * 1_000_000

    # 3순위: 브랜드 기본값
    if brand_name in BRAND_DEFAULT_TM:
        return float(BRAND_DEFAULT_TM[brand_name]) * 1_000_000

    # 4순위: 전체 기본값
    return float(DEFAULT_TM) * 1_000_000


def get_tm_m(brand_name: str, store_name: str = None, month: str = None) -> float:
    """
    기존 호환성용: 백만원(M) 단위 반환 (소수 1자리 반올림)
    """
    won = get_tm(brand_name, store_name, month)
    return round(won / 1_000_000, 1)
