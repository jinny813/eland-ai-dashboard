"""
core/data_loader.py
===================
Google Sheets → 대시보드 JSON 변환 파이프라인

수정 내역:
- [v68.4] 전체 로직 긴급 복구 및 마스터 브랜드 리스트 도입
- NC신구로점 여성 카테고리에 4개 신규 브랜드 상시 노출 처리
- 데이터 미업로드 브랜드에 대한 0점 자리표시자(Placeholder) 생성 로직 추가
"""

import unicodedata
import pandas as pd
from datetime import datetime
from database.gsheet_manager import GSheetManager
from core.scoring_logic import AssortmentScorer
from config.scoring_config import SCORING_CONFIG, get_weights_by_category, get_category_guide
from config.brand_targets import (
    get_tm, PREV_MONTH_SALES, PREV_YEAR_SALES, MONTHLY_TM,
    PREV_YEAR_MONTHLY_SALES, CURR_MONTH_ACTUALS, normalize_brand_name,
)
from core.html_generator import _build_detail, _build_bp_detail, _build_best_items, _build_action_plan
from config.area_config import get_area
from config.store_type_config import get_store_type as _cfg_store_type, get_display_label as _cfg_display_label, BRAND_STORE_TYPES
from config.brand_targets import _normalize_month_key
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


