"""
core/data_loader.py
===================
Google Sheets → 대시보드 JSON 변환 파이프라인

수정 내역:
- [v68.4] 전체 로직 긴급 복구 및 마스터 브랜드 리스트 도입
- NC신구로점 여성 카테고리에 4개 신규 브랜드 상시 노출 처리
- 데이터 미업로드 브랜드에 대한 0점 자리표시자(Placeholder) 생성 로직 추가
"""

import pandas as pd
from datetime import datetime
from database.gsheet_manager import GSheetManager
from core.scoring_logic import AssortmentScorer
from config.scoring_config import SCORING_CONFIG, get_weights_by_category, get_category_guide
from config.brand_targets import (
    get_tm, PREV_MONTH_SALES, PREV_YEAR_SALES, MONTHLY_TM,
    PREV_YEAR_MONTHLY_SALES, CURR_MONTH_ACTUALS,
)
from core.html_generator import _build_detail, _build_bp_detail, _build_best_items, _build_action_plan
from config.area_config import get_area
from config.store_type_config import get_store_type as _cfg_store_type, get_display_label as _cfg_display_label
import logging

logger = logging.getLogger(__name__)

# ── 수치 변환 유틸
def _try_float(v) -> float:
    try:
        if isinstance(v, (int, float)): return float(v)
        s = str(v).replace(',', '').replace(' ', '').replace('%', '').strip()
        if s in ('', '#N/A', '#REF!', '#VALUE!', 'nan', 'None'): return 0.0
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _is_outlet_type(store_type: str) -> bool:
    """상설 매장 판단 — '복합'은 상설 로직 동일 적용"""
    v = str(store_type).strip().lower()
    return any(k in v for k in ["상설", "outlet", "아울렛", "팩토리", "factory", "복합"]) or v.startswith("상")


def _get_config(category: str, store_type: str, brand: str) -> dict:
    """우선순위: 카테고리_매장유형_브랜드 > 카테고리_매장유형 > 기본_설정 > category_store_type base"""
    # SCORING_CONFIG 키는 '상설' 표기 통일
    normalized_type = "상설" if _is_outlet_type(store_type) else "정상"
    key_brand = f"{category}_{normalized_type}_{brand}"
    key_type  = f"{category}_{normalized_type}"
    base = get_weights_by_category(category, store_type, brand)
    return (
        SCORING_CONFIG.get(key_brand)
        or SCORING_CONFIG.get(key_type)
        or SCORING_CONFIG.get("기본_설정")
        or base
    )


def _score_df(target_df: pd.DataFrame, config: dict) -> int:
    """DataFrame을 채점하여 total_score 정수 반환 (데이터 없으면 0)"""
    if target_df is None or target_df.empty:
        return 0
    scorer = AssortmentScorer(config=config)
    scored = scorer.score(target_df)
    if scored is None or scored.empty:
        return 0
    return int(round(float(scored.iloc[0].get('total_score', 0))))

def _score_df_product(target_df: pd.DataFrame, config: dict) -> int:
    """DataFrame을 채점하여 product_score 정수 반환 (데이터 없으면 0)"""
    if target_df is None or target_df.empty:
        return 0
    scorer = AssortmentScorer(config=config)
    scored = scorer.score(target_df)
    if scored is None or scored.empty:
        return 0
    return int(round(float(scored.iloc[0].get('product_score', 0))))


