import os
import json
import pandas as pd
from datetime import datetime, timedelta
import pandas as pd

# ── [v8.0] 다중 팔레트 기반 동적 색상 유틸리티
def _get_dynamic_color(pct: float, p_type: str = "default") -> str:
    """
    달성률(pct)에 따라 25% 구간별로 [Red, Yellow, Green, Blue] 계열 색상 반환.
    각 p_type(지표타입)별로 서로 다른 프리미엄 팔레트 적용.
    """
    # 구간 정의 (0~25: Danger, 25-50: Warning, 50-75: Success, 75+: Excellent)
    step = 0
    if pct < 25:    step = 0
    elif pct < 50:  step = 1
    elif pct < 75:  step = 2
    else:           step = 3

    # 지표별 프리미엄 팔레트 정의 ([Red, Yellow, Green, Blue] 계열 각각 4단계)
    palettes = {
        "total":  ["#F87171", "#FBBF24", "#34D399", "#60A5FA"], # 총 재고 (기본)
        "dis":    ["#EF4444", "#F97316", "#FB923C", "#FDBA74"], # 할인율 (레드/오렌지 테마)
        "fresh":  ["#D97706", "#F59E0B", "#FBBF24", "#FDE68A"], # 신선도 (옐로우/골드 테마로 변경)
        "best":   ["#8B5CF6", "#A78BFA", "#C4B5FD", "#DDD6FE"], # BEST (보라색 테마)
        "season": ["#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"], # 시즌 (블루 테마로 변경)
        "default":["#94A3B8", "#64748B", "#475569", "#334155"]
    }
    
    colors = palettes.get(p_type, palettes["default"])
    return colors[step]

from core.scoring_logic import AssortmentScorer, _is_outlet
from config.scoring_config import SCORING_CONFIG

# ──────────────────────────────────────────────
# 아이템 점수 세부 색상 팔레트
# ──────────────────────────────────────────────
ITEM_COLORS = [
    "#7C3AED","#A78BFA","#C4B5FD","#DDD6FE","#EDE9FE",
    "#6D28D9","#8B5CF6","#9F7AEA","#B794F4","#D6BCFA",
]
SEASON_COLORS = {
    "봄": "#FCD34D", "여름": "#F59E0B",
    "가을": "#D97706", "겨울": "#92400E", "사계절": "#B45309",
}

def _safe_float(v) -> float:
    try:
        if pd.isna(v): return 0.0
        return float(str(v).replace(',', '').strip())
    except:
        return 0.0

