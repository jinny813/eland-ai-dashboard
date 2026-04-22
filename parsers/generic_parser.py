"""
parsers/generic_parser.py
========================
범용 파서 (직접 붙여넣기 및 표준 엑셀용)

특정 법인에 종속되지 않고, 컬럼 헤더 명칭을 기반으로 유연하게 데이터를 추출합니다.
"""

import logging
import pandas as pd
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

# 1. 반환 컬럼 표준
INVENTORY_COLS = [
    'year', 'season_code', 'style_code', 'style_name', 'item_code', 'item_name',
    'price_type', 'freshness_type', 'discount_rate', 
    'stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price',
]

# 2. 범용 컬럼 우선순위 매핑 (다양한 명칭 대응)
INV_PRIORITY = {
    'year':         ['year', '년도', '생산년도', '연도', 'Year'],
    'season_code':  ['season_code', '시즌', '시즌코드', 'Season'],
    'style_code':   ['style_code', '스타일', '스타일코드', '품번', '상품코드', '품목코드', 'Style'],
    'style_name':   ['style_name', '스타일명', '상품명', '품명', 'Style Name', 'Product Name'],
    'item_code':    ['item_code', '아이템', '아이템코드', 'Item'], 
    'item_name':    ['item_name', '아이템명', '품목명', 'Item Name'],
    'price_type':   ['price_type', '단가 유형', '단가유형', '단가', 'Price Type'],
    'freshness_type': ['freshness_type', '신선도구분', '신선도', 'Freshness'],
    'discount_rate': ['discount_rate', '할인율', '할인', 'Discount'],
    'stock_qty':    [
        '판매가능재고', '판매가능 재고', '현재고', '재고량', '수량', '재고', 'Qty', 'Stock', 'stock_qty'
    ],
    'stock_amt':    ['판매가능 재고금액', '판매가능재고금액', '재고금액', '금액', 'Amount', 'stock_amt'],
    'sales_qty':    ['판매', '판매수량', '판매량', 'Sales Qty', 'sales_qty'],
    'sales_amt':    ['실판매금액', '판매금액', '매출액', 'Sales Amt', 'sales_amt'],
    'normal_price': ['normal_price', '현단가', '정상 판매가', '정상가', 'Normal Price'],
}

SALES_PRIORITY = {
    'style_code':   ['style_code', '스타일', '스타일코드', '품번', '상품코드'],
    'sales_qty':    ['sales_qty', '수량', '판매수량', '판매량'],
    'sales_amt':    ['sales_amt', '실판매금액', '판매금액', '매출액'],
    'normal_price': ['normal_price', '정상 판매가', '현단가', '정상가'],
    'sales_date':   ['sales_date', '일자', '판매일', 'Date'],
}

class GenericParser(BaseParser):
    """표준 컬럼 명칭을 사용하는 범용 파서"""

    def __init__(self):
        self.company_name = "Generic"

    def parse_inventory(self, data) -> pd.DataFrame:
        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 필수 컬럼(품번) 존재 여부 최소 확인
        style_col = None
        for cand in INV_PRIORITY['style_code']:
            if cand in df.columns:
                style_col = cand
                break
        
        if style_col is None:
            # 헤더 없이 데이터만 있는 경우 등을 대비해 컬럼이 적으면 경고
            if len(df.columns) < 3:
                 raise ValueError("[Generic] 재고: 데이터를 인식할 수 없습니다. 헤더를 포함해 주세요.")
            # 첫 번째 컬럼을 스타일 코드로 가정 (복사 붙여넣기 시 흔한 케이스)
            style_col = df.columns[0]
            logger.warning(f"[Generic] 스타일 컬럼을 찾지 못해 첫 번째 컬럼('{style_col}')을 사용합니다.")

        # 기본 필터링 (빈 행 및 합계 행 제거)
        df = df[df[style_col].notna()].copy()
        df = df[~df[style_col].astype(str).str.contains('합계|소계|Total', na=False)].copy()

        parsed_df = self._extract_by_priority(df, INV_PRIORITY)

        # 수치 변환 레이어
        num_cols = ['stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price', 'discount_rate']
        for col in num_cols:
            if col in parsed_df.columns:
                s = parsed_df[col].astype(str).str.replace(',', '', regex=False).str.strip()
                s = s.replace(['None', 'nan', '', 'NaN', 'null'], "0", regex=False)
                # % 기호 제거
                if col == 'discount_rate':
                    s = s.str.replace('%', '', regex=False)
                parsed_df[col] = pd.to_numeric(s, errors='coerce').fillna(0)

        # 연도·시즌 정규화
        for col in ['year', 'season_code']:
            if col in parsed_df.columns:
                val = parsed_df[col].astype(str).str.replace('년', '', regex=False).str.strip()
                parsed_df[col] = pd.to_numeric(val, errors='coerce').fillna(0).astype(int)

        if 'year' in parsed_df.columns:
            parsed_df['year'] = parsed_df['year'].apply(lambda y: 2000 + y if 0 < y < 100 else y)

        # 중복 스타일 합산
        agg_cols = {
            'stock_qty': 'sum',
            'stock_amt': 'sum',
            'sales_qty': 'sum',
            'sales_amt': 'sum',
            'normal_price': 'max',
            'discount_rate': 'max',
            'year': 'first',
            'season_code': 'first',
            'style_name': 'first',
            'item_code': 'first',
            'item_name': 'first',
            'price_type': 'first',
            'freshness_type': 'first'
        }
        final_agg = {k: v for k, v in agg_cols.items() if k in parsed_df.columns}
        
        parsed_df = parsed_df.groupby('style_code', as_index=False).agg(final_agg)

        # 필수 컬럼 보장
        for col in INVENTORY_COLS:
            if col not in parsed_df.columns:
                if col in num_cols:
                    parsed_df[col] = 0
                else:
                    parsed_df[col] = ""

        logger.info(f"[Generic] 재고 파싱 완료: {len(parsed_df)}행")
        return parsed_df[INVENTORY_COLS].reset_index(drop=True)

    def parse_sales(self, data) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'normal_price'])

        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 합계 행 제거
        for check_col in df.columns:
             df = df[~df[check_col].astype(str).str.contains('합계|소계|Total', na=False)].copy()

        parsed_df = self._extract_by_priority(df, SALES_PRIORITY)
        parsed_df = parsed_df[parsed_df['style_code'].notna()].copy()

        for col in ['sales_qty', 'sales_amt', 'normal_price']:
            if col in parsed_df.columns:
                s = parsed_df[col].astype(str).str.replace(',', '', regex=False).str.strip()
                parsed_df[col] = pd.to_numeric(s, errors='coerce').fillna(0)

        if 'sales_date' in parsed_df.columns and parsed_df['sales_date'].notna().any():
            parsed_df['sales_date'] = pd.to_datetime(parsed_df['sales_date'], errors='coerce').dt.strftime('%Y-%m-%d')

        grp_cols = ['style_code']
        if 'sales_date' in parsed_df.columns and parsed_df['sales_date'].notna().any():
            grp_cols.append('sales_date')

        agg_dict = {'sales_qty': 'sum', 'sales_amt': 'sum', 'normal_price': 'max'}
        parsed_df = parsed_df.groupby(grp_cols, as_index=False).agg(agg_dict)

        for col in ['sales_qty', 'sales_amt', 'normal_price']:
            parsed_df[col] = parsed_df[col].astype(int)

        logger.info(f"[Generic] 판매 파싱 완료: {len(parsed_df)}행")
        return parsed_df