def load_dashboard_data(mgr: GSheetManager = None) -> dict:
    """
    Google Sheets → 대시보드 JSON 구조 생성. 
    마스터 브랜드 리스트를 통해 데이터가 없어도 특정 브랜드를 노출합니다.
    """
    try:
        # 1. 연결 및 로드
        if mgr is None:
            mgr = GSheetManager()
        if not mgr.is_connected:
            return {"error": "구글 시트 연동 실패"}

        sheet = mgr.spreadsheet.worksheet("Records")
        all_recs = sheet.get_all_records()
        if not all_recs:
            # 데이터가 없을 경우에도 UI가 깨지지 않도록 기본 구조를 반환합니다.
            return {
                "CATS": [],
                "STORES": [],
                "scoreData": {},
                "BRANDS": [],
                "DETAIL": {},
                "BP_DETAIL": {},
                "BEST_ITEMS": {},
                "ACTION_PLAN": {}
            }

        df = pd.DataFrame(all_recs)

        # [v74.1] 공격적 데이터 정규화: 모든 텍스트 컬럼의 앞뒤 공백 강제 제거
        # (인합 및 분류 성공률을 극대화)
        str_cols = ['brand_name', 'store_name', 'style_code', 'freshness_type', 'season_code', 'store_type', 'data_month']
        for c in str_cols:
            if c in df.columns:
                df[c] = df[c].astype(str).str.strip()

        # [v74.6] 수치형 컬럼 강제 변환 (정렬 및 계산 오류 방지)
        # stock_amt, stock_qty 등 컬럼에 콤마가 포함된 문자열이 섞여 있을 경우 sort_values 시 TypeError 발생 가능
        num_cols = ['stock_amt', 'stock_qty', 'sales_qty', 'sales_amt', 'normal_price']
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)

        # [v126.0] year 필터: 정상 매장 중 스포츠/잡화 카테고리 제외
        # 스포츠·잡화 브랜드는 year 컬럼 미사용 (freshness_type으로 신선도 관리)
        # → year가 비어있어도 필터링하지 않도록 예외 처리
        # 아울렛 계열(압소바 등) 브랜드는 시트 store_type이 정상으로 등록돼 있더라도
        #   year 없이 운영하므로 상설로 사전 보정 후 필터에서 제외
        _no_year_outlet_brands = ['압소바', '더레노마']
        for _b in _no_year_outlet_brands:
            _m = df['brand_name'].str.contains(_b, na=False)
            df.loc[_m, 'store_type'] = '상설'

        if 'year' in df.columns and 'store_type' in df.columns and 'category_group' in df.columns:
            is_normal = ~df['store_type'].apply(_is_outlet_type)
            # 잡화: 전 건 year 없음 → 패션 시즌 year 불필요 카테고리
            is_no_year_cat = df['category_group'].astype(str).str.strip().isin(['스포츠', '잡화'])
            bad_year  = df['year'].astype(str).str.strip().eq("")
            # freshness_type='신상' 행은 year가 없어도 유효 (신상품은 이전 연도 없음)
            is_fresh_new = df['freshness_type'].astype(str).str.contains('신상', na=False) if 'freshness_type' in df.columns else pd.Series([False] * len(df))
            # 정상 매장 + year 필요 카테고리 + year 없음 + 신상 아님 → 필터링
            df = df[~(is_normal & ~is_no_year_cat & bad_year & ~is_fresh_new)]
        
        # [v125.0] 카테고리 통합 및 자동 매핑
        if 'category_group' in df.columns:
            df.loc[df['category_group'] == '골프웨어', 'category_group'] = '신사'
            df.loc[df['category_group'] == '아동의류(특정매입)', 'category_group'] = '아동'
            # 스케쳐스 스포츠 카테고리 강제 매핑 (데이터 유실 방지)
            df.loc[df['brand_name'].str.contains('스케쳐스', na=False), 'category_group'] = '스포츠'
        
        # [v4.3] 이랜드월드 브랜드(스파오키즈, 뉴발란스키즈) 정상 매장 로직 적용 (사용자 요청)
        eland_world_brands = ['스파오키즈', '뉴발란스키즈']
        for b in eland_world_brands:
            mask = df['brand_name'].str.contains(b, na=False)
            df.loc[mask, 'store_type'] = '정상'
            
        all_stores = [s for s in df['store_name'].unique()
                      if s and not str(s).lstrip('-').replace('.', '', 1).isdigit()]
        stores = sorted(all_stores, key=lambda s: (0 if s == 'NC신구로점' else (1 if s == '뉴코아부천점' else 2), s))
        
        bp_stores = [s for s in all_stores if s.startswith("__BP__")]
        bp_df = df[df['store_name'].isin(bp_stores)] if bp_stores else pd.DataFrame()

        cats = ['전체', '여성', '아동', '신사', '캐주얼', '스포츠', '잡화']
        # [v4.0] 데이터가 있는 최신 월 자동 선택 (현재 월 데이터 부재 시 대응)
        available_months = df['data_month'].unique()
        current_month = f"{datetime.now().month}월"
        
        # 월 이름에서 숫자 추출하여 정렬 (12월 > 1월 방지)
        def _get_m_num(m_str):
            try: return int(str(m_str).replace('월','').strip())
            except: return 0
            
        sorted_months = sorted([m for m in available_months if m], key=_get_m_num, reverse=True)
        
        if current_month in available_months:
            diag_month = current_month
        elif sorted_months:
            diag_month = sorted_months[0]
        else:
            diag_month = current_month
            
        print(f"DEBUG: Selected diag_month = {diag_month}")

        # [v68.4] 마스터 브랜드 리스트 (데이터 유무와 상관없이 노출할 브랜드 명시)
        MASTER_CATEGORY_BRANDS = {
            "NC신구로점": {
                "여성": [
                    "로엠", "미쏘", "리스트", "쉬즈미스", "JJ지고트", "나이스클랍", "바바팩토리", "베네통", "시슬리",
                    "클라비스", "더아이잗", "비씨비지", "발렌시아", "베스띠벨리", "올리비아로렌",
                    "제시뉴욕", "에잇컨셉", "샤틴", "보니스팍스", "안지크", "플라스틱아일랜드"
                ],
                "스포츠": ["스케쳐스"]
            },
            "2001중계점": { "여성": ["리스트", "나이스클랍"] },
            "NC송파점": { "여성": ["쉬즈미스"] },
            "동아쇼핑점": { "여성": ["로엠"] },
            "NC야탑점": { "여성": ["베네통", "시슬리"] },
            "NC강서점": { "여성": ["JJ지고트"] },
            "NC평촌점": { "여성": ["바바팩토리"] },
            "뉴코아부천점": {
                "아동": [
                    "컬리수", "페리미츠", "베네통키즈", "아가방", "모이몰른", "뉴발란스키즈",
                    "탑텐키즈", "스파오키즈", "행텐틴즈", "NBA키즈", "폴햄키즈", "MLB키즈",
                    "앙팡스(압소바)", "블랙야크키즈", "휠라키즈", "아디다스키즈", "지프키즈", "에어워크주니어"
                ]
            },
        }

        # [v4.8] 브랜드별 1등 매장 자동 지정: 같은 브랜드 중 평매출(평당 매출액) 최상위 매장
        _normal_stores = [s for s in stores if not s.startswith("__BP__")]
        brand_top_store: dict = {}  # brand_name → top store name
        for _b in df['brand_name'].unique():
            if not _b: continue
            _b_rows = df[(df['brand_name'] == _b) & (df['store_name'].isin(_normal_stores))]
            _avgs = {}
            for _s in _b_rows['store_name'].unique():
                _s_sales = _b_rows[_b_rows['store_name'] == _s]['sales_amt'].apply(_try_float).sum()
                _s_area = get_area(_s, _b)
                _avgs[_s] = (_s_sales / _s_area) if _s_area > 0 else _s_sales
            if len(_avgs) >= 2:  # 2개 이상 매장에 있어야 비교 의미
                brand_top_store[_b] = max(_avgs, key=_avgs.get)

        score_data  = {}
        brands_list = []
        detail_data = {}
        bp_detail   = {}
        best_items  = {}
        action_plan = {}  # [액션가이드] 브랜드별 층장 액션 제안

        for store in stores:
            st_df = df[df['store_name'] == store]
            score_data[store] = []
            detail_data[store] = {}
            bp_detail[store] = {}
            best_items[store] = {}
            action_plan[store] = {}  # [액션가이드] 지점별 초기화

            # 1. 카테고리별 요약 점수 계산 (P1)
            for cat in cats:
                target_df = st_df if cat == '전체' else st_df[st_df['category_group'] == cat]
                
                actual_brands = target_df['brand_name'].unique().tolist() if not target_df.empty else []
                loop_brands = actual_brands

                if not loop_brands:
                    score_data[store].append(0)
                    continue

                cat_scores_with_sales = []
                for brand in loop_brands:
                    b_df = target_df[target_df['brand_name'] == brand].copy()
                    if b_df.empty:
                        # [v114.0] 데이터가 없는 브랜드는 P1 점수 합산에서 제외
                        continue
                    
                    _ct = _cfg_store_type(store, brand)
                    b_type = _ct if _ct else (str(b_df.iloc[0].get('store_type', '상설')).strip() or '상설')
                    cfg = _get_config(cat if cat != '전체' else "여성", b_type, brand)
                    b_df['tM'] = get_tm(brand_name=brand, store_name=store, month=diag_month)
                    score = _score_df_product(b_df, cfg)
                    
                    prev_benchmark_sales = PREV_MONTH_SALES.get(store, {}).get(brand, 0.0)
                    if prev_benchmark_sales > 0:
                        b_sales = prev_benchmark_sales
                    else:
                        b_sales = b_df['sales_amt'].apply(_try_float).sum() if 'sales_amt' in b_df.columns else 0.0
                        
                    cat_scores_with_sales.append((score, b_sales))

                if cat_scores_with_sales:
                    total_sales = sum(s[1] for s in cat_scores_with_sales)
                    if total_sales > 0:
                        weighted_sum = sum(s[0] * (s[1] / total_sales) for s in cat_scores_with_sales)
                        avg = int(round(weighted_sum))
                    else:
                        # 매출 데이터가 모두 0인 경우 단순 평균
                        avg = int(round(sum(s[0] for s in cat_scores_with_sales) / len(cat_scores_with_sales)))
                else:
                    avg = 0
                    
                score_data[store].append(avg)

            # 2. 브랜드별 상세 데이터 구축 (P2)
            # [v114.1] 데이터가 있는 브랜드만 노출 (Placeholder 생성 로직 제거)
            all_target_brands = sorted(st_df['brand_name'].unique().tolist())

            for b_name in all_target_brands:
                if not b_name: continue
                b_df = st_df[st_df['brand_name'] == b_name].copy()
                
                # 데이터가 없는 브랜드를 걸러내는 안전장치
                if b_df.empty:
                    continue

                # [v121.0] 데이터 중복 업로드 및 스타일 합계 판매량 반복 노출 대응
                if 'inv_uid' in b_df.columns and b_df['inv_uid'].notna().any():
                    b_df = b_df.drop_duplicates(subset=['inv_uid'])
                else:
                    # 1. 먼저 완전히 동일한 행 제거
                    b_df = b_df.drop_duplicates()
                    
                    # [v122.0] 판매량이 있는 경우에만 스타일별 중복 제거 수행
                    # 판매량이 0인 행들은 각각의 재고를 모두 합산해야 하므로 보존해야 함
                    sales_mask = b_df['sales_qty'] > 0
                    sales_df = b_df[sales_mask].copy()
                    zero_df = b_df[~sales_mask].copy()
                    
                    if not sales_df.empty:
                        subset_cols = ['style_code', 'sales_qty', 'sales_amt']
                        for c in ['color', 'size']:
                            if c in b_df.columns: subset_cols.append(c)
                        sales_df = sales_df.drop_duplicates(subset=subset_cols, keep='first')
                    
                    b_df = pd.concat([sales_df, zero_df], ignore_index=True)

                # 데이터가 있는 브랜드 처리
                b_cat = str(b_df.iloc[0].get('category_group', '여성')).strip() or '여성'
                
                # [v107.0] 특정 브랜드는 DB 설정과 무관하게 '정상/상설' 유형 고정 적용
                # 지오지아는 신사 카테고리 상설매장으로 고정 (사용자 요청)
                normals = ["로엠", "미쏘", "더아이잗", "에잇컨셉", "폴햄키즈", "스파오키즈", "뉴발란스키즈"]
                outlets = ["지오지아", "지오지아팩토리", "인동팩토리(리스트,쉬즈미스)", "프로젝트키즈", "네파", "젝시믹스", "스케쳐스"]
                
                _cfg_type = _cfg_store_type(store, b_name)
                if _cfg_type:
                    b_type = _cfg_type
                    b_df['store_type'] = _cfg_type
                elif b_name in normals:
                    b_type = "정상"
                    b_df['store_type'] = "정상"
                elif b_name in outlets:
                    b_type = "상설"
                    b_df['store_type'] = "상설"
                else:
                    b_type = str(b_df.iloc[0].get('store_type', '상설')).strip() or '상설'

                cfg = _get_config(b_cat, b_type, b_name)
                
                tM_won = get_tm(brand_name=b_name, store_name=store, month=diag_month)
                b_df['tM'] = tM_won
                
                # [v74.5] 중복 제거 로직 완화 (상설 매장은 inv_uid가 없으면 모든 행 합산)
                is_outlet_b = _is_outlet_type(b_type)
                if 'inv_uid' in b_df.columns and b_df['inv_uid'].notna().any():
                    stock_ref = b_df.drop_duplicates('inv_uid')
                elif is_outlet_b:
                    # 상설 매장: inv_uid가 없으면 모든 데이터 신뢰 (합산)
                    stock_ref = b_df
                else:
                    # 정상 매장: 기존처럼 기준 컬럼으로 중복 제거
                    dedup_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
                    stock_ref = b_df.drop_duplicates(subset=[c for c in dedup_cols if c in b_df.columns])
                
                stock_amt = stock_ref['stock_amt'].apply(lambda x: max(0.0, _try_float(x))).sum()
                stock_qty = stock_ref['stock_qty'].apply(lambda x: max(0.0, _try_float(x))).sum()
                
                # [v4.2] 당월 실적 키 계산
                try:
                    _diag_mo = int(str(diag_month).replace('월', '').strip())
                    _cur_mk = f"{datetime.now().year}_{_diag_mo:02d}"
                except Exception:
                    _cur_mk = None

                b_data_month = str(b_df.iloc[0].get('data_month', '')).strip()
                b_df['area'] = get_area(store, b_name)
                prev_benchmark_sales = PREV_MONTH_SALES.get(store, {}).get(b_name, 0.0)

                # 브랜드 월 매출: CURR_MONTH_ACTUALS 최근 가용 월 → PREV_MONTH_SALES(3월) → 합산
                # _active_mk: 실제로 사용 중인 실적 월 키 (성장률 비교 기준 결정에 사용)
                _active_mk = None
                _active_sales = 0
                if _cur_mk:
                    for _try_mk in sorted(CURR_MONTH_ACTUALS.get(store, {}).keys(), reverse=True):
                        if _try_mk <= _cur_mk:
                            v = CURR_MONTH_ACTUALS[store][_try_mk].get(b_name, 0)
                            if v > 0:
                                _active_mk = _try_mk
                                _active_sales = v
                                break

                if _active_sales > 0:
                    b_df['brand_month_sales'] = _active_sales
                elif prev_benchmark_sales > 0:
                    b_df['brand_month_sales'] = prev_benchmark_sales
                    b_df['data_month'] = "3월"
                    b_data_month = "3월"
                    try:
                        _active_mk = f"{datetime.now().year}_03"
                    except Exception:
                        pass
                else:
                    b_df['brand_month_sales'] = b_df['sales_amt'].sum() if 'sales_amt' in b_df.columns else 0.0

                scorer = AssortmentScorer(config=cfg)
                scored = scorer.score(b_df)

                if scored is not None and not scored.empty:
                    row = scored.iloc[0]
                    cur_sales_sum = b_df['brand_month_sales'].iloc[0] if 'brand_month_sales' in b_df.columns else 0.0

                    # [v4.2] 성장률: 활성 월의 전년동월과 비교 (PREV_YEAR_MONTHLY_SALES → PREV_YEAR_SALES)
                    _prev_yr_sales = None
                    if _active_mk and '_' in _active_mk:
                        _act_yr, _act_mo = _active_mk.split('_')
                        _prev_yr_mk = f"{int(_act_yr)-1}_{_act_mo}"
                        _prev_yr_sales = PREV_YEAR_MONTHLY_SALES.get(store, {}).get(_prev_yr_mk, {}).get(b_name)
                    if not _prev_yr_sales:
                        _prev_yr_sales = PREV_YEAR_SALES.get(store, {}).get(b_name)

                    if _prev_yr_sales and _prev_yr_sales > 0:
                        g_pct = (cur_sales_sum - _prev_yr_sales) / _prev_yr_sales * 100
                    else:
                        # MoM fallback: MONTHLY_TM 최근월 target vs PREV_MONTH_SALES
                        mom_cur = 0
                        if _cur_mk and store in MONTHLY_TM:
                            for _fk in sorted(MONTHLY_TM[store].keys(), reverse=True):
                                _fv = MONTHLY_TM[store][_fk].get(b_name, 0)
                                if _fv and _fv > 0:
                                    mom_cur = _fv
                                    break
                        mom_base = prev_benchmark_sales
                        g_pct = ((mom_cur - mom_base) / mom_base * 100) if (mom_cur > 0 and mom_base > 0) else 0.0

                    brands_list.append({
                        "name": b_name, "store": store, "category": b_cat,
                        "type": "outlet" if _is_outlet_type(b_type) else "normal",
                        "type_label": _cfg_display_label(store, b_name, b_type),
                        "total": int(round(float(row.get('total_score', 0)))),
                        "product_score": int(row.get('product_score', 0)),
                        "eff_score": int(row.get('eff_score', 0)),
                        "item": int(round(float(row.get('item_score', 0)))),
                        "zoning": cfg.get('zoning', '미분류'),
                        "dis": int(round(float(row.get('discount_score', 0)))),
                        "fresh": int(round(float(row.get('freshness_score', 0)))),
                        "best": int(round(float(row.get('best_score', 0)))),
                        "season": int(round(float(row.get('season_score', 0)))),
                        "tM": round(tM_won / 1_000_000, 1),
                        "sM": max(0.0, round(stock_amt / 1_000_000, 1)),
                        "sQ": int(stock_qty),
                        "sales_amt": cur_sales_sum / 1_000_000,
                        "prev_sales": prev_benchmark_sales / 1_000_000,
                        "growth_pct": float(g_pct),
                        "area": get_area(store, b_name),
                        "month": diag_month, "data_month": b_data_month,
                        "scoring_guide": {
                            "score_weights": {
                                "dis":   round(cfg.get('weight_discount',  0.30) * 100),
                                "fresh": round(cfg.get('weight_freshness', 0.20) * 100),
                                "sea":   round(cfg.get('weight_season',    0.15) * 100),
                                "best":  round(cfg.get('weight_best',      0.25) * 100),
                                "item":  round(cfg.get('weight_item',      0.10) * 100),
                            },
                            "item_w":  {k: round(v*100) for k, v in cfg.get('inv_weights', {}).get('item',   {}).items() if v > 0},
                            "dis_w":   {k: round(v*100) for k, v in cfg.get('inv_weights', {}).get('dis',    {}).items() if v > 0},
                            "fresh_w": {k: round(v*100) for k, v in cfg.get('inv_weights', {}).get('fresh',  {}).items() if v > 0},
                            "sea_w":   {k: round(v*100) for k, v in cfg.get('inv_weights', {}).get('season', {}).items() if v > 0},
                            "best_pct": round(cfg.get('inv_weights', {}).get('best', {}).get('store10', 0.20) * 100),
                            "is_outlet": _is_outlet_type(b_type),
                        }
                    })

                # 상세 섹션 조립 — JS lookup key와 일치시키기 위해 display_label 사용
                display_key = _cfg_display_label(store, b_name, b_type)
                if b_name not in detail_data[store]:
                    detail_data[store][b_name] = {}
                    bp_detail[store][b_name] = {}
                    best_items[store][b_name] = {}
                    action_plan[store][b_name] = {}  # [액션가이드] 브랜드별 초기화

                detail_data[store][b_name][display_key] = _build_detail(b_df, cfg, tM=tM_won)
                bp_detail[store][b_name][display_key] = _build_bp_detail(cfg, bp_df if not bp_df.empty else None)
                best_items[store][b_name][display_key] = _build_best_items(b_df)

                # [액션가이드] BP 매장 데이터 우선, 없으면 1등 매장 데이터로 집중 판매 비교
                bp_brand_df = bp_df[bp_df['brand_name'] == b_name].copy() if not bp_df.empty else pd.DataFrame()
                if bp_brand_df.empty:
                    _top_store = brand_top_store.get(b_name)
                    if _top_store and _top_store != store:
                        bp_brand_df = df[(df['store_name'] == _top_store) & (df['brand_name'] == b_name)].copy()
                        bp_brand_df.attrs['top_store_name'] = _top_store
                action_plan[store][b_name][display_key] = _build_action_plan(b_df, bp_brand_df)

        # [v4.1] 할인율점수 0 브랜드: 카테고리 요약 점수 재계산에서 제외
        # [v4.2] '전체' 점수: 카테고리별 점수를 카테고리 매출 비중으로 가중평균 (2단계 집계)
        # [v4.4] 할인율 데이터가 하나도 없는 경우 전체 브랜드 폴백으로 점수 유지
        for store in stores:
            store_brands = [b for b in brands_list if b['store'] == store]

            # Step 1: 개별 카테고리 점수 산출 (dis==0 제외, 없으면 전체 포함)
            cat_score_map = {}  # cat → (score, valid_sales_sum)
            for cat in cats:
                if cat == '전체':
                    continue
                valid = [b for b in store_brands if b['category'] == cat and b['dis'] != 0]
                if not valid:
                    # 할인율 데이터가 없는 경우 전체 브랜드로 폴백
                    valid = [b for b in store_brands if b['category'] == cat]
                if not valid:
                    cat_score_map[cat] = (0, 0.0)
                    continue
                cat_sales = sum(b['sales_amt'] for b in valid)
                if cat_sales > 0:
                    w_avg = sum(b['product_score'] * (b['sales_amt'] / cat_sales) for b in valid)
                    cat_score_map[cat] = (int(round(w_avg)), cat_sales)
                else:
                    simple = sum(b['product_score'] for b in valid) / len(valid)
                    cat_score_map[cat] = (int(round(simple)), 0.0)

            # Step 2: '전체' = 카테고리 점수를 카테고리 매출 비중으로 가중평균
            weighted_cats = [(s, t) for s, t in cat_score_map.values() if t > 0]
            if weighted_cats:
                total_cat_sales = sum(t for _, t in weighted_cats)
                전체_score = int(round(sum(s * t / total_cat_sales for s, t in weighted_cats)))
            else:
                scored = [s for s, _ in cat_score_map.values() if s > 0]
                전체_score = int(round(sum(scored) / len(scored))) if scored else 0

            # Step 3: cats 순서대로 new_scores 구성
            new_scores = []
            for cat in cats:
                if cat == '전체':
                    new_scores.append(전체_score)
                else:
                    new_scores.append(cat_score_map.get(cat, (0, 0.0))[0])
            score_data[store] = new_scores

        return {
            "CATS": cats, "STORES": stores, "scoreData": score_data, "BRANDS": brands_list,
            "DETAIL": detail_data, "BP_DETAIL": bp_detail, "BEST_ITEMS": best_items,
            "ACTION_PLAN": action_plan,
            "SCORING_GUIDE": get_category_guide(),
        }

    except Exception as e:
        import traceback
        logger.error(f"대시보드 로드 오류: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}