def _build_detail(df: pd.DataFrame, config: dict, tM: float = 100.0) -> dict:
    """각 지표의 실제 세부 구성 비중을 계산해서 대시보드용 dict 반환"""
    if df is None or df.empty:
        return {}

    df = df.copy()
    # 수치형 변환 보장
    df['_amt'] = df['stock_amt'].apply(_safe_float)
    df['_qty'] = df['stock_qty'].apply(_safe_float) if 'stock_qty' in df.columns else 0

    total_amt = df['_amt'].sum()
    total_qty = df['_qty'].sum()
    if total_amt <= 0:
        return {}

    # [v45.5] 연차(Age) 계산 시 기준 연도 동적 추출
    def _get_year_base_sync():
        try:
            if 'year' in df.columns:
                years = pd.to_numeric(df['year'].astype(str).str.replace('년','').strip(), errors='coerce')
                return int(years.max())
            return 2026
        except: return 2026
    
    year_base = _get_year_base_sync()
    inv_w = config.get('inv_weights', {})
    target_total = tM * 2.0  # 목표 재고액 (원 단위)

    # 1. 신상품 비중 (신선도 지표에서 가져옴)
    target_new_ratio = inv_w.get('fresh', {}).get('new', 0.70)
    target_remain_total = target_total * (1.0 - target_new_ratio)

    def _seg_extra(group_key: str, seg_key: str, actual_amt: float = 0.0) -> dict:
        """weight, targetM, pct를 계산해 반환"""
        w = inv_w.get(group_key, {}).get(seg_key, 0.0)
        base = target_remain_total if group_key == 'dis' else target_total
        target_amt_won = base * w
        
        # 달성률(pct) 계산 로직 (중복 곱셈 제거)
        pct = 0.0
        if target_amt_won > 0:
            pct = (actual_amt / target_amt_won * 100)
        elif target_amt_won == 0:
            pct = 100.0 if actual_amt <= 0 else 0.0
            
        return {"weight": w, "targetM": round(target_amt_won / 1_000_000, 1), "pct": round(pct, 1)}

    # 1. 아이템 점수 세부
    item_segs = []
    if 'item_name' in df.columns:
        item_grp = df.groupby('item_name').agg(
            valM=('_amt', 'sum'), qty=('_qty', 'sum')
        ).reset_index().sort_values('valM', ascending=False).head(10)
        for i, row in item_grp.iterrows():
            item_segs.append({
                "key":  str(row['item_name']),
                "l":    str(row['item_name']),
                "valM": round(float(row['valM']) / 1_000_000, 2),
                "qty":  int(row['qty']),
                "c":    ITEM_COLORS[len(item_segs) % len(ITEM_COLORS)],
            })

    # 2. 할인율 세부
    def get_age(y):
        try:
            y_num = int(str(y).replace('년','').strip())
            if y_num < 100: y_num += 2000
            return max(0, year_base - y_num)
        except:
            return 0

    # 2. 할인율 세부 — [v8.0 동적 색상 적용]
    def get_age_sync(y):
        try:
            val = str(y).replace('년','').strip()
            y_num = int(val)
            if y_num < 100: y_num += 2000
            return max(0, year_base - y_num)
        except: return 0

    if 'year' in df.columns:
        df['_age'] = df['year'].apply(get_age_sync)
        
        # [v16.4] 누락된 store_type 선언부 복구
        store_type = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
        outlet = _is_outlet(store_type)   # '상', '상설' 모두 True
        
        # [v16.5] _gen_insight 공통 함수 복구
        def _gen_insight(segs):
            diffs = []
            for s in segs:
                if s.get('opt_pct', 0) > 0 and 'mix_pct' in s:
                    diff = s['mix_pct'] - s['opt_pct']
                    diffs.append((diff, s['l'], s['opt_pct']))
            if not diffs: return "재고 믹스가 지침과 유사합니다."
            max_diff = max(diffs, key=lambda x: abs(x[0]))
            status = "많습니다" if max_diff[0] > 0 else "적습니다"
            return f"현재 {max_diff[1]} 비중이 최적 지침({max_diff[2]}%) 대비 {abs(max_diff[0]):.1f}%p {status}."

        # [v22.1] 정밀 재고 집계 헬퍼 함수 (데이터 타입 정규화 강화)
        def _get_stock_ref(mask):
            sub = df[mask]
            if sub.empty: return sub
            if 'inv_uid' in sub.columns and sub['inv_uid'].notna().any():
                return sub.drop_duplicates('inv_uid')
            
            if outlet:
                # 상설 매장: inv_uid가 없으면 모든 데이터 합산 (중복 제거 생략)
                return sub
            else:
                # 정상 매장: 기존 기준 컬럼으로 중복 제거
                d_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
                return sub.drop_duplicates(subset=[c for c in d_cols if c in sub.columns])

        # 할인율 지표 최적 비중 동기화 (v22.1: 정수형 변환 필터 적용)
        df['_age_int'] = df['_age'].round().fillna(-1).astype(int)
        age_0_f = (df['_age_int'] == 0)
        age_1_f = (df['_age_int'] == 1)
        age_2_f = (df['_age_int'] == 2)
        age_3_f = (df['_age_int'] == 3)
        age_4_f = (df['_age_int'] >= 4)
        
        dis_total_amt = _get_stock_ref(age_0_f | age_1_f | age_2_f | age_3_f | age_4_f)['_amt'].sum() or 1

        def _get_dis_item_sync(key, label, age_filter, target_ratio, ui_weight):
            ref = _get_stock_ref(age_filter)
            actual_amt = ref['_amt'].sum()
            mix_pct = round((actual_amt / dis_total_amt) * 100, 1)
            
            # [v45.5] 목표액 정밀 계산 (중복 곱셈 제거)
            target_amt_won = target_total * target_ratio
            if target_amt_won > 0:
                pct = round((actual_amt / target_amt_won) * 100, 1)
            else:
                pct = 100.0 if actual_amt <= 0 else 0.0
            
            vivid_red = '#FF2D55'
            item_color = '#CBD5E1' if target_ratio <= 0 else vivid_red
            
            return {
                "key": key, "l": label, "valM": round(actual_amt/1_000_000, 1),
                "qty": int(ref['_qty'].sum()),
                "c": item_color,
                "weight": ui_weight,
                "pct": pct,
                "targetM": round(target_amt_won / 1_000_000, 1),
                "mix_pct": mix_pct, "opt_pct": target_ratio * 100
            }

        # [v27.3] 매장 유형별 할인율 세그먼트 비중 동기화 (상설: 5단계 전용 매핑)
        if outlet:
            # 상설: discount_rate (U열) 직접 사용
            df['_dis_rate'] = df['discount_rate'].apply(
                AssortmentScorer._parse_discount_rate
            ) if 'discount_rate' in df.columns else 0.0
            dr = df['_dis_rate']
            dis_segs = [
                _get_dis_item_sync("d70",    "70% 이상 할인",    (dr >= 70),                     0.10, 10),
                _get_dis_item_sync("d50",    "50~70% 미만 할인", (dr >= 50) & (dr < 70),         0.20, 20),
                _get_dis_item_sync("d30",    "30~50% 미만 할인", (dr >= 30) & (dr < 50),         0.30, 30),
                _get_dis_item_sync("d10",    "1~30% 미만 할인",  (dr > 0) & (dr < 30),           0.10, 10),
            ]
        else:
            # 정상: age 기반 매핑 — 70%+(0), 50%+(5), 30%+(10), 1-30%(15)
            dis_segs = [
                _get_dis_item_sync("age_4", "70% 이상 할인", age_4_f, 0.00,  0),
                _get_dis_item_sync("age_3", "50~70% 미만 할인", age_3_f, 0.05,  5),
                _get_dis_item_sync("age_2", "30~50% 미만 할인", age_2_f, 0.10, 10),
                _get_dis_item_sync("age_1", "1~30% 미만 할인",  age_1_f, 0.15, 15),
            ]
        dis_insight = _gen_insight(dis_segs)
    else:
        dis_segs = []
        dis_insight = ""

    # 3. 신선도 세부 (상설: 신상10%, 기획20%, 시즌오프70% / 정상: 신상70%, 시즌오프30%)
    fresh_total_amt = _get_stock_ref(df['_age'].notna())['_amt'].sum() or 1
    
    def _get_fresh_item(key, label, mask, opt_weight):
        ref = _get_stock_ref(mask)
        amt = ref['_amt'].sum()
        extra = _seg_extra("fresh", key, actual_amt=amt)
        mix_pct = round((amt / fresh_total_amt) * 100, 1)
        return {
            "key": key, "l": label, "valM": round(amt/1_000_000, 1),
            "qty": int(ref['_qty'].sum()), "c": _get_dynamic_color(extra.get("pct", 0), "fresh"),
            "weight": opt_weight, # weight 필드는 목표 비중% 로 표시
            "mix_pct": mix_pct, "opt_pct": opt_weight,
            **extra,
            "pct": min(100.0, extra.get("pct", 0)) # 달성률 100% 캡
        }

    # [v27.3] 신선도 판별 로직 동기화 (상설 매장 전용 레이블 명시 - 포함 조건으로 유연성 확보)
    if outlet:
        ft = df['freshness_type'].astype(str).str.strip().str.upper() if 'freshness_type' in df.columns else pd.Series([''] * len(df))
        fresh_segs = [
            _get_fresh_item("new",  "신상 (New)", ft.str.contains('신상|NEW', na=False),   10),
            _get_fresh_item("plan", "기획 상품",  ft.str.contains('기획', na=False),       20),
            _get_fresh_item("off",  "시즌 OFF",   ft.str.contains('OFF|이월|시즌', na=False), 70),
        ]
    else:
        # 정상: year/age 기반
        is_plan = df['price_type'].astype(str).str.contains('균일|기획', na=False)
        is_new  = (df['_age_int'] == 0) & (~is_plan)
        is_off  = (df['_age_int'] >= 1) & (~is_plan)
        fresh_segs = [
            _get_fresh_item("new", "신상 (New)", is_new, 70),
            _get_fresh_item("off", "시즌 OFF",   is_off, 30),
        ]
    fresh_insight = _gen_insight(fresh_segs)

    # 4. 시즌 세부 (목표 비중 70% 고정)
    def _get_sea_sync_final(key, label, codes, weight, color, is_active):
        # [v74.5] 시즌 코드 매칭 시 포함 조건 사용
        if outlet:
            mask = df['season_code'].astype(str).str.contains('|'.join(codes), na=False) if 'season_code' in df.columns else pd.Series([False]*len(df))
        else:
            mask = df['_s_code'].isin(codes) if '_s_code' in df.columns else pd.Series([False]*len(df))
            
        ref = _get_stock_ref(mask)
        actual_amt = ref['_amt'].sum() if not ref.empty else 0
        
        target_amt_won = target_total * 0.70 # 상설/정상 공통 시즌 목표 70%
        pct = min(100.0, round((actual_amt / target_amt_won) * 100, 1)) if target_amt_won > 0 else (100.0 if actual_amt==0 else 0)
        mix_pct = round((actual_amt / total_amt * 100), 1) if total_amt > 0 else 0
        
        return {
            "key": key, "l": label,
            "valM": round(actual_amt/1_000_000, 1),
            "qty": int(ref['_qty'].sum()) if not ref.empty else 0,
            "c": color if is_active else "#94A3B8", 
            "weight": 70, "pct": pct, "targetM": round(target_amt_won / 1_000_000, 1),
            "mix_pct": mix_pct, "opt_pct": 70,
            "is_score_target": is_active 
        }

    season_segs = []
    if 'season_code' in df.columns:
        curr_month = datetime.now().month
        is_ss_now = (2 <= curr_month <= 7)
        df['_s_code'] = df['season_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        if outlet:
            # 상설: season_code 한글값 ('봄','여름','가을','겨울') 직접 매칭
            season_segs = [
                _get_sea_sync_final("ss_s", "봄 (SS)",  ['봄'],    35 if is_ss_now else 15, "#FCD34D", is_ss_now),
                _get_sea_sync_final("ss_m", "여름 (SS)", ['여름'],  35 if is_ss_now else 15, "#F59E0B", is_ss_now),
                _get_sea_sync_final("fw_f", "가을 (FW)", ['가을'],  15 if is_ss_now else 35, "#D97706", not is_ss_now),
                _get_sea_sync_final("fw_w", "겨울 (FW)", ['겨울'],  15 if is_ss_now else 35, "#007AFF", not is_ss_now),
            ]
        else:
            # 정상: 숫자 season_code ('1','2','3','4','9')
            season_segs = [
                _get_sea_sync_final("ss_s", "봄 (SS)",  ['1', '9'], 35 if is_ss_now else 15, "#FCD34D", is_ss_now),
                _get_sea_sync_final("ss_m", "여름 (SS)", ['2', '9'], 35 if is_ss_now else 15, "#F59E0B", is_ss_now),
                _get_sea_sync_final("fw_f", "가을 (FW)", ['3', '9'], 15 if is_ss_now else 35, "#D97706", not is_ss_now),
                _get_sea_sync_final("fw_w", "겨울 (FW)", ['4', '9'], 15 if is_ss_now else 35, "#007AFF", not is_ss_now),
            ]
    season_insight = _gen_insight([s for s in season_segs if s.get('is_score_target')]) if season_segs else ""

    # 5. BEST 세부 (상설인 경우 날짜 필터 무시하고 전체 sales_qty 기준 집계)
    best_segs = []
    best_insight = ""
    if 'sales_qty' in df.columns and 'style_code' in df.columns:
        if outlet:
            # 상설 매장: 날짜 구분 없이 현재 데이터의 전체 판매량 합계 기준
            sales_agg = df.assign(_sq=pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)).groupby('style_code')['_sq'].sum().reset_index()
            top10_styles = sales_agg.nlargest(10, '_sq', keep='all')['style_code'].tolist()
        else:
            # 정상 매장: 최근 14일 기준 유지
            df['_sale_dt_obj'] = pd.to_datetime(df['sales_date'], errors='coerce')
            max_dt = df['_sale_dt_obj'].max()
            if pd.notna(max_dt):
                cutoff = max_dt - timedelta(days=14)
                recent_sales_df = df[df['_sale_dt_obj'] >= cutoff].copy()
            else:
                recent_sales_df = df.copy()
            sales_agg = recent_sales_df.groupby('style_code')['sales_qty'].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).reset_index()
            top10_styles = sales_agg.nlargest(10, 'sales_qty', keep='all')['style_code'].tolist()
        
        # 중복 제거된 고유 재고 기준으로 합산
        style_mask = df['style_code'].astype(str).str.strip().str.upper().isin([str(s).strip().upper() for s in top10_styles])
        ref_best = _get_stock_ref(style_mask)
        best_amt = ref_best['_amt'].sum()

        target_amt_won = target_total * 0.25
        best_segs = [{
            "key": "best", "l": "매장 판매 BEST 10", "valM": round(best_amt/1_000_000, 1),
            "qty": int(ref_best['_qty'].sum()),
            "c": "#8B5CF6", "weight": 25, "opt_weight": 25, 
            "pct": min(100.0, round((best_amt / (target_amt_won + 0.001)) * 100, 1)) if target_amt_won > 0 else 0,
            "targetM": round(target_amt_won / 1_000_000, 1),
            "mix_pct": round((best_amt / total_amt * 100), 1) if total_amt > 0 else 0, 
            "opt_pct": 25
        }]
    else:
        best_segs = [{
            "key": "best", "l": "매장 판매 BEST 10", "valM": 0, "qty": 0, "c": "#8B5CF6", "weight": 2.5, "opt_weight": 25, "pct": 0, "targetM": round(target_total * 0.25, 1), "mix_pct": 0, "opt_pct": 25
        }]
    best_insight = _gen_insight(best_segs)

    return {
        "item":   {"segs": item_segs,   "warnFn_key": "item_warn"},
        "dis":    {"segs": dis_segs,    "warnFn_key": "dis_warn", "insight": dis_insight},
        "fresh":  {"segs": fresh_segs,  "warnFn_key": "fresh_warn", "insight": fresh_insight},
        "best":   {"segs": best_segs,   "warnFn_key": "best_warn", "insight": best_insight},
        "season": {"segs": season_segs, "warnFn_key": "season_warn", "insight": season_insight},
        "total_qty_unique": int(total_qty) # [v74.3] 중복 제거된 유일 재고 수량
    }


