"""
core/data_manager.py
====================
[버그 수정 내역]

■ [v67.0] 수치 데이터 증발(0 노출) 버그 수정
  - pd.to_numeric() 처리 전 쉼표(,) 제거 및 문자열 'None' 처리 로직 강화
  - 엑셀의 서식(천단위 구분기호) 때문에 데이터가 NaN으로 변하는 현상 원천 차단
"""

import os
import json
import numpy as np
import logging
import pandas as pd
from parsers.elandworld_parser import ElandWorldParser
from parsers.indongfn_parser import IndongFnParser
from parsers.babagroup_parser import BabaGroupParser
from parsers.lottegfr_parser import LotteGfrParser
from parsers.generic_parser import GenericParser

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
            "베네통":     "Generic",
            "시슬리":     "Generic",
            "스케쳐스":   "ElandWorld",
            "직접 입력(범용)": "Generic",
        }
        self.COMPANY_PARSERS = {
            "ElandWorld": ElandWorldParser(),
            "IndongFN":   IndongFnParser(),
            "BabaGroup":  BabaGroupParser(),
            "LotteGFR":   LotteGfrParser(),
            "Generic":    GenericParser(),
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

        # [v19.0] 판매조회 파싱 및 필터링 (14일 제한 해제)
        if sales_data is not None:
            df_sales = parser.parse_sales(sales_data)
            logger.info(f"[DataManager] 판매조회 파싱 완료 (시계열 데이터 보존): {len(df_sales)}행")
        else:
            df_sales = pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'normal_price'])

        # 병합 로직 (시계열 다중 행 대응 v19.0)
        if not df_sales.empty and 'style_code' in df_sales.columns:
            # 1. 판매 데이터와 재고 데이터 병합 (Left Join)
            # 재고 데이터의 각 행(inv_uid)에 대해 매칭되는 모든 판매 기록(style_code 기준)을 모두 붙입니다.
            df_merged = pd.merge(df_inv, df_sales, on='style_code', how='left', suffixes=('', '_s'))

            # 2. 날짜 및 판매 수치 정리
            if 'sales_date' in df_merged.columns:
                df_merged['sales_date'] = df_merged['sales_date'].fillna("")
            
            # [v19.0] 재고 중복 방지 및 시계열 보존 핵심 로직
            # 동일한 인벤토리 유닛(inv_uid)에 대해 여러 날짜의 판매가 붙은 경우,
            # 날짜 내림차순으로 정렬하여 가장 최신(첫 행)에만 재고를 남기고 나머지는 0 처리합니다.
            if 'sales_date' in df_merged.columns:
                df_merged = df_merged.sort_values(by=['inv_uid', 'sales_date'], ascending=[True, False])
                
                # 중복된 inv_uid 찾기 (첫 번째 행 제외)
                mask = df_merged.duplicated(subset=['inv_uid'], keep='first')
                
                # 중복된(과거 날짜) 행들의 재고 수치 초기화
                df_merged.loc[mask, ['stock_qty', 'stock_amt']] = 0
                logger.info(f"[DataManager] 시계열 재고 마스킹 처리 완료: {mask.sum()}개 행 재고 0처리")

            # 판매 수치 컬럼 보정 (Null 처리)
            for col in ['sales_qty', 'sales_amt']:
                if col in df_merged.columns:
                    df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce').fillna(0)
        else:
            df_merged = df_inv.copy()
            if 'sales_date' not in df_merged.columns:
                df_merged['sales_date'] = ""

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

        # 품번(style_code) 없는 행 제거 (합계행 등)
        df_merged = df_merged[
            df_merged['style_code'].astype(str).str.strip().replace('', pd.NA).notna()
        ].copy()

        df_merged = df_merged.reset_index(drop=True)
        df_merged['no'] = df_merged.index

        # 마스터 컬럼 정렬
        for col in MASTER_COLUMNS:
            if col not in df_merged.columns:
                df_merged[col] = None
        df_merged = df_merged[MASTER_COLUMNS].copy()

        # [v100.0] 최종 데이터 클리닝: JSON 직렬화 오류 방지를 위한 NaN/Inf 제거
        import numpy as np
        df_merged = df_merged.replace([np.inf, -np.inf], 0)
        df_merged = df_merged.fillna({
            col: 0 for col in NUMERIC_INT_COLS + NUMERIC_FLOAT_COLS if col in df_merged.columns
        })
        df_merged = df_merged.fillna("") # 나머지 컬럼은 빈 문자열로

        return df_merged

    # ── [데이터 정규화 및 무결성 관리 유틸리티] ──

    def _load_style_master(self):
        """style_master.json 로드 유틸리티"""
        path = os.path.join(os.path.dirname(__file__), "style_master.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def update_style_master(self, new_data: dict) -> int:
        """새로운 스타일 정보를 style_master.json에 저장"""
        master = self._load_style_master()
        master.update(new_data)
        path = os.path.join(os.path.dirname(__file__), "style_master.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(master, f, ensure_ascii=False, indent=2)
        logger.info(f"[DataManager] {len(new_data)}건의 스타일 정보 업데이트 완료")
        return len(new_data)

    def scan_missing_styles(self) -> list:
        """DB(GSheet)를 스캔하여 품명이 누락된 상위 스타일 목록 추출"""
        try:
            from database.gsheet_manager import GSheetManager
            gsm = GSheetManager(sheet_name="Records")
            recs = gsm.spreadsheet.worksheet("Records").get_all_records()
            if not recs: return []
            
            df = pd.DataFrame(recs)
            master = self._load_style_master()
            
            # 판매량 기준으로 정렬하여 중요도 파악
            df['sales_qty'] = pd.to_numeric(df.get('sales_qty', 0), errors='coerce').fillna(0)
            unique_styles = df.groupby(['brand_name', 'style_code'])['sales_qty'].sum().reset_index()
            unique_styles = unique_styles.sort_values(by='sales_qty', ascending=False)
            
            missing = []
            for _, row in unique_styles.iterrows():
                s = str(row['style_code'])
                if s not in master or not master[s].get('style_name') or master[s].get('style_name') == '—':
                    missing.append({
                        "brand": row['brand_name'],
                        "style": s,
                        "sales": int(row['sales_qty'])
                    })
            return missing
        except Exception as e:
            logger.error(f"[DataManager] 스타일 스캔 실패: {e}")
            return []