import os
import json
import pandas as pd
from datetime import datetime, timedelta
from core.scoring_logic import AssortmentScorer, _is_outlet
from config.scoring_config import SCORING_CONFIG

# ── [v8.0] 다중 팔레트 기반 동적 색상 유틸리티
def _get_dynamic_color(pct: float, p_type: str = "default") -> str:
    """
    달성률(pct)에 따라 25% 구간별로 [Red, Yellow, Green, Blue] 계열 색상 반환.
    """
    step = 0
    if pct < 25:    step = 0
    elif pct < 50:  step = 1
    elif pct < 75:  step = 2
    else:           step = 3

    palettes = {
        "total":  ["#F87171", "#FBBF24", "#34D399", "#60A5FA"], 
        "item":   ["#8B5CF6", "#A78BFA", "#C4B5FD", "#DDD6FE"], 
        "dis":    ["#EF4444", "#F97316", "#FB923C", "#FDBA74"], 
        "fresh":  ["#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"], 
        "best":   ["#10B981", "#34D399", "#6EE7B7", "#A7F3D0"], 
        "season": ["#D97706", "#F59E0B", "#FBBF24", "#FDE68A"], 
        "default":["#94A3B8", "#64748B", "#475569", "#334155"]
    }
    colors = palettes.get(p_type, palettes["default"])
    return colors[step]

ITEM_COLORS = ["#7C3AED","#A78BFA","#C4B5FD","#DDD6FE","#EDE9FE","#6D28D9","#8B5CF6","#9F7AEA","#B794F4","#D6BCFA"]

def _safe_float(v) -> float:
    try:
        if pd.isna(v): return 0.0
        return float(str(v).replace(',', '').strip())
    except: return 0.0

def _get_stock_ref_gen(df, outlet):
    """중복 제거된 고유 재고 레퍼런스 추출"""
    if df.empty: return df
    if 'inv_uid' in df.columns and df['inv_uid'].notna().any():
        return df.drop_duplicates('inv_uid')
    if outlet: return df
    d_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
    return df.drop_duplicates(subset=[c for c in d_cols if c in df.columns])