def _build_bp_detail(config: dict, bp_df=None) -> dict:
    """BP_DETAIL 생성 (실제 BP 지점 데이터 or config 기준값 fallback)"""
    if bp_df is not None and not bp_df.empty:
        return _build_detail(bp_df, config)

    bp_item = config.get("bp_item_target", {})
    item_segs = []
    for i, (name, share) in enumerate(bp_item.items()):
        item_segs.append({
            "key": name, "l": name,
            "valM": round(share, 1),
            "qty":  0,
            "c":    ITEM_COLORS[i % len(ITEM_COLORS)],
        })

    dis_segs_bp = [
        {"key":"s70",   "l":"70% 이상", "valM":0.05,  "qty":0, "c":"#E30019"},
        {"key":"s50",   "l":"50% 이상", "valM":8.75,  "qty":0, "c":"#F97316"},
        {"key":"s30",   "l":"30% 이상", "valM":46.3,  "qty":0, "c":"#FBBF24"},
        {"key":"normal","l":"정상가",   "valM":44.9,  "qty":0, "c":"#D4D5D5"},
    ]
    fresh_target = config.get("bp_freshness_target", 70.0)
    fresh_segs_bp = [
        {"key":"new",  "l":"신상(정상)", "valM":fresh_target,              "qty":0, "c":"#1D4ED8"},
        {"key":"plan", "l":"기획 상품",  "valM":18.0,                      "qty":0, "c":"#93C5FD"},
        {"key":"off",  "l":"시즌 OFF",   "valM":round(100-fresh_target-18,1),"qty":0, "c":"#DBEAFE"},
    ]
    season_segs_bp = [
        {"key":"s1","l":"봄",     "valM":18.0, "qty":0, "c":"#FCD34D"},
        {"key":"s2","l":"여름",   "valM":52.0, "qty":0, "c":"#F59E0B"},
        {"key":"s3","l":"가을",   "valM":15.0, "qty":0, "c":"#D97706"},
        {"key":"s4","l":"겨울",   "valM":10.0, "qty":0, "c":"#92400E"},
        {"key":"s9","l":"사계절", "valM":5.0,  "qty":0, "c":"#B45309"},
    ]
    bp_best = config.get("bp_best_target", [25.0, 29.4])
    best_mid = (bp_best[0] + bp_best[1]) / 2
    best_segs_bp = [
        {"key":"store10","l":"매장 Top10","valM":best_mid,              "qty":0, "c":"#15803D"},
        {"key":"other",  "l":"그 외",     "valM":round(100-best_mid,1), "qty":0, "c":"#86EFAC"},
    ]

    return {
        "item":   {"segs": item_segs},
        "dis":    {"segs": dis_segs_bp},
        "fresh":  {"segs": fresh_segs_bp},
        "best":   {"segs": best_segs_bp},
        "season": {"segs": season_segs_bp},
    }


