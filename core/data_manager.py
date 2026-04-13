"""
core/data_manager.py
====================
[버그 수정 내역]

■ [v67.0] 수치 데이터 증발(0 노출) 버그 수정
  - pd.to_numeric() 처리 전 쉼표(,) 제거 및 문자열 'None' 처리 로직 강화
  - 엑셀의 서식(천단위 구분기호) 때문에 데이터가 NaN으로 변하는 현상 원천 차단
"""

import logging
import pandas as pd
from parsers.elandworld_parser import ElandWorldParser
from parsers.indongfn_parser import IndongFnParser
from parsers.babagroup_parser import BabaGroupParser
from parsers.lottegfr_parser import LotteGfrParser

logger = logging.getLogger(__name__)

MASTER_COLUMNS = [
    "no", "year", "season_code", "style_code", "style_name", "item_code", "item_name", "price_type",
    "stock_qty", "stock_amt", "sales_qty", "sales_amt", "normal_price", "sales_date",
    "brand_name", "store_name", "category_group", "store_type", "data_month", 
    "freshness_type", "discount_rate", "inv_uid",
]

NUMERIC_INT_COLS = [
    "year", "season_code",
    "stock_qty", "stock_amt",
    "sales_qty", "sales_amt", "normal_price",
]

NUMERIC_FLOAT_COLS = [
    "discount_rate",
]


class DataManager:
    def __init__(self):
        self.BRAND_TO_COMPANY = {
            "로엠":       "ElandWorld",
            "미쏘":       "ElandWorld",
            "리스트":     "IndongFN",
            "쉬즈미스":   "IndongFN",
            "인동팩토리(리스트,쉬즈미스)": "IndongFN",
            "JJ지고트":   "BabaGroup",
            "바바팩토리": "BabaGroup",
            "나이스클랍": "LotteGFR",
        }
        self.COMPANY_PARSERS = {
            "ElandWorld": ElandWorldParser(),
            "IndongFN":   IndongFnParser(),
            "BabaGroup":  BabaGroupParser(),
            "LotteGFR":   LotteGfrParser(),
        }

    def process_and_merge(
        self,
        brand_name: str,
        store_name: str,
        category_group: str,
        store_type: str,
        data_month: str,
        inv_data,
        sales_data=None,
    ) -> pd.DataFrame:

        company_key = self.BRAND_TO_COMPANY.get(brand_name)
        if not company_key:
            raise ValueError(f"법인 맵핑에 등록되지 않은 브랜드: {brand_name}")

        parser = self.COMPANY_PARSERS.get(company_key)
        if not parser:
            raise ValueError(f"법인 파서 누락: {company_key}")

        # 재고조회 파싱
        df_inv = parser.parse_inventory(inv_data)
        if df_inv is None or df_inv.empty:
            raise ValueError("재고조회 파싱 결과가 비어있습니다.")

        # [v21.5] 재고 데이터 고유 식별자(inv_uid) 부여
        df_inv['inv_uid'] = [f"{brand_name}_{store_name}_{i}" for i in range(len(df_inv))]

        # 판매조회 파싱
        if sales_data is not None:
            df_sales = parser.parse_sales(sales_data)
            
            # [v63.0] 최근 14일 데이터 필터링
            if not df_sales.empty and 'sales_date' in df_sales.columns:
                df_sales['sales_date_dt'] = pd.to_datetime(df_sales['sales_date'], errors='coerce')
                valid_dates = df_sales[df_sales['sales_date_dt'].notna()]
                
                if not valid_dates.empty:
                    max_date = valid_dates['sales_date_dt'].max()
                    start_date = max_date - pd.to_timedelta(13, unit='D')
                    df_sales = df_sales[df_sales['sales_date_dt'] >= start_date].copy()
                    df_sales = df_sales.drop(columns=['sales_date_dt'])
            
            logger.info(f"[DataManager] 판매조회 파싱 완료: {len(df_sales)}행")
        else:
            df_sales = pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'normal_price'])

        # 병합
        if not df_sales.empty and 'style_code' in df_sales.columns:
            # [수정 2] 판매 데이터를 품번(style_code) 기준으로 사전 집계하여 1:1 매칭 구조 생성
            # (시계열 데이터가 섞여있을 경우 발생하는 재고 데이터 중복 증폭 현상 차단)
            sales_agg = df_sales.groupby('style_code', as_index=False).agg({
                'sales_qty': 'sum',
                'sales_amt': 'sum',
                'normal_price': 'max'
            })
            
            df_inv['sales_qty'] = 0
            df_inv['sales_amt'] = 0
            
            df_merged = pd.merge(df_inv, sales_agg, on='style_code', how='left', suffixes=('', '_s'))

            if 'sales_qty_s' in df_merged.columns:
                df_merged['sales_qty'] = df_merged['sales_qty_s'].fillna(0).astype(int)
            if 'sales_amt_s' in df_merged.columns:
                df_merged['sales_amt'] = df_merged['sales_amt_s'].fillna(0).astype(int)
            if 'normal_price_s' in df_merged.columns:
                df_merged['normal_price'] = df_merged['normal_price_s'].fillna(df_merged['normal_price']).fillna(0).astype(int)

            df_merged = df_merged.drop(columns=[c for c in df_merged.columns if c.endswith('_s')], errors='ignore')
        else:
            df_merged = df_inv.copy()

        # 메타 컬럼
        df_merged['brand_name']     = brand_name
        df_merged['store_name']     = store_name
        df_merged['category_group'] = category_group
        df_merged['store_type']     = store_type
        df_merged['data_month']     = data_month

        if 'sales_date' not in df_merged.columns:
            df_merged['sales_date'] = None

        # [v67.0] 수치 타입 보장: 쉼표 제거 및 강제 정수 변환 로직 보강
        # [v67.1] 정수형 수치 타입 보장
        for col in NUMERIC_INT_COLS:
            if col in df_merged.columns:
                s = df_merged[col].astype(str).str.replace(',', '', regex=False).str.strip()
                s = s.replace(['None', 'nan', '', 'NaN', 'null'], "0", regex=False)
                df_merged[col] = pd.to_numeric(s, errors='coerce').fillna(0).astype(int)

        # [v67.1] 실수형 수치 타입 보장 (할인율 등)
        for col in NUMERIC_FLOAT_COLS:
            if col in df_merged.columns:
                s = df_merged[col].astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False).str.strip()
                s = s.replace(['None', 'nan', '', 'NaN', 'null'], "0", regex=False)
                df_merged[col] = pd.to_numeric(s, errors='coerce').fillna(0.0)

        df_merged = df_merged.reset_index(drop=True)
        df_merged['no'] = df_merged.index

        # 마스터 컬럼 정렬
        for col in MASTER_COLUMNS:
            if col not in df_merged.columns:
                df_merged[col] = None
        df_merged = df_merged[MASTER_COLUMNS].copy()

        return df_merged