def _build_detail(df: pd.DataFrame, config: dict, tM: float = 100.0) -> dict:
    if df is None or df.empty: return {}

    df = df.copy()
    df['_amt'] = df['stock_amt'].apply(_safe_float)
    df['_qty'] = df['stock_qty'].apply(_safe_float) if 'stock_qty' in df.columns else 0
    total_amt = df['_amt'].sum()
    if total_amt <= 0: return {}

    store_type = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
    outlet = _is_outlet(store_type)
    target_total = tM * 2.0  # 목표 재고액 (200%)
    inv_w = config.get('inv_weights', {})

    # 1. 아이템 점수 세부
    scorer = AssortmentScorer(config)
    df['item_group'] = df['item_code'].apply(scorer._get_item_group) if 'item_code' in df.columns else 'Others'
    item_map = {'Outer':'아우터', 'Top':'상의', 'Bottom':'하의', 'Skirt':'스커트', 'Dress':'원피스'}
    item_weights = inv_w.get('item', {'Outer':0.30, 'Top':0.30, 'Bottom':0.20, 'Skirt':0.10, 'Dress':0.10})
    item_segs = []
    for i, (eng, kor) in enumerate(item_map.items()):
        ref = _get_stock_ref_gen(df[df['item_group'] == eng], outlet)
        amt = ref['_amt'].sum()
        target_ratio = item_weights.get(eng, 0.0)
        tgt_amt = target_total * target_ratio
        pct = (amt / tgt_amt * 100) if tgt_amt > 0 else 0.0
        item_segs.append({
            "key": eng, "l": kor, "valM": round(amt/1_000_000, 1), "qty": int(ref['_qty'].sum()),
            "c": ITEM_COLORS[i % len(ITEM_COLORS)], "weight": int(target_ratio*100), "pct": min(100.0, round(pct, 1)),
            "targetM": round(tgt_amt/1_000_000, 1), "mix_pct": round(amt/total_amt*100, 1), "opt_pct": int(target_ratio*100)
        })

    # [v8.7] 연차(Age) 계산: 기준 연도 정규화 (자릿수 보정)
    year_base = config.get('year_base', 2026)
    if year_base < 100: year_base += 2000

    def _get_age_sync(y):
        try:
            val = str(y).replace('년','').strip()
            y_num = int(val)
            if y_num < 100: y_num += 2000
            return max(0, year_base - y_num)
        except: return 0
    
    df['_age'] = df['year'].apply(_get_age_sync) if 'year' in df.columns else 0

    # 2. 할인율 세부
    df['_dis_rate'] = df['discount_rate'].apply(AssortmentScorer._parse_discount_rate) if 'discount_rate' in df.columns else 0.0
    if outlet:
        # 상설: 실시간 할인율 필드 활용
        dis_cfg = [('d70', '70% 이상', (df['_dis_rate']>=70), 0.10), 
                   ('d50', '50~70% 미만', (df['_dis_rate']>=50)&(df['_dis_rate']<70), 0.20),
                   ('d30', '30~50% 미만', (df['_dis_rate']>=30)&(df['_dis_rate']<50), 0.30), 
                   ('d10', '1~30% 미만', (df['_dis_rate']>0)&(df['_dis_rate']<30), 0.10)]
    else:
        # 정상: 연차(year) 기준 매핑 — 70%+(4년+), 50%+(3년), 30%+(2년), 1-30%(1년), 정상가(0년)
        dis_cfg = [('d70', '70% 이상', (df['_age']>=4), 0.00), 
                   ('d50', '50~70% 미만', (df['_age']==3), 0.05),
                   ('d30', '30~50% 미만', (df['_age']==2), 0.10), 
                   ('d10', '1~30% 미만', (df['_age']==1), 0.15),
                   ('d0',  '정상가 (신규)', (df['_age']==0), 0.00)]
    
    dis_segs = []
    for key, lbl, mask, ratio in dis_cfg:
        ref = _get_stock_ref_gen(df[mask], outlet)
        amt = ref['_amt'].sum()
        tgt_amt = target_total * ratio
        pct = (amt / tgt_amt * 100) if tgt_amt > 0 else (100.0 if ratio == 0 and amt <= 0 else 0)
        dis_segs.append({
            "key": key, "l": lbl, "valM": round(amt/1_000_000, 1), "qty": int(ref['_qty'].sum()),
            "c": "#EF4444" if ratio > 0 else "#CBD5E1", "weight": int(ratio*100), "pct": min(100.0, round(pct, 1)),
            "targetM": round(tgt_amt/1_000_000, 1), "mix_pct": round(amt/total_amt*100, 1), "opt_pct": int(ratio*100)
        })

    # 3. 신선도 세부
    ft = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series(['']*len(df))
    if outlet: 
        # 상설: 명시적 필드
        fresh_cfg = [('new', '신상', (ft == '신상'), 0.10), ('plan', '기획', (ft == '기획'), 0.20)]
    else: 
        # 정상: 연차 0년차를 신상으로 간주
        fresh_cfg = [('new', '신상', (df['_age'] == 0), 0.70)]
    
    fresh_segs = []
    for key, lbl, mask, ratio in fresh_cfg:
        ref = _get_stock_ref_gen(df[mask], outlet)
        amt = ref['_amt'].sum()
        tgt_amt = target_total * ratio
        pct = (amt / tgt_amt * 100) if tgt_amt > 0 else 0
        fresh_segs.append({
            "key": key, "l": lbl, "valM": round(amt/1_000_000, 1), "qty": int(ref['_qty'].sum()),
            "c": _get_dynamic_color(pct, "fresh"), "weight": int(ratio*100), "pct": min(100.0, round(pct, 1)),
            "targetM": round(tgt_amt/1_000_000, 1), "mix_pct": round(amt/total_amt*100, 1), "opt_pct": int(ratio*100)
        })

    # 4. 시즌 세부 (4개 계절 고정 노출)
    month = datetime.now().month
    # [v8.8] 새로운 계절 구분: 봄(1,2,3), 여름(4,5,6), 가을(7,8,9), 겨울(10,11,12)
    # 1-6월: SS 시즌, 7-12월: FW 시즌
    is_ss = 1 <= month <= 6
    
    # 계절 정의 및 코드 매핑
    season_map = [
        {'key': 'spring', 'l': '봄 (SS)',  'codes': ['봄', '1', '9']},
        {'key': 'summer', 'l': '여름 (SS)', 'codes': ['여름', '2', '9']},
        {'key': 'autumn', 'l': '가을 (FW)', 'codes': ['가을', '3', '8', '9']},
        {'key': 'winter', 'l': '겨울 (FW)', 'codes': ['겨울', '4', '9']}
    ]
    
    # 목표 비중 결정 로직 (사용자 요청: 4월 봄 50%, 여름 30%)
    target_weights = {} # {코어라벨: 비중}
    if month in [1, 2, 3, 4]:
        target_weights = {"봄": 0.50, "여름": 0.30}
    elif month in [5, 6]:
        target_weights = {"여름": 0.50, "봄": 0.30}
    elif month in [7, 8, 9]:
        target_weights = {"가을": 0.50, "겨울": 0.30}
    else: # 10, 11, 12
        target_weights = {"겨울": 0.50, "가을": 0.30}
        
    sc_df = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series(['']*len(df))
    season_segs = []
    
    for item in season_map:
        mask = sc_df.isin(item['codes'])
        ref = _get_stock_ref_gen(df[mask], outlet)
        amt = ref['_amt'].sum()
        
        # 해당 계절 라벨(봄, 여름 등) 추출하여 목표 비중 매칭
        core_label = item['l'].split(' ')[0]
        ratio = target_weights.get(core_label, 0.0)
            
        tgt_amt = target_total * ratio
        pct = (amt / tgt_amt * 100) if tgt_amt > 0 else (100.0 if ratio == 0 else 0)
        
        season_segs.append({
            "key": item['key'], "l": item['l'], "valM": round(amt/1_000_000, 1), "qty": int(ref['_qty'].sum()),
            "c": _get_dynamic_color(pct, "season") if ratio > 0 else "#CBD5E1", 
            "weight": int(ratio * 100), "pct": min(100.0, round(pct, 1)),
            "targetM": round(tgt_amt/1_000_000, 1), "mix_pct": round(amt/total_amt*100, 1), "opt_pct": int(ratio * 100),
            "is_score_target": ratio > 0
        })

    # 5. BEST 세부
    best_styles = []
    if 'sales_qty' in df.columns:
        sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
        sales_sum = df.assign(_sq=sq).groupby('style_code')['_sq'].sum().sort_values(ascending=False)
        best_styles = sales_sum.head(10)[sales_sum > 0].index.tolist()
    
    ref_best = _get_stock_ref_gen(df[df['style_code'].isin(best_styles)], outlet)
    best_amt = ref_best['_amt'].sum()
    tgt_best = target_total * 0.25
    best_pct = (best_amt / tgt_best * 100) if tgt_best > 0 else 0
    best_segs = [{
        "key": "best", "l": "판매 BEST 10", "valM": round(best_amt/1_000_000, 1), "qty": int(ref_best['_qty'].sum()),
        "c": "#8B5CF6", "weight": 25, "pct": min(100.0, round(best_pct, 1)), "targetM": round(tgt_best/1_000_000, 1),
        "mix_pct": round(best_amt/total_amt*100, 1), "opt_pct": 25
    }]

    return {
        "item": {"segs": item_segs}, "dis": {"segs": dis_segs}, "fresh": {"segs": fresh_segs},
        "best": {"segs": best_segs}, "season": {"segs": season_segs}, "total_qty_unique": int(df['_qty'].sum())
    }