def _build_best_items(df) -> dict:
    """판매 Top10 — 상품코드(품번) 기준 세부 스타일별 순위 테이블 (최근 14일 기준)"""
    if df is None or df.empty or "sales_qty" not in df.columns:
        return {"store": [], "nc": []}
    
    # [v75.3] 브랜드명 추출 (인동팩토리 규칙 적용용)
    s_name = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns else ""

    def _sf(v):
        try: return float(str(v).replace(",","").strip())
        except: return 0.0

    df = df.copy()

    # [v53.0] 중복 합산 방지 고유 재고 레퍼런스 추출
    # 판매 이력(14일분)에 의한 stock_amt/stock_qty 배수 합산을 차단하기 위해
    # 먼저 전체 df에서 품번별 유일한 재고 레퍼런스를 생성합니다.
    def _get_unique_stock_ref(base_df):
        if base_df.empty: return base_df
        dedup_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
        valid_cols = [c for c in dedup_cols if c in base_df.columns]
        return base_df.drop_duplicates(subset=valid_cols) if valid_cols else base_df

    # 1. 최근 14일 판매 데이터 필터링 (판매량 합산용)
    sales_df = df.copy()
    if 'sales_date' in df.columns and df['sales_date'].notna().any():
        try:
            df['_sale_dt_obj'] = pd.to_datetime(df['sales_date'], errors='coerce')
            max_dt = df['_sale_dt_obj'].max()
            if pd.notna(max_dt):
                cutoff = max_dt - timedelta(days=14)
                sales_df = df[df['_sale_dt_obj'] >= cutoff].copy()
        except: pass

    # 2. 판매량 및 매출액 집계 (최근 14일 합계로 판매가 역산)
    sales_df["_sales"] = sales_df["sales_qty"].apply(_sf)
    sales_df["_sales_amt"] = sales_df["sales_amt"].apply(_sf) if "sales_amt" in sales_df.columns else 0
    
    sales_agg = sales_df.groupby("style_code").agg({"_sales": "sum", "_sales_amt": "sum"}).reset_index()
    # [v54.0] 판매가 실시간 연산 (금액 / 수량)
    sales_agg["_price"] = sales_agg.apply(lambda r: r["_sales_amt"] / r["_sales"] if r["_sales"] > 0 else 0, axis=1)
    
    top10_raw = sales_agg.nlargest(10, "_sales", keep="all")
    top_styles = top10_raw["style_code"].tolist()

    # 3. 재고 및 마스터 정보 집계 (품번별 고유 레코드 기준)
    # [v53.0] 판매 기록에 의한 배수 합산을 차단하기 위해 고유 레코드만 가져옵니다.
    unique_df = _get_unique_stock_ref(df[df["style_code"].isin(top_styles)])
    
    unique_df["_amt"]   = unique_df["stock_amt"].apply(_sf)
    unique_df["_qty"]   = unique_df["stock_qty"].apply(_sf) if "stock_qty" in unique_df.columns else 0

    agg_map = {"_qty": "sum", "_amt": "sum"}
    if "style_name" in unique_df.columns: agg_map["style_name"] = "first"
    if "item_name" in unique_df.columns:  agg_map["item_name"] = "first"
    if "normal_price" in unique_df.columns: agg_map["normal_price"] = "max"
    
    stock_agg = unique_df.groupby("style_code").agg(agg_map).reset_index()

    # 4. 판매량/가격과 재고 데이터 결합
    final_agg = pd.merge(top10_raw, stock_agg, on="style_code", how="left")
    
    # [v74.8] 상설 매장 전용 판매량 노출 보정 (SUM / COUNT)
    # 순위 결정 로직(top10_raw)은 그대로 유지하고, 대시보드에 표시되는 수치만 보정합니다.
    store_type = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
    if _is_outlet(store_type):
        avg_sales = sales_df.groupby("style_code")["_sales"].mean().reset_index().rename(columns={"_sales": "_sales_avg"})
        final_agg = pd.merge(final_agg, avg_sales, on="style_code", how="left")
        final_agg["_sales"] = final_agg["_sales_avg"].fillna(final_agg["_sales"])

    final_agg = final_agg.sort_values("_sales", ascending=False).reset_index(drop=True)

    # [v75.4] 순위 재계산: 보정된 판매량(_sales) 기준으로 순위 맵 생성
    # (보정 전 합계 수치 기준 맵을 참조하여 순위가 15위 등으로 꼬이는 현상 해결)
    unique_sales = sorted(final_agg["_sales"].unique(), reverse=True)
    sales_to_rank = {s: i+1 for i, s in enumerate(unique_sales)}

    store_list = []

    # [v74.9] 상설 매장 전용 스타일 정보 보완 (마스터 파일 참조)
    style_cache = {}
    master_path = os.path.join(os.path.dirname(__file__), "style_master.json")
    if os.path.exists(master_path):
        try:
            with open(master_path, "r", encoding="utf-8") as f:
                style_cache = json.load(f)
        except: pass

    for _, row in final_agg.iterrows():
        s_code = str(row["style_code"]).strip()
        style_n = str(row.get("style_name", "")).strip()
        item_n = str(row.get("item_name", "")).strip()
        
        # 상설 매장이고 정보가 부족한 경우 마스터 캐시 참조
        if _is_outlet(store_type):
            cached = style_cache.get(s_code)
            if cached:
                item_n = cached.get("item_name", item_n)
                style_n = cached.get("style_name", style_n)
            
            # [v75.1] 스타일명을 기반으로 아이템명(카테고리) 자동 추론
            if (not item_n or item_n in ["—", "nan", ""]) and style_n and style_n != "—":
                keywords = {
                    "원피스": ["원피스", "드레스", "OP"],
                    "니트": ["니트", "풀오버", "PO", "가디건", "CD"],
                    "팬츠": ["팬츠", "슬랙스", "데님", "바지", "LP", "PT"],
                    "블라우스": ["블라우스", "셔츠", "BL", "SH"],
                    "치마": ["스커트", "치마", "SK"],
                    "자켓": ["자켓", "재킷", "JK"],
                    "코트": ["코트", "CT"],
                    "티셔츠": ["티셔츠", "티", "TS", "TOP"],
                    "점퍼": ["점퍼", "JP", "다운", "패딩"]
                }
                for cat, keys in keywords.items():
                    if any(k in style_n.upper() for k in keys):
                        item_n = cat
                        break

            # [v75.2] 브랜드 프리픽스 규칙 적용
            brand_prefix = ""
            # 1. 인동팩토리 (T: 리스트, S: 쉬즈미스)
            if s_name == "인동팩토리(리스트,쉬즈미스)" or "인동팩토리" in s_name:
                if s_code.startswith("T"): brand_prefix = "리스트"
                elif s_code.startswith("S"): brand_prefix = "쉬즈미스"
            
            # 2. 바바패션 계열 (JJ지고트, 아이잗바바, 아이잗컬렉션 등)
            elif any(k in s_name for k in ["지고트", "바바", "아이잗"]) or s_code.startswith(("G", "B", "C", "N")):
                # 품번 프리픽스 기반 세부 브랜드 식별 (v75.6)
                if s_code.startswith("GS") or "제이제이지고트" in s_name:
                    brand_prefix = "JJ지고트"
                elif s_code.startswith("BN"):
                    brand_prefix = "아이잗바바"
                elif s_code.startswith(("BM", "CM", "GR")):
                    brand_prefix = "아이잗컬렉션"
                elif s_code.startswith("CN"):
                    brand_prefix = "더아이잗"
                elif "지고트" in s_name and "JJ" not in s_name:
                    brand_prefix = "지고트"
                else:
                    brand_prefix = s_name.replace("팩토리", "").replace("패션", "").strip()

            if brand_prefix:
                # [v75.7] 상품명 정규화 (브랜드 키워드 자동 제거)
                brand_keywords = ["리스트", "쉬즈미스", "제이제이지고트", "JJ지고트", "바바패션", "아이잗바바", "아이잗컬렉션", "더아이잗", "더 아이잗", "지고트"]
                clean_style = style_n
                for k in brand_keywords:
                    clean_style = clean_style.replace(k, "")
                
                clean_style = clean_style.replace("[", "").replace("]", "").strip()
                style_n = f"[{brand_prefix}] {clean_style}"

        display_style = style_n if style_n and style_n != "nan" and style_n != "—" else "—"
        display_item = item_n if item_n and item_n != "nan" and item_n != "—" else "—"
        
        # [v54.2] 판매가 결정: '#DIV/0!' 등 엑셀 오류 문자열 대응 (안전한 변환)
        calc_price = int(row.get("_price", 0))
        db_price = int(_sf(row.get("normal_price", 0)))
        final_price = calc_price if calc_price > 0 else db_price
        
        store_list.append({
            "rank":       sales_to_rank.get(row["_sales"], 1),
            "item_name":  display_item,
            "style_code": str(row["style_code"]),
            "style_name": display_style,
            "price":      final_price,
            "sales":      int(row["_sales"]),
            "valWon":     int(row["_amt"]),
            "qty":        int(row["_qty"]),
        })

    nc_list = [dict(it) for it in store_list]
    return {"store": store_list, "nc": nc_list}


def render_dashboard_html(df) -> str:
    """기존 인터페이스 유지용 — HTML 템플릿을 그대로 반환 (API 방식 사용 권장)"""
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "ui", "dashboard_template.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    return html