def preprocess_raw_records(
    mgr: GSheetManager,
    raw_recs: list,
) -> tuple:
    """
    [Stage 1] 원시 레코드를 한 번만 전처리하여 cleaned DataFrame을 반환합니다.
    - DataFrame 생성 / str.strip / Unicode NFC 정규화 / 수치형 변환
    - brandmaster 로드 (GSheet API 1회)
    - storemaster_override 적용 (importlib 1회)
    - year 필터
    반환: (cleaned_df, brand_zoning_map, sorted_months)
    """
    # ── brandmaster 1회 로드 ──
    brand_master_df = mgr.load_brand_master() if mgr else None
    brand_zoning_map: dict = {}
    if brand_master_df is not None and not brand_master_df.empty:
        for _, r in brand_master_df.iterrows():
            b_name_raw = str(r.get('브랜드명', '')).strip()
            zoning_raw = str(r.get('조닝', '')).strip()
            if b_name_raw and zoning_raw:
                brand_zoning_map[b_name_raw] = zoning_raw

    df = pd.DataFrame(raw_recs)

    # ── 텍스트 컬럼 공백 제거 ──
    str_cols = ['brand_name', 'store_name', 'style_code', 'freshness_type',
                'season_code', 'store_type', 'data_month']
    for c in str_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # ── Unicode NFC 정규화 ──
    for c in ['store_name', 'brand_name', 'freshness_type', 'category_group', 'data_month']:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: unicodedata.normalize('NFC', str(x)).strip())

    # ── store_name 정규화: NC/뉴코아/동아/2001 접두사 제거 ──
    def _clean_store(name: str) -> str:
        name = str(name).strip()
        for prefix in ['NC', '뉴코아', '동아', '2001']:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        if '강남' in name:
            name = '강남점'
        elif name == '불광':
            name = '불광점'
        elif name == '쇼핑':
            name = '쇼핑점'
        return name

    if 'store_name' in df.columns:
        before_stores = df['store_name'].unique().tolist()
        df['store_name'] = df['store_name'].apply(_clean_store)
        after_stores = df['store_name'].unique().tolist()
        logger.debug("store_name 정규화 전=%s...", before_stores[:5])
        logger.debug("store_name 정규화 후=%s...", after_stores[:5])

    # ── 수치형 컬럼 변환 ──
    num_cols = ['stock_amt', 'stock_qty', 'sales_qty', 'sales_amt', 'normal_price']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(',', '', regex=False).str.strip(),
                errors='coerce'
            ).fillna(0)

    # ── storemaster_override 정적 오버라이드 (1회) ──
    try:
        import importlib
        import config.storemaster_override as sm_ov
        import config.brand_targets as _cfg_targets
        import config.area_config as _cfg_area
        import config.store_type_config as _cfg_type
        importlib.reload(sm_ov)
        if getattr(sm_ov, 'STORE_AREA', None):
            for _s, _bmap in sm_ov.STORE_AREA.items():
                _cfg_area.AREA_CONFIG.setdefault(_s, {}).update(_bmap)
        if getattr(sm_ov, 'STORE_BRAND_TYPE', None):
            for _s, _bmap in sm_ov.STORE_BRAND_TYPE.items():
                _cfg_type.BRAND_STORE_TYPES.setdefault(_s, {}).update(_bmap)
        if getattr(sm_ov, 'PREV_YEAR_MONTHLY_SALES_OVERRIDE', None):
            for _ym, _store_map in sm_ov.PREV_YEAR_MONTHLY_SALES_OVERRIDE.items():
                for _s, _bmap in _store_map.items():
                    _cfg_targets.PREV_YEAR_MONTHLY_SALES.setdefault(_s, {}).setdefault(_ym, {}).update(_bmap)
        if getattr(sm_ov, 'CURR_YEAR_MONTHLY_SALES_OVERRIDE', None):
            for _ym, _store_map in sm_ov.CURR_YEAR_MONTHLY_SALES_OVERRIDE.items():
                for _s, _bmap in _store_map.items():
                    _cfg_targets.CURR_MONTH_ACTUALS.setdefault(_s, {}).setdefault(_ym, {}).update(_bmap)
        if getattr(sm_ov, 'MONTHLY_TARGET_OVERRIDE', None):
            _cur_mo = f"{datetime.now().month:02d}"
            _cur_yr = str(datetime.now().year)
            for _ym, _store_map in sm_ov.MONTHLY_TARGET_OVERRIDE.items():
                _yr, _mo = _ym.split('_')
                for _s, _bmap in _store_map.items():
                    _cfg_targets.MONTHLY_TM.setdefault(_s, {}).setdefault(_ym, {}).update(_bmap)
                    if _yr == _cur_yr and _mo == _cur_mo:
                        _cfg_targets.STORE_BRAND_TM.setdefault(_s, {}).update(_bmap)
        logger.info("[storemaster_override] 정적 오버라이드 적용 완료")
    except ImportError:
        pass
    except Exception as _soe:
        logger.error("[storemaster_override] 적용 실패: %s", _soe)

    # ── [v185.0] storemaster 동적 오버라이드 ──
    try:
        import config.brand_targets as _cfg_targets
        import config.area_config as _cfg_area
        import config.store_type_config as _cfg_type
        
        # storemaster 데이터를 로드하여 동적으로 딕셔너리 구성
        df_sm = mgr.load_store_master() if mgr else None
        if df_sm is not None and not df_sm.empty:
            cols = df_sm.columns.tolist()
            
            # 컬럼 매핑 인덱스 찾기
            def find_col_local(df_cols, keywords):
                for kw in keywords:
                    for col in df_cols:
                        if kw.lower() in str(col).lower():
                            return col
                return None

            store_col = find_col_local(cols, ['지점', '점포', '매장'])
            brand_col = find_col_local(cols, ['브랜드', 'brand'])
            area_col  = find_col_local(cols, ['평수', '면적', 'area'])
            type_col  = find_col_local(cols, ['유형', '구분', 'type', '매장유형'])
            
            # 매출 컬럼 파싱 (25_03, 26_04 등)
            sales_cols = {}
            for col in cols:
                import re
                m = re.match(r'^(\d{2})_(\d{2})$', str(col).strip())
                if m:
                    sales_cols[('20' + m.group(1), m.group(2))] = col
                    
            # 목표 컬럼 파싱 (목표_04 등)
            target_cols = {}
            for col in cols:
                import re
                m = re.match(r'^목표_(\d{2})$', str(col).strip())
                if m:
                    target_cols[m.group(1)] = col
            
            # 브랜드/지점명 정형화 헬퍼
            def clean_brand_local(name: str) -> str:
                if not name: return ""
                return str(name).split('(')[0].strip()
                
            def clean_store_local(name: str) -> str:
                if not name: return ""
                name = str(name).strip()
                for prefix in ["NC", "뉴코아", "동아", "2001"]:
                    if name.startswith(prefix):
                        name = name[len(prefix):].strip()
                        break
                if '분당' in name:
                    name = '분당점'
                elif '강남' in name:
                    name = '강남점'
                elif name == '불광':
                    name = '불광점'
                elif name == '쇼핑':
                    name = '쇼핑점'
                return name
                
            def normalize_type_local(t: str) -> str:
                t = str(t).strip()
                return '정상' if '정상' in t else '상설'
                
            _cur_mo = f"{datetime.now().month:02d}"
            _cur_yr = str(datetime.now().year)

            for _, row in df_sm.iterrows():
                store_name = clean_store_local(row.get(store_col, ''))
                brand_name = clean_brand_local(row.get(brand_col, ''))
                if not store_name or not brand_name or store_name == 'nan' or brand_name == 'nan':
                    continue
                
                # 평수 오버라이드
                if area_col:
                    area_val = _try_float(row.get(area_col, 0))
                    if area_val > 0:
                        _cfg_area.AREA_CONFIG.setdefault(store_name, {})[brand_name] = area_val
                
                # 유형 오버라이드
                if type_col:
                    _cfg_type.BRAND_STORE_TYPES.setdefault(store_name, {})[brand_name] = normalize_type_local(row.get(type_col, '상설'))
                
                # 매출 실적 오버라이드
                for (yr, mo), col in sales_cols.items():
                    v_sales = _try_float(row.get(col, 0))
                    if v_sales > 0:
                        ym_key = f"{yr}_{mo}"
                        if yr == '2025':
                            _cfg_targets.PREV_YEAR_MONTHLY_SALES.setdefault(store_name, {}).setdefault(ym_key, {}).update({brand_name: v_sales})
                        elif yr == '2026':
                            _cfg_targets.CURR_MONTH_ACTUALS.setdefault(store_name, {}).setdefault(ym_key, {}).update({brand_name: v_sales})
                            
                # 당월 목표 오버라이드
                for mo, col in target_cols.items():
                    v_target = _try_float(row.get(col, 0))
                    if v_target > 0:
                        # 10만 이하 단위는 M 단위로 판단하여 보정
                        if 0 < v_target < 100000:
                            v_target = v_target * 1_000_000
                        _cfg_targets.MONTHLY_TM.setdefault(store_name, {}).setdefault(f"2026_{mo}", {}).update({brand_name: v_target})
                        if yr == _cur_yr and mo == _cur_mo:
                            _cfg_targets.STORE_BRAND_TM.setdefault(store_name, {}).update({brand_name: v_target})
                            
            logger.info("[storemaster] 동적 오버라이드 주입 완료")
    except ImportError:
        pass
    except Exception as _soe:
        logger.error("[storemaster_override] 적용 실패: %s", _soe)

    # ── 특수 브랜드 store_type 강제 설정 ──
    if 'brand_name' in df.columns:
        _no_year_outlet_brands = ['압소바', '더레노마']
        for _b in _no_year_outlet_brands:
            _m = df['brand_name'].str.contains(_b, na=False)
            df.loc[_m, 'store_type'] = '상설'

    # ── year 필터 ──
    if 'year' in df.columns and 'store_type' in df.columns and 'category_group' in df.columns:
        is_normal = ~df['store_type'].apply(_is_outlet_type)
        is_no_year_cat = df['category_group'].astype(str).str.strip().isin(['스포츠', '잡화', '신사'])
        bad_year = df['year'].astype(str).str.strip().eq("")
        is_fresh_new = (
            df['freshness_type'].astype(str).str.contains('신상', na=False)
            if 'freshness_type' in df.columns
            else pd.Series([False] * len(df))
        )
        _safe_stores = ['불광점', '강남점', '쇼핑점']
        is_safe_store = df['store_name'].isin(_safe_stores)
        df['sales_qty'] = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
        df['sales_amt'] = pd.to_numeric(df['sales_amt'], errors='coerce').fillna(0)
        has_sales = (df['sales_qty'] > 0) | (df['sales_amt'] > 0)
        before = len(df)
        df = df[~(is_normal & ~is_no_year_cat & bad_year & ~is_fresh_new & ~is_safe_store & ~has_sales)]
        logger.debug("year 필터 후 %d → %d행 (제거: %d)", before, len(df), before - len(df))
        logger.debug("필터 후 지점 목록: %s", df['store_name'].unique().tolist())

    # ── 카테고리 통합 ──
    if 'category_group' in df.columns:
        df.loc[df['category_group'] == '골프웨어', 'category_group'] = '신사'
        df.loc[df['category_group'] == '아동의류(특정매입)', 'category_group'] = '아동'
        if 'brand_name' in df.columns:
            df.loc[df['brand_name'].str.contains('스케쳐스', na=False), 'category_group'] = '스포츠'

    # ── 이랜드월드 브랜드 정상 매장 강제 ──
    if 'brand_name' in df.columns:
        for b in ['스파오키즈', '뉴발란스키즈']:
            mask = df['brand_name'].str.contains(b, na=False)
            df.loc[mask, 'store_type'] = '정상'

    # ── 가용 월 목록 ──
    def _get_m_num(m_str):
        try:
            mk = _normalize_month_key(str(m_str))
            if mk:
                yr, mo = mk.split('_')
                return int(yr) * 100 + int(mo)
            return 0
        except Exception:
            return 0

    available_months_raw = df['data_month'].unique()
    sorted_months = sorted(
        [m for m in available_months_raw if m],
        key=_get_m_num, reverse=True
    )

    return df, brand_zoning_map, sorted_months


