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
from config.scoring_config import SCORING_CONFIG, _WOMEN_NORMAL_BASE, _WOMEN_OUTLET_BASE
from config.brand_targets import get_tm
from core.html_generator import _build_detail, _build_bp_detail, _build_best_items
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
    """우선순위: 카테고리_매장유형_브랜드 > 카테고리_매장유형 > 기본_설정 > store_type base"""
    # SCORING_CONFIG 키는 '상설' 표기 통일
    normalized_type = "상설" if _is_outlet_type(store_type) else "정상"
    key_brand = f"{category}_{normalized_type}_{brand}"
    key_type  = f"{category}_{normalized_type}"
    base = _WOMEN_OUTLET_BASE if _is_outlet_type(store_type) else _WOMEN_NORMAL_BASE
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
            return {"error": "데이터가 없습니다."}

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

        # 2. 기초 변수 초기화
        # year 필터는 정상 매장(로엠 등)에만 적용 — 상설 브랜드는 year가 없어도 discount_rate 기반으로 채점
        if 'year' in df.columns and 'store_type' in df.columns:
            is_normal = ~df['store_type'].apply(_is_outlet_type)
            bad_year  = df['year'].astype(str).str.strip().eq("")
            df = df[~(is_normal & bad_year)]
        
        all_stores = [s for s in df['store_name'].unique()
                      if s and not str(s).lstrip('-').replace('.', '', 1).isdigit()]
        stores = sorted(all_stores, key=lambda s: (0 if s == 'NC신구로점' else 1, s))
        
        bp_stores = [s for s in all_stores if s.startswith("__BP__")]
        bp_df = df[df['store_name'].isin(bp_stores)] if bp_stores else pd.DataFrame()

        cats = ['전체', '여성', '스포츠', '캐주얼', '잡화', '아동', '신사', '골프웨어']
        diag_month = f"{datetime.now().month}월"

        # [v68.4] 마스터 브랜드 리스트 (데이터 유무와 상관없이 노출할 브랜드 명시)
        MASTER_CATEGORY_BRANDS = {
            "NC신구로점": {
                "여성": ["로엠", "인동팩토리(리스트,쉬즈미스)", "JJ지고트", "나이스클랍", "바바팩토리"]
            }
        }

        score_data  = {}
        brands_list = []
        detail_data = {}
        bp_detail   = {}
        best_items  = {}

        for store in stores:
            st_df = df[df['store_name'] == store]
            score_data[store] = []
            detail_data[store] = {}
            bp_detail[store] = {}
            best_items[store] = {}

            # 1. 카테고리별 요약 점수 계산 (P1)
            for cat in cats:
                master_list = MASTER_CATEGORY_BRANDS.get(store, {}).get(cat, [])
                target_df = st_df if cat == '전체' else st_df[st_df['category_group'] == cat]
                
                actual_brands = target_df['brand_name'].unique().tolist() if not target_df.empty else []
                # 마스터 브랜드와 실제 데이터 브랜드 합집합
                loop_brands = list(set(actual_brands + master_list))

                if not loop_brands:
                    score_data[store].append(0)
                    continue

                cat_scores = []
                for brand in loop_brands:
                    b_df = target_df[target_df['brand_name'] == brand].copy()
                    if b_df.empty:
                        cat_scores.append(0)
                        continue
                    
                    b_type = str(b_df.iloc[0].get('store_type', '상설')).strip() or '상설'
                    cfg = _get_config(cat if cat != '전체' else "여성", b_type, brand)
                    b_df['tM'] = get_tm(brand_name=brand, store_name=store, month=diag_month)
                    cat_scores.append(_score_df(b_df, cfg))

                avg = int(round(sum(cat_scores)/len(cat_scores))) if cat_scores else 0
                score_data[store].append(avg)

            # 2. 브랜드별 상세 데이터 구축 (P2)
            actual_brands = st_df['brand_name'].unique().tolist()
            all_target_brands = set(actual_brands)
            for m_list in MASTER_CATEGORY_BRANDS.get(store, {}).values():
                all_target_brands.update(m_list)

            for b_name in all_target_brands:
                if not b_name: continue
                b_df = st_df[st_df['brand_name'] == b_name].copy()
                
                # 데이터가 없는 브랜드 (마스터 리스트 기반) 처리
                if b_df.empty:
                    b_cat = "여성"
                    for mc, ml in MASTER_CATEGORY_BRANDS.get(store, {}).items():
                        if b_name in ml: b_cat = mc; break
                    
                    b_type = "정상" if b_name in ["로엠"] else "상설"
                    tM_won = get_tm(brand_name=b_name, store_name=store, month=diag_month)

                    brands_list.append({
                        "name": b_name, "store": store, "category": b_cat,
                        "type": "outlet" if _is_outlet_type(b_type) else "normal", "type_label": b_type,
                        "total": 0, "dis": 0, "fresh": 0, "best": 0, "season": 0,
                        "tM": round(tM_won / 1_000_000, 1), "sM": 0.0, "sQ": 0,
                        "month": diag_month, "data_month": ""
                    })
                    continue

                # 데이터가 있는 브랜드 처리
                b_cat = str(b_df.iloc[0].get('category_group', '여성')).strip() or '여성'
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
                
                scorer = AssortmentScorer(config=cfg)
                scored = scorer.score(b_df)
                if scored is not None and not scored.empty:
                    row = scored.iloc[0]
                    brands_list.append({
                        "name": b_name, "store": store, "category": b_cat,
                        "type": "outlet" if _is_outlet_type(b_type) else "normal", "type_label": b_type,
                        "total": int(round(float(row.get('total_score', 0)))),
                        "dis": int(round(float(row.get('discount_score', 0)))),
                        "fresh": int(round(float(row.get('freshness_score', 0)))),
                        "best": int(round(float(row.get('best_score', 0)))),
                        "season": int(round(float(row.get('season_score', 0)))),
                        "tM": round(tM_won / 1_000_000, 1),
                        "sM": max(0.0, round(stock_amt / 1_000_000, 1)),
                        "sQ": int(stock_qty),
                        "month": diag_month, "data_month": str(b_df.iloc[0].get('data_month', ''))
                    })

                # 상세 섹션 조립
                if b_name not in detail_data[store]:
                    detail_data[store][b_name] = {}
                    bp_detail[store][b_name] = {}
                    best_items[store][b_name] = {}
                
                detail_data[store][b_name][b_type] = _build_detail(b_df, cfg, tM=tM_won)
                bp_detail[store][b_name][b_type] = _build_bp_detail(cfg, bp_df if not bp_df.empty else None)
                best_items[store][b_name][b_type] = _build_best_items(b_df)

        return {
            "CATS": cats, "STORES": stores, "scoreData": score_data, "BRANDS": brands_list,
            "DETAIL": detail_data, "BP_DETAIL": bp_detail, "BEST_ITEMS": best_items
        }

    except Exception as e:
        import traceback
        logger.error(f"대시보드 로드 오류: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}
