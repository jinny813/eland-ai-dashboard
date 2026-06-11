import os
import re
import json
import sqlite3
import urllib.parse
import urllib.request
import pandas as pd
from datetime import datetime
from core.scoring_logic import AssortmentScorer, _is_outlet
from core.analyzer import ActionAnalyzer

# ── item_group(영문) → 한국어 카테고리명
_ITEM_GROUP_KO = {
    'Outer': '아우터', 'Top': '상의', 'Bottom': '하의', 'Skirt': '스커트',
    'Dress': '원피스', 'Set': '세트', 'Suits': '수트', 'Shirts': '셔츠',
    'Casual': '캐주얼', 'Knit': '니트',
    'RunningShoes': '러닝화', 'CasualShoes': '캐주얼화', 'OtherShoes': '기타화',
}

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "product_master.db")
_SCORER_GENERIC = AssortmentScorer({})


def _item_code_to_ko(item_code: str) -> str:
    if not item_code or item_code in ('—', '-', 'nan', 'None', ''):
        return '—'
    grp = _SCORER_GENERIC._get_item_group(item_code)
    return _ITEM_GROUP_KO.get(grp, '—')


def _naver_search_style_name(brand_name: str, style_code: str) -> str:
    client_id = os.environ.get("NAVER_CLIENT_ID", "")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return ''
    query = f"{brand_name} {style_code}".strip()
    if not query:
        return ''
    try:
        enc = urllib.parse.quote(query)
        url = f"https://openapi.naver.com/v1/search/shop.json?query={enc}&display=1"
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", client_id)
        req.add_header("X-Naver-Client-Secret", client_secret)
        resp = urllib.request.urlopen(req, timeout=5)
        if resp.getcode() != 200:
            return ''
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', [])
        if not items:
            return ''
        title = re.sub(r'<[^>]*>', '', items[0].get('title', '')).strip()
        if title:
            try:
                conn = sqlite3.connect(_DB_PATH)
                conn.execute(
                    "INSERT OR REPLACE INTO products (style_code, product_name, brand, updated_at) "
                    "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (style_code, title, brand_name)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            # JSON 파일에 캐시 누적
            try:
                json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "style_master.json")
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as jf:
                        master_data = json.load(jf)
                else:
                    master_data = {}
                if style_code not in master_data:
                    master_data[style_code] = {}
                master_data[style_code]["style_name"] = title
                master_data[style_code]["brand"] = brand_name
                ko_item = _item_code_to_ko(style_code)
                if ko_item and ko_item != '—':
                    master_data[style_code]["item_name"] = ko_item
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(master_data, jf, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return title
    except Exception:
        return ''

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
        s = str(v).replace(',', '').strip()
        if s in ('', '#N/A', '#REF!', '#VALUE!', 'nan', 'None'): return 0.0
        return float(s)
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
    df['_amt'] = df['stock_amt'].apply(lambda x: max(0.0, _safe_float(x)))
    df['_qty'] = df['stock_qty'].apply(lambda x: max(0.0, _safe_float(x))) if 'stock_qty' in df.columns else 0
    total_amt = df['_amt'].sum()
    if total_amt <= 0: return {}

    store_type = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
    outlet = _is_outlet(store_type)
    target_total = tM * 2.0  # 목표 재고액 (200%)
    inv_w = config.get('inv_weights', {})

    # 1. 아이템 점수 세부 (조닝별 특화 로직 반영)
    scorer = AssortmentScorer(config)
    zoning = config.get('zoning', '여성')

    # [v4.9] category_group 기반 조닝 폴백: config 조닝이 없거나 여성 기본값이면 카테고리로 보정
    category_group = str(df['category_group'].iloc[0]).strip() if 'category_group' in df.columns and not df.empty else ''
    _KNOWN_ZONINGS = {'스포츠', '아웃도어', '애슬레저', '신발', '남성', '아동', '캐릭터', '커리어', '시니어', '캐주얼'}
    _CAT_ZONING    = {'스포츠': '스포츠', '아웃도어': '아웃도어', '신사': '남성', '아동': '아동', '캐주얼': '캐주얼'}
    if zoning not in _KNOWN_ZONINGS:
        zoning = _CAT_ZONING.get(category_group, zoning)

    # [v135.0] 스마트 아이템 그룹핑 (scoring_logic과 동일하게 동기화)
    def _get_group_smart(row):
        # item_code 우선, 비어있으면 style_code fallback
        ic = str(row.get('item_code', '')).strip()
        code = ic if ic and ic not in ('nan', '0') else str(row.get('style_code', '')).strip()
        raw = code.upper() if code else ''

        # [v4.9c] 아동/남성 조닝: ITEM_CODE 전용 매핑 직접 조회 (슬라이딩 스캔 보다 정확)
        if raw and raw not in ('NAN', '0'):
            if zoning == '아동':
                hit = AssortmentScorer.ITEM_CODE_KIDS.get(raw) or \
                      AssortmentScorer.ITEM_CODE_KIDS.get(raw[2:4] if len(raw) >= 4 else raw[:2])
                if hit:
                    return hit
            elif zoning == '남성':
                hit = AssortmentScorer.ITEM_CODE_MENS.get(raw) or \
                      (AssortmentScorer.ITEM_CODE_MENS.get(raw[:2]) if len(raw) >= 2 else None)
                if hit: return hit
                for _s in range(2, min(len(raw) - 1, 10)):
                    hit = AssortmentScorer.ITEM_CODE_MENS.get(raw[_s:_s + 2])
                    if hit: return hit

        group = scorer._get_item_group(code)

        is_sports = (zoning == '스포츠')
        if is_sports and group in ['Top', 'Bottom', 'Others']:
            name = str(row.get('style_name', row.get('item_name', ''))).strip()
            cat = str(row.get('category_group', '')).strip()
            full_text = (name + cat).upper()
            
            # 신발류 키워드 감지 (스포츠 브랜드 특화)
            if any(k in full_text for k in ['러닝', 'RUNNING', '맥스', 'MAX', '쿠셔닝', '퍼포먼스', '신발', '슈즈', '운동화', 'SHOES']):
                return 'RunningShoes'
            if any(k in full_text for k in ['워킹', 'WALKING', '고워크', 'GOWALK', '슬립온', '캐주얼', '라이프']):
                return 'CasualShoes'
            if any(k in full_text for k in ['스니커즈', 'SNEAKERS', '샌들', 'SANDAL', '슬리퍼']):
                return 'OtherShoes'
        return group

    df['item_group'] = df.apply(_get_group_smart, axis=1)
    
    # [v136.0] 조닝별 레이블 맵 정의
    zoning_map = {
        '스포츠':   {'RunningShoes':'러닝화', 'CasualShoes':'워킹화', 'OtherShoes':'기타신발', 'Top':'상의', 'Bottom':'하의'},
        '아웃도어': {'Outer':'아우터', 'Top':'상의', 'Bottom':'하의', 'RunningShoes':'트레킹화', 'CasualShoes':'라이프스타일화'},
        '애슬레저': {'Top':'상의', 'Bottom':'하의', 'OtherShoes':'잡화'},
        '신발':     {'RunningShoes':'운동화', 'CasualShoes':'캐주얼화', 'OtherShoes':'샌들/슬리퍼'},
        '남성':     {'Suits':'정장', 'Shirts':'셔츠', 'Casual':'캐주얼', 'Knit':'니트', 'Bottom':'하의'},
        '아동':     {'Outer':'아우터', 'Top':'상의', 'Bottom':'하의', 'Dress':'원피스', 'Set':'상하세트'},
        '캐릭터':   {'Dress':'원피스', 'Outer':'아우터', 'Top':'상의', 'Bottom':'하의', 'Skirt':'스커트'},
        '커리어':   {'Outer':'아우터', 'Top':'상의', 'Dress':'원피스', 'Bottom':'하의', 'Skirt':'스커트'},
        '시니어':   {'Dress':'원피스', 'Outer':'아우터', 'Top':'상의', 'Bottom':'하의', 'Skirt':'스커트'},
        '캐주얼':   {'Outer':'아우터', 'Top':'상의', 'Dress':'원피스', 'Bottom':'하의', 'Skirt':'스커트'},
        '일반':     {'Outer':'아우터', 'Top':'상의', 'Bottom':'하의', 'Skirt':'스커트', 'Dress':'원피스'}
    }
    item_map = zoning_map.get(zoning, zoning_map['일반'])
    
    # [v3.9] 조닝별 기본 아이템 구성 정의 (설정 누락 시 대비)
    default_item_w = {
        '스포츠':   {'Top': 0.40, 'Bottom': 0.30, 'RunningShoes': 0.20, 'OtherShoes': 0.10},
        '아웃도어': {'Outer': 0.40, 'Top': 0.40, 'Bottom': 0.20},
        '애슬레저': {'Top': 0.50, 'Bottom': 0.40, 'OtherShoes': 0.10},
        '남성':     {'Suits': 0.40, 'Shirts': 0.20, 'Casual': 0.20, 'Knit': 0.10, 'Bottom': 0.10},
        '아동':     {'Outer': 0.30, 'Top': 0.30, 'Bottom': 0.25, 'Dress': 0.05, 'Set': 0.10},
        '캐주얼':   {'Outer': 0.35, 'Top': 0.25, 'Bottom': 0.10, 'Skirt': 0.15, 'Dress': 0.15},
        '일반':     {'Outer':0.30, 'Top':0.30, 'Bottom':0.20, 'Skirt':0.10, 'Dress':0.10},
    }
    item_weights = inv_w.get('item', default_item_w.get(zoning, default_item_w['일반']))
    # 남성 조닝인데 Suits 키가 없으면(여성 config 상속 오류) → 남성 기본값 강제 적용
    if zoning == '남성' and 'Suits' not in item_weights:
        item_weights = default_item_w['남성']
    
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
            "targetM": round(tgt_amt/1_000_000, 1), "mix_pct": round(amt/total_amt*100, 1) if total_amt > 0 else 0, "opt_pct": int(target_ratio*100)
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
    
    # [v4.1] 할인율 데이터가 모두 0인 상설 매장의 경우 연차(Age) 기준으로 자동 Fallback 처리
    has_dis_data = (df['_dis_rate'] > 0).any()
    use_age_for_dis = outlet and not has_dis_data

    category_group = str(df['category_group'].iloc[0]) if 'category_group' in df.columns else ""
    # [v11.1] 스포츠 카테고리 대응: 정상 매장이라도 실제 할인율 필드 사용 (아동은 제외)
    is_rate_based = zoning in ["스포츠", "아웃도어", "애슬레저"]
    if not is_rate_based and any(k in category_group for k in ["스포츠", "아웃도어"]):
        is_rate_based = True

    # [v4.5] 정상 매장도 할인율 데이터가 있으면 rate-based 사용 (로엠 계열 제외)
    _brand_nm_h = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns and not df.empty else ''
    _age_only_brands_h = {'로엠', '로엠(ROEM)'}

    dis_inv = inv_w.get('dis', {})

    if (outlet and not use_age_for_dis) or is_rate_based or (has_dis_data and _brand_nm_h not in _age_only_brands_h):
        # 상설 또는 스포츠: 실시간 할인율 필드 활용
        dis_cfg = [('d70', '70% 이상', (df['_dis_rate']>=70), dis_inv.get('s70', 0.10)), 
                   ('d50', '50~70% 미만', (df['_dis_rate']>=50)&(df['_dis_rate']<70), dis_inv.get('s50', 0.20)),
                   ('d30', '30~50% 미만', (df['_dis_rate']>=30)&(df['_dis_rate']<50), dis_inv.get('s30', 0.30)), 
                   ('d10', '1~30% 미만', (df['_dis_rate']>0)&(df['_dis_rate']<30), dis_inv.get('s10', 0.10)),
                   ('d0',  '0%', (df['_dis_rate']==0), dis_inv.get('s0', 0.00))]
    else:
        # 정상 또는 할인율 데이터 없는 상설: 연차(year) 기준 매핑
        dis_cfg = [('d70', '70% 이상', (df['_age']>=4), dis_inv.get('s70', 0.00)),
                   ('d50', '50~70%', (df['_age']==3), dis_inv.get('s50', 0.05)),
                   ('d30', '30~50%', (df['_age']==2), dis_inv.get('s30', 0.10)),
                   ('d10', '1~30%', (df['_age']==1), dis_inv.get('s10', 0.15)),
                   ('d0',  '정상가', (df['_age']==0), dis_inv.get('s0', 0.70))]
    
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
    # [v4.4.5] 사용자 요청: _age나 _dis_rate 추정 로직을 전면 배제하고 오직 DB의 freshness_type 텍스트만 신뢰
    _new_mask = ft.str.contains('신상', na=False)
    _plan_mask = ft.str.contains('기획', na=False)

    if outlet:
        # 상설: 신상(10%), 기획(20%)
        fresh_cfg = [
            ('new', '신상', _new_mask, 0.10), 
            ('plan', '기획', _plan_mask, 0.20)
        ]
    else:
        # 정상: 신상(70%), 기획(0%)
        fresh_cfg = [
            ('new', '신상', _new_mask, 0.70),
            ('plan', '기획', _plan_mask, 0.00)
        ]
    
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
    # 데이터 기준월 사용 (오늘 날짜가 아닌 실제 데이터 월 기준으로 시즌 목표 결정)
    _raw_m = df['data_month'].iloc[0] if 'data_month' in df.columns and not df.empty else ''
    month = int(str(_raw_m).replace('월', '').strip()) if str(_raw_m).replace('월', '').strip().isdigit() else datetime.now().month
    # [v8.8] 새로운 계절 구분: 봄(1,2,3), 여름(4,5,6), 가을(7,8,9), 겨울(10,11,12)
    # 1-6월: SS 시즌, 7-12월: FW 시즌
    # 계절 정의 및 코드 매핑
    season_map = [
        {'key': 'spring', 'l': '봄 (SS)',  'codes': ['봄', '1', '9']},
        {'key': 'summer', 'l': '여름 (SS)', 'codes': ['여름', '2', '9']},
        {'key': 'autumn', 'l': '가을 (FW)', 'codes': ['가을', '3', '8', '9']},
        {'key': 'winter', 'l': '겨울 (FW)', 'codes': ['겨울', '4', '9']}
    ]
    
    # 목표 비중 결정: data_month 기준 (1~3월=봄시즌, 4~6월=여름시즌)
    target_weights = {}
    if month in [1, 2, 3]:
        target_weights = {"봄": 0.50, "여름": 0.30}
    elif month in [4, 5, 6]:
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
    # [v128.0] scoring_logic.py와 동일하게 config의 inv_weights 참조 (하드코딩 0.25 제거)
    best_styles = []
    if 'sales_qty' in df.columns:
        sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
        sales_sum = df.assign(_sq=sq).groupby('style_code')['_sq'].sum().sort_values(ascending=False)
        best_styles = sales_sum.head(10)[sales_sum > 0].index.tolist()
    
    ref_best = _get_stock_ref_gen(df[df['style_code'].isin(best_styles)], outlet)
    best_amt = ref_best['_amt'].sum()
    # scoring_logic과 동일한 비율 사용 (상설: 0.20, 정상: config 기본값)
    best_ratio = inv_w.get('best', {}).get('store10', 0.25)
    tgt_best = target_total * best_ratio
    best_pct = (best_amt / tgt_best * 100) if tgt_best > 0 else 0
    best_segs = [{
        "key": "best", "l": "판매 BEST 10", "valM": round(best_amt/1_000_000, 1), "qty": int(ref_best['_qty'].sum()),
        "c": "#8B5CF6", "weight": int(best_ratio * 100), "pct": min(100.0, round(best_pct, 1)),
        "targetM": round(tgt_best/1_000_000, 1),
        "mix_pct": round(best_amt/total_amt*100, 1), "opt_pct": int(best_ratio * 100)
    }]

    return {
        "item": {"segs": item_segs}, "dis": {"segs": dis_segs}, "fresh": {"segs": fresh_segs},
        "best": {"segs": best_segs}, "season": {"segs": season_segs}, "total_qty_unique": int(df['_qty'].sum())
    }

def _build_bp_detail(config: dict, bp_df=None) -> dict:
    if bp_df is not None and not bp_df.empty: return _build_detail(bp_df, config)
    return { "item":{"segs":[]}, "dis":{"segs":[]}, "fresh":{"segs":[]}, "best":{"segs":[]}, "season":{"segs":[]} }

def _get_product_info(style_codes: list) -> dict:
    """DB에서 스타일 정보를 딕셔너리 형태로 일괄 로드"""
    if not style_codes: return {}
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "product_master.db")
    try:
        conn = sqlite3.connect(db_path)
        codes_str = "', '".join(style_codes)
        query = f"SELECT * FROM products WHERE style_code IN ('{codes_str}')"
        df_p = pd.read_sql(query, conn)
        conn.close()
        
        res = {}
        for _, row in df_p.iterrows():
            res[row['style_code']] = {
                "item_name": row['category'],
                "style_name": row['product_name'],
                "keywords": row['keywords'].split(", ") if row['keywords'] else [],
                "normal_price": row.get('normal_price', 0)
            }
        return res
    except:
        return {}

_EMPTY_VALS = {'', '—', '-', 'nan', 'None', 'none'}

def _build_best_items(df) -> dict:
    if df is None or df.empty or "sales_qty" not in df.columns: return {"store":[], "nc":[]}
    df = df.copy()
    sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
    style_sales = df.assign(_sq=sq).groupby('style_code')['_sq'].sum()
    best_styles = style_sales[style_sales > 0].nlargest(10).index.tolist()

    store_type = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
    outlet = _is_outlet(store_type)
    ref_df = _get_stock_ref_gen(df[df['style_code'].isin(best_styles)], outlet)
    brand_name = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns else ''

    res = []
    p_map = _get_product_info(best_styles)

    for s in best_styles:
        sub = ref_df[ref_df['style_code'] == s]
        if sub.empty: continue
        row = sub.iloc[0]

        # ── 1) raw data에서 초기값 추출
        raw_item_name = str(row.get('item_name', '') or '').strip()
        raw_style_name = str(row.get('style_name', '') or '').strip()

        # ── 2) dedup으로 누락된 경우: 같은 style_code의 다른 행에서 탐색
        if raw_style_name in _EMPTY_VALS:
            for _, srow in df[df['style_code'] == s].iterrows():
                sn = str(srow.get('style_name', '') or '').strip()
                if sn not in _EMPTY_VALS:
                    raw_style_name = sn
                    break

        # ── 3) DB 마스터 override
        if s in p_map:
            db_item = p_map[s].get('item_name') or ''
            db_style = p_map[s].get('style_name') or ''
            if db_item and db_item not in _EMPTY_VALS:
                raw_item_name = db_item
            if db_style and db_style not in _EMPTY_VALS:
                raw_style_name = db_style

        # ── 4) item_name: item_code 기반 한국어 카테고리명
        if raw_item_name in _EMPTY_VALS:
            ic = str(row.get('item_code', '') or '').strip()
            if not ic or ic in _EMPTY_VALS:
                ic = s
            raw_item_name = _item_code_to_ko(ic)

        # ── 5) style_name: 네이버 쇼핑 검색 (API key 있을 때만)
        if raw_style_name in _EMPTY_VALS and brand_name:
            found = _naver_search_style_name(brand_name, s)
            if found:
                raw_style_name = found

        # [v131.0] 단가 보완 로직 강화:
        # 1. DB 마스터 정보(p_map)에 유효 단가가 있는지 우선 확인
        db_price = p_map.get(s, {}).get('normal_price', 0)
        
        # 2. 해당 스타일의 전체 데이터(df)에서 0보다 큰 유효 단가가 있는지 검색
        style_all = df[df['style_code'] == s]
        valid_prices = style_all['normal_price'].apply(_safe_float)
        valid_prices = valid_prices[valid_prices > 0]
        
        if db_price and db_price > 0:
            raw_price = db_price
        elif not valid_prices.empty:
            raw_price = valid_prices.iloc[0]
        else:
            # 2. 단가 정보가 전혀 없으면 재고액/재고수량으로 역산
            s_amt = style_all['stock_amt'].apply(_safe_float).sum()
            s_qty = style_all['stock_qty'].apply(_safe_float).sum()
            if s_qty > 0:
                raw_price = s_amt / s_qty
            else:
                # 3. 재고도 없으면 판매액/판매수량으로 역산 (BEST 아이템이므로 판매 데이터는 존재함)
                sales_amt_sum = style_all['sales_amt'].apply(_safe_float).sum()
                sales_qty_sum = style_all['sales_qty'].apply(_safe_float).sum()
                if sales_qty_sum > 0:
                    raw_price = sales_amt_sum / sales_qty_sum
                else:
                    raw_price = 0

        res.append({
            "rank": len(res)+1, "item_name": str(raw_item_name), "style_code": str(s),
            "style_name": str(raw_style_name), "price": int(raw_price),
            "sales": int(df[df['style_code']==s]['sales_qty'].apply(_safe_float).sum()),
            "valWon": int(sub['stock_amt'].apply(_safe_float).sum()), "qty": int(sub['stock_qty'].apply(_safe_float).sum())
        })
    return {"store": res, "nc": res}

def _build_action_plan(b_df: pd.DataFrame, bp_brand_df: pd.DataFrame = None) -> dict:
    """
    [v200.0] 분석 엔진 분리: core/analyzer.py의 ActionAnalyzer에 분석 위임
    """
    analyzer = ActionAnalyzer()
    return analyzer.get_action_recommendations(b_df, bp_brand_df)


def render_dashboard_html(_df=None) -> str:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "dashboard_template.html")
    with open(path, "r", encoding="utf-8") as f: return f.read()