def load_dashboard_data(
    mgr: GSheetManager = None,
    selected_month: str = None,
    raw_recs: list = None,
    # Stage 1 결과를 직접 주입 받을 수 있음 (속도 최적화 경로)
    _preprocessed: tuple = None,
) -> dict:
    """
    Google Sheets → 대시보드 JSON 구조 생성.
    마스터 브랜드 리스트를 통해 데이터가 없어도 특정 브랜드를 노출합니다.

    [성능 최적화]
    _preprocessed=(cleaned_df, brand_zoning_map, sorted_months) 를 주입하면
    Stage 1 전처리(137K rows 정규화 + brandmaster + storemaster) 를 건너뜁니다.
    주입하지 않으면 raw_recs / mgr 로 직접 전처리합니다 (하위 호환 경로).
    """
    try:
        # ── 연결 확인 ──
        if mgr is None:
            mgr = GSheetManager()
        if not mgr.is_connected:
            return {"error": "구글 시트 연동 실패"}

        # ── Stage 1: 전처리 (주입 우선, 없으면 직접 실행) ──
        if _preprocessed is not None:
            df, brand_zoning_map, sorted_months = _preprocessed
        else:
            # 하위 호환 경로 — raw_recs 또는 시트에서 직접 로드
            if raw_recs is not None:
                all_recs = raw_recs
            else:
                sheet = mgr.spreadsheet.worksheet("Records")
                all_recs = sheet.get_all_records()

            if not all_recs:
                return {
                    "CATS": [], "STORES": [], "scoreData": {},
                    "BRANDS": [], "DETAIL": {}, "BP_DETAIL": {},
                    "BEST_ITEMS": {}, "ACTION_PLAN": {}
                }

            df, brand_zoning_map, sorted_months = preprocess_raw_records(mgr, all_recs)

        if df.empty:
            return {
                "CATS": [], "STORES": [], "scoreData": {},
                "BRANDS": [], "DETAIL": {}, "BP_DETAIL": {},
                "BEST_ITEMS": {}, "ACTION_PLAN": {}
            }

        # ── [v17.16] 구글 시트 DB(df) 기반 실적 데이터를 brand_targets 매핑 딕셔너리에 동적으로 대량 적재 ──
        try:
            import config.brand_targets as _cfg_targets
            from config.brand_targets import _normalize_month_key, normalize_brand_name
            from config.area_config import clean_store_name
            
            valid_rows = df[
                df['store_name'].notna() & (df['store_name'] != "") &
                df['brand_name'].notna() & (df['brand_name'] != "") &
                df['data_month'].notna() & (df['data_month'] != "")
            ].copy()
            
            if not valid_rows.empty:
                valid_rows['_norm_store'] = valid_rows['store_name'].apply(clean_store_name)
                valid_rows['_norm_brand'] = valid_rows['brand_name'].apply(normalize_brand_name)
                valid_rows['_norm_month_key'] = valid_rows['data_month'].apply(_normalize_month_key)
                
                group_df = valid_rows[valid_rows['_norm_month_key'].notna()].groupby(
                    ['_norm_store', '_norm_month_key', '_norm_brand']
                )['sales_amt'].sum().reset_index()
                
                for _, r_data in group_df.iterrows():
                    st_key = r_data['_norm_store']
                    ym_key = r_data['_norm_month_key']
                    br_key = r_data['_norm_brand']
                    s_amt = float(r_data['sales_amt'])
                    
                    if s_amt > 0:
                        yr_key = ym_key.split('_')[0]
                        if yr_key == '2025':
                            # 기존 storemaster 데이터가 없을 때만 fallback으로 채움
                            existing = _cfg_targets.PREV_YEAR_MONTHLY_SALES.get(st_key, {}).get(ym_key, {}).get(br_key, 0)
                            if not existing or existing <= 0:
                                _cfg_targets.PREV_YEAR_MONTHLY_SALES.setdefault(st_key, {}).setdefault(ym_key, {}).update({br_key: s_amt})
                        elif yr_key == '2026':
                            existing = _cfg_targets.CURR_MONTH_ACTUALS.get(st_key, {}).get(ym_key, {}).get(br_key, 0)
                            if not existing or existing <= 0:
                                _cfg_targets.CURR_MONTH_ACTUALS.setdefault(st_key, {}).setdefault(ym_key, {}).update({br_key: s_amt})
                            
                logger.info("[data_loader] DB 내 과거 및 당기 실적 데이터 동적 적재 완료 (%d건)", len(group_df))
        except Exception as _e:
            logger.error("[data_loader] DB 실적 동적 적재 오류: %s", _e)

        # ── 가용 월 및 진단 월 결정 ──
        available_months = df['data_month'].unique()
        current_month = f"{datetime.now().month}월"

        if selected_month and selected_month in available_months:
            diag_month = selected_month
        elif current_month in available_months:
            diag_month = current_month
        elif sorted_months:
            diag_month = sorted_months[0]
        else:
            diag_month = current_month

        logger.debug("Selected diag_month = %s", diag_month)

        # ── 월 필터 ──
        df = df[df['data_month'] == diag_month].copy()
        logger.debug("월 필터 후 데이터 수 = %d", len(df))

        # ── 지점 목록 구성 ──
        all_stores = [s for s in df['store_name'].unique()
                      if pd.notna(s) and str(s).strip() and not str(s).lstrip('-').replace('.', '', 1).isdigit()]

        try:
            from config.storemaster_override import STORE_AREA
            for s in STORE_AREA.keys():
                if s not in all_stores:
                    all_stores.append(s)
        except BaseException:
            pass

        stores = sorted(list(set(all_stores)), key=lambda s: (0 if s == '신구로점' else (1 if s == '부천점' else 2), s))

        bp_stores = [s for s in all_stores if s.startswith("__BP__")]
        bp_df = df[df['store_name'].isin(bp_stores)] if bp_stores else pd.DataFrame()

        cats = ['전체', '여성', '아동', '신사', '캐주얼', '스포츠', '잡화']

        # [v68.4] 마스터 브랜드 리스트 (데이터 유무와 상관없이 노출할 브랜드 명시)
        MASTER_CATEGORY_BRANDS = {
            "신구로점": {
                "여성": [
                    "로엠", "미쏘", "리스트", "쉬즈미스", "JJ지고트", "나이스클랍", "바바팩토리", "베네통", "시슬리",
                    "클라비스", "더아이잗", "비씨비지", "발렌시아", "베스띠벨리", "올리비아로렌",
                    "제시뉴욕", "에잇컨셉", "샤틴", "보니스팍스", "안지크", "플라스틱아일랜드"
                ],
                "스포츠": ["스케쳐스"]
            },
            "중계점": { "여성": ["리스트", "나이스클랍"] },
            "송파점": { "여성": ["쉬즈미스"] },
            "쇼핑점": { "여성": ["로엠"] },
            "야탑점": { "여성": ["베네통", "시슬리"] },
            "강서점": { "여성": ["JJ지고트"] },
            "평촌점": { "여성": ["바바팩토리"] },
            "부천점": {
                "아동": [
                    "컬리수", "페리미츠", "베네통키즈", "아가방", "모이몰른", "뉴발란스키즈",
                    "탑텐키즈", "스파오키즈", "행텐틴즈", "NBA키즈", "폴햄키즈", "MLB키즈",
                    "앙팡스(압소바)", "블랙야크키즈", "휠라키즈", "아디다스키즈", "지프키즈", "에어워크주니어"
                ]
            },
        }

        # 관리 대상 매장(신구로, 부천 등 store_type_config에 정의된 매장)
        _MANAGED_STORES = set(BRAND_STORE_TYPES.keys())
        _normal_stores = [s for s in stores if not s.startswith("__BP__")]
        # 벤치마크 매장: 관리 대상 아닌 매장 (중계, 강서, 동아 등 1등 매장)
        _benchmark_stores = [s for s in _normal_stores if s not in _MANAGED_STORES]

        # 브랜드별 최상위 벤치마크 매장 산출 (관리 대상 매장끼리 비교 제외)
        brand_top_benchmark: dict = {}  # brand_name → top benchmark store name
        for _b in df['brand_name'].unique():
            if not _b: continue
            _b_rows = df[(df['brand_name'] == _b) & (df['store_name'].isin(_benchmark_stores))]
            _avgs = {}
            for _s in _b_rows['store_name'].unique():
                _s_sales = _b_rows[_b_rows['store_name'] == _s]['sales_amt'].apply(_try_float).sum()
                _s_area = get_area(_s, _b)
                _avgs[_s] = (_s_sales / _s_area) if _s_area > 0 else _s_sales
            if _avgs:
                brand_top_benchmark[_b] = max(_avgs, key=_avgs.get)

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
                    try:
                        score = _score_df_product(b_df, cfg)
                    except Exception as _e:
                        logger.warning(f"[P1] 채점 실패 — {store}/{brand}: {_e}")
                        score = 0
                    
                    prev_benchmark_sales = PREV_MONTH_SALES.get(store, {}).get(normalize_brand_name(brand), 0.0)
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
                normals = ["로엠", "미쏘", "에잇컨셉", "폴햄키즈", "스파오키즈", "뉴발란스키즈"]
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

                # [v176.0] 목표재고액 공식 통일: 평수 * 10만원/일 * 30일 (×2 제거)
                # - tM_won (목표매출): 전년동월×1.3 자동계산 (get_tm 1순위)
                # - tM_inv_won (목표재고액): 평수 * 100,000 * 30 (재고 회전 기준)
                _tM_adjusted = None
                _b_area_for_cap = get_area(store, b_name)
                tM_for_score = tM_won  # 채점에 사용할 tM (목표매출 기준)

                if _b_area_for_cap > 0:
                    tM_inv_won = _b_area_for_cap * 100_000.0 * 30.0 * 3.0  # 평수 * 10만 * 30일 * 3배
                    _tM_adjusted = 'cap'
                else:
                    # 평수 미설정 브랜드: 목표매출의 3배를 목표재고로 (최소 안전망)
                    tM_inv_won = tM_won * 3.0

                b_df['tM'] = tM_for_score  # 채점 로직은 목표매출 기준 사용

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
                
                # [v4.2] 당월 실적 키 계산 — 모든 월 형식 처리 ("6월", "26년 6월", "2026-06" 등)
                _cur_mk = _normalize_month_key(diag_month)

                b_data_month = str(b_df.iloc[0].get('data_month', '')).strip()
                b_df['area'] = get_area(store, b_name)
                _b_norm = normalize_brand_name(b_name)
                prev_benchmark_sales = PREV_MONTH_SALES.get(store, {}).get(_b_norm, 0.0)

                # 브랜드 월 매출: CURR_MONTH_ACTUALS 최근 가용 월 → PREV_MONTH_SALES(3월) → 합산
                # _active_mk: 실제로 사용 중인 실적 월 키 (성장률 비교 기준 결정에 사용)
                _active_mk = None
                _active_sales = 0
                if _cur_mk:
                    _norm_store = store
                    for prefix in ["NC", "뉴코아", "동아", "2001"]:
                        if _norm_store.startswith(prefix):
                            _norm_store = _norm_store[len(prefix):].strip()
                            break
                    if '분당' in _norm_store: _norm_store = '분당점'
                    elif '강남' in _norm_store: _norm_store = '강남점'
                    
                    _store_actuals = CURR_MONTH_ACTUALS.get(_norm_store, {})
                    for _try_mk in sorted(_store_actuals.keys(), reverse=True):
                        if _try_mk <= _cur_mk and isinstance(_store_actuals[_try_mk], dict):
                            v = _store_actuals[_try_mk].get(_b_norm, 0)
                            if v > 0:
                                _active_mk = _try_mk
                                _active_sales = v
                                break
                    if _active_sales == 0 and not isinstance(_store_actuals.get(_b_norm), dict):
                        _fallback_val = _store_actuals.get(_b_norm, 0)
                        if _fallback_val > 0:
                            _active_sales = _fallback_val
                            _active_mk = _cur_mk

                if _active_sales > 0:
                    b_df['brand_month_sales'] = _active_sales
                elif prev_benchmark_sales > 0:
                    b_df['brand_month_sales'] = prev_benchmark_sales
                    try:
                        _active_mk = f"{datetime.now().year}_03"
                    except Exception:
                        pass
                else:
                    b_df['brand_month_sales'] = b_df['sales_amt'].sum() if 'sales_amt' in b_df.columns else 0.0

                try:
                    scorer = AssortmentScorer(config=cfg)
                    scored = scorer.score(b_df)
                except Exception as _e:
                    logger.warning(f"[P2] 채점 실패 — {store}/{b_name}: {_e}")
                    scored = None

                if scored is not None and not scored.empty:
                    row = scored.iloc[0]
                    cur_sales_sum = b_df['brand_month_sales'].iloc[0] if 'brand_month_sales' in b_df.columns else 0.0

                    # [v4.2] 성장률: 활성 월의 전년동월과 비교 (PREV_YEAR_MONTHLY_SALES → PREV_YEAR_SALES)
                    _prev_yr_sales = None
                    if _active_mk and '_' in _active_mk:
                        _act_yr, _act_mo = _active_mk.split('_')
                        _prev_yr_mk = f"{int(_act_yr)-1}_{_act_mo}"
                        _prev_yr_sales = PREV_YEAR_MONTHLY_SALES.get(store, {}).get(_prev_yr_mk, {}).get(_b_norm)
                    if not _prev_yr_sales:
                        _prev_yr_sales = PREV_YEAR_SALES.get(store, {}).get(_b_norm)

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

                    # ── 평균 할인율 계산 (가중 평균)
                    try:
                        dis_rates = b_df['discount_rate'].apply(AssortmentScorer._parse_discount_rate).fillna(0.0) if 'discount_rate' in b_df.columns else pd.Series(0.0, index=b_df.index)
                        # -1.0은 제외하거나 0으로 보정 (파싱 에러 방지)
                        dis_rates = dis_rates.apply(lambda x: max(0.0, x))
                        qtys = pd.to_numeric(b_df['stock_qty'], errors='coerce').fillna(0.0) if 'stock_qty' in b_df.columns else pd.Series(0.0, index=b_df.index)
                        
                        total_qty = qtys.sum()
                        if total_qty > 0:
                            avg_dis = float((dis_rates * qtys).sum() / total_qty)
                        else:
                            avg_dis = float(dis_rates.mean()) if not dis_rates.empty else 0.0
                    except Exception as _e:
                        logger.warning(f"Failed to calculate avg_discount_rate: {_e}")
                        avg_dis = 0.0

                    brands_list.append({
                        "name": b_name, "store": store, "category": b_cat,
                        "type": "outlet" if _is_outlet_type(b_type) else "normal",
                        "type_label": _cfg_display_label(store, b_name, b_type),
                        "total": int(round(float(row.get('total_score', 0)))),
                        "product_score": int(row.get('product_score', 0)),
                        "eff_score": int(row.get('eff_score', 0)),
                        "item": int(round(float(row.get('item_score', 0)))),
                        "zoning": brand_zoning_map.get(b_name) or cfg.get('zoning', '미분류'),
                        "dis": int(round(float(row.get('discount_score', 0)))),
                        "avg_discount_rate": round(avg_dis, 1),
                        "fresh": int(round(float(row.get('freshness_score', 0)))),
                        "best": int(round(float(row.get('best_score', 0)))),
                        "season": int(round(float(row.get('season_score', 0)))),
                        "dis_estimated": bool(row.get('dis_estimated', False)),
                        "tM": round(tM_won / 1_000_000, 1),
                        "tM_inv": round(tM_inv_won / 1_000_000, 1),
                        "tM_adjusted": _tM_adjusted,
                        "sM": max(0.0, round(stock_amt / 1_000_000, 1)),
                        "sQ": int(stock_qty),
                        "sales_amt": cur_sales_sum / 1_000_000,
                        "prev_sales": prev_benchmark_sales / 1_000_000,
                        "prev_yr_sales_amt": (_prev_yr_sales / 1_000_000) if _prev_yr_sales else 0.0,
                        "growth_pct": float(g_pct),
                        "area": get_area(store, b_name),
                        "month": diag_month, "data_month": b_data_month,
                        "scoring_guide": {
                            "score_weights": {
                                "dis":   round(cfg.get('weight_discount',  0.30) * 100),
                                "fresh": round(cfg.get('weight_freshness', 0.20) * 100),
                                "sea":   round(cfg.get('weight_season',    0.15) * 100),
                                "best":  round(cfg.get('weight_best',      0.35) * 100),
                                "item":  round(cfg.get('weight_item',      0.00) * 100),
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

                # [액션가이드] 벤치마크 매장: 재고 확보 필요(ai_unified)는 동일 로직, 집중판매(push)는 비움
                # 관리 매장(신구로/부천): 재고 확보 + 벤치마크 1등 매장 기반 집중판매 모두 적용
                if store not in _MANAGED_STORES:
                    action_plan[store][b_name][display_key] = _build_action_plan(b_df, None)
                else:
                    bp_brand_df = bp_df[bp_df['brand_name'] == b_name].copy() if not bp_df.empty else pd.DataFrame()
                    if bp_brand_df.empty:
                        _top_benchmark = brand_top_benchmark.get(b_name)
                        if _top_benchmark:
                            bp_brand_df = df[(df['store_name'] == _top_benchmark) & (df['brand_name'] == b_name)].copy()
                            bp_brand_df.attrs['top_store_name'] = _top_benchmark
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

        import gc
        del df, all_recs
        gc.collect()

        return {
            "AVAILABLE_MONTHS": sorted_months,
            "CATS": cats, "STORES": stores, "scoreData": score_data, "BRANDS": brands_list,
            "DETAIL": detail_data, "BP_DETAIL": bp_detail, "BEST_ITEMS": best_items,
            "ACTION_PLAN": action_plan,
            "SCORING_GUIDE": get_category_guide(),
        }

    except Exception as e:
        import traceback
        import gc
        gc.collect()
        logger.error(f"대시보드 로드 오류: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}
