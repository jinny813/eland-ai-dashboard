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
from config.scoring_config import SCORING_CONFIG, get_weights_by_category
from config.brand_targets import get_tm, PREV_MONTH_SALES, PREV_YEAR_SALES
from core.html_generator import _build_detail, _build_bp_detail, _build_best_items, _build_action_plan
from config.area_config import get_area
import logging

logger = logging.getLogger(__name__)

# ── 수치 변환 유틸
def _try_float(v) -> float:
    try:
        if isinstance(v, (int, float)): return float(v)
        return float(str(v).replace(',', '').replace(' ', '').replace('%', '').strip())
    except (TypeError, ValueError):
        return 0.0


def _is_outlet_type(store_type: str) -> bool:
    """상설 매장 판단 — scoring_logic._is_outlet 과 동일 기준"""
    v = str(store_type).strip().lower()
    return v in ("상설") or "outlet" in v


def _get_config(category: str, store_type: str, brand: str) -> dict:
    """우선순위: 카테고리_매장유형_브랜드 > 카테고리_매장유형 > 기본_설정 > category_store_type base"""
    # SCORING_CONFIG 키는 '상설' 표기 통일
    normalized_type = "상설" if _is_outlet_type(store_type) else "정상"
    key_brand = f"{category}_{normalized_type}_{brand}"
    key_type  = f"{category}_{normalized_type}"
    base = get_weights_by_category(category, store_type)
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
            msg = mgr.error_msg if mgr and mgr.error_msg else "데이터가 없습니다."
            return {"error": msg}

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

        # [v126.0] year 필터: 정상 매장 중 스포츠 카테고리 제외
        # 스포츠 브랜드(스케쳐스 등)는 year 컬럼이 없고 freshness_type으로 신선도 관리
        # → year가 비어있어도 필터링하지 않도록 예외 처리
        if 'year' in df.columns and 'store_type' in df.columns and 'category_group' in df.columns:
            is_normal = ~df['store_type'].apply(_is_outlet_type)
            is_sports = df['category_group'].astype(str).str.strip() == '스포츠'
            bad_year  = df['year'].astype(str).str.strip().eq("")
            # 정상 매장이면서 스포츠가 아니면서 year가 없는 경우만 필터링
            df = df[~(is_normal & ~is_sports & bad_year)]
        
        # [v125.0] 카테고리 통합 및 자동 매핑
        if 'category_group' in df.columns:
            df.loc[df['category_group'] == '골프웨어', 'category_group'] = '신사'
            # 스케쳐스 스포츠 카테고리 강제 매핑 (데이터 유실 방지)
            df.loc[df['brand_name'].str.contains('스케쳐스', na=False), 'category_group'] = '스포츠'
        
        all_stores = [s for s in df['store_name'].unique()
                      if s and not str(s).lstrip('-').replace('.', '', 1).isdigit()]
        stores = sorted(all_stores, key=lambda s: (0 if s == 'NC신구로점' else 1, s))
        
        bp_stores = [s for s in all_stores if s.startswith("__BP__")]
        bp_df = df[df['store_name'].isin(bp_stores)] if bp_stores else pd.DataFrame()

        cats = ['전체', '여성', '스포츠', '신사', '아동', '캐주얼', '잡화']
        diag_month = f"{datetime.now().month}월"

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
        }

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
                master_list = MASTER_CATEGORY_BRANDS.get(store, {}).get(cat, [])
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
                    
                    b_type = str(b_df.iloc[0].get('store_type', '상설')).strip() or '상설'
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
                normals = ["로엠", "미쏘", "더아이잗", "에잇컨셉"]
                outlets = ["지오지아", "지오지아팩토리", "인동팩토리(리스트,쉬즈미스)"]
                
                if b_name in normals:
                    b_type = "정상"
                elif b_name in outlets:
                    b_type = "상설"
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
                
                stock_amt = stock_ref['stock_amt'].apply(_try_float).sum()
                stock_qty = stock_ref['stock_qty'].apply(_try_float).sum()
                
                # [v104.5] 매출 데이터 소급 적용 로직 (벤치마크 실적 우선 적용)
                b_data_month = str(b_df.iloc[0].get('data_month', '')).strip()
                prev_benchmark_sales = PREV_MONTH_SALES.get(store, {}).get(b_name, 0.0)
                
                # 채점용 메타데이터 주입 (면적 및 매출)
                b_df['area'] = get_area(store, b_name)
                
                if prev_benchmark_sales > 0:
                    # 벤치마크(3월) 실적이 있다면 브랜드 월 매출액으로 설정
                    b_df['brand_month_sales'] = prev_benchmark_sales
                    b_df['data_month'] = "3월"
                    b_data_month = "3월"
                else:
                    # 없다면 개별 아이템들의 매출을 합산하여 브랜드 월 매출액으로 설정
                    b_df['brand_month_sales'] = b_df['sales_amt'].sum() if 'sales_amt' in b_df.columns else 0.0
                
                scorer = AssortmentScorer(config=cfg)
                scored = scorer.score(b_df)
                
                if scored is not None and not scored.empty:
                    row = scored.iloc[0]
                    cur_sales_sum = b_df['brand_month_sales'].iloc[0] if 'brand_month_sales' in b_df.columns else 0.0

                    # [v3.3] 성장세 계산 로직 강화: YoY 우선, 없으면 MoM(PREV_MONTH_SALES) 참조
                    base_sales = PREV_YEAR_SALES.get(store, {}).get(b_name) or PREV_MONTH_SALES.get(store, {}).get(b_name)
                    g_pct = ((cur_sales_sum - base_sales) / base_sales * 100) if (base_sales and base_sales > 0) else 0.0

                    brands_list.append({
                        "name": b_name, "store": store, "category": b_cat,
                        "type": "outlet" if _is_outlet_type(b_type) else "normal", "type_label": b_type,
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
                        "month": diag_month, "data_month": b_data_month
                    })

                # 상세 섹션 조립
                if b_name not in detail_data[store]:
                    detail_data[store][b_name] = {}
                    bp_detail[store][b_name] = {}
                    best_items[store][b_name] = {}
                    action_plan[store][b_name] = {}  # [액션가이드] 브랜드별 초기화
                
                detail_data[store][b_name][b_type] = _build_detail(b_df, cfg, tM=tM_won)
                bp_detail[store][b_name][b_type] = _build_bp_detail(cfg, bp_df if not bp_df.empty else None)
                best_items[store][b_name][b_type] = _build_best_items(b_df)

                # [액션가이드] BP 매장에서 동일 브랜드 데이터만 필터링하여 액션 계획 생성
                bp_brand_df = bp_df[bp_df['brand_name'] == b_name].copy() if not bp_df.empty else pd.DataFrame()
                action_plan[store][b_name][b_type] = _build_action_plan(b_df, bp_brand_df)

        return {
            "CATS": cats, "STORES": stores, "scoreData": score_data, "BRANDS": brands_list,
            "DETAIL": detail_data, "BP_DETAIL": bp_detail, "BEST_ITEMS": best_items,
            "ACTION_PLAN": action_plan  # [액션가이드] 층장 액션 제안 데이터
        }

    except Exception as e:
        import traceback
        logger.error(f"대시보드 로드 오류: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}