def _build_bp_detail(config: dict, bp_df=None) -> dict:
    if bp_df is not None and not bp_df.empty: return _build_detail(bp_df, config)
    return { "item":{"segs":[]}, "dis":{"segs":[]}, "fresh":{"segs":[]}, "best":{"segs":[]}, "season":{"segs":[]} }

def _load_style_master():
    """style_master.json 로드 유틸리티"""
    try:
        path = os.path.join(os.path.dirname(__file__), "style_master.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def _build_best_items(df) -> dict:
    if df is None or df.empty or "sales_qty" not in df.columns: return {"store":[], "nc":[]}
    df = df.copy()
    sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
    best_styles = df.assign(_sq=sq).groupby('style_code')['_sq'].sum().nlargest(10).index.tolist()
    
    store_type = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
    outlet = _is_outlet(store_type)
    ref_df = _get_stock_ref_gen(df[df['style_code'].isin(best_styles)], outlet)
    
    res = []
    # 마스터 데이터 로드
    master = _load_style_master()
    
    for s in best_styles:
        sub = ref_df[ref_df['style_code'] == s]
        if sub.empty: continue
        row = sub.iloc[0]
        
        # 명칭 보완 로직
        raw_item_name = str(row.get('item_name','—'))
        raw_style_name = str(row.get('style_name','—'))
        
        if (raw_item_name == '—' or not raw_item_name) and s in master:
            raw_item_name = master[s].get('item_name', '—')
            
        if (raw_style_name == '—' or not raw_style_name) and s in master:
            raw_style_name = master[s].get('style_name', '—')

        res.append({
            "rank": len(res)+1, "item_name": raw_item_name, "style_code": str(s),
            "style_name": raw_style_name, "price": int(_safe_float(row.get('normal_price',0))),
            "sales": int(df[df['style_code']==s]['sales_qty'].apply(_safe_float).sum()),
            "valWon": int(sub['stock_amt'].apply(_safe_float).sum()), "qty": int(sub['stock_qty'].apply(_safe_float).sum())
        })
    return {"store": res, "nc": res}

def render_dashboard_html(df) -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "dashboard_template.html")
    with open(path, "r", encoding="utf-8") as f: return f.read()
