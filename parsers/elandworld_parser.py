"""
parsers/elandworld_parser.py
============================
이랜드월드 법인 파서 (브랜드: 로엠, 미쏘)

[변경 내역] v9
- [v67.5] 사용자 제보 반영: stock_qty 매핑 최우선 순위에 '판매가 능재고' (L열) 추가
- [v67.4] stock_qty 매핑 강화: '현재고', '판매가능 재고', '수량' 등 다양한 명칭 대응
- [v67.0] 수치 변환 로직 보강: 쉼표(,) 제거 전처리 추가
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

# 2. 재고 파일 컬럼 우선순위 매핑
# [v67.5] 사용자 제보: '판매가 능재고' 명칭 최우선 추가
INV_PRIORITY = {
    'year':         ['year', '년도', '생산년도'],
    'season_code':  ['season_code', '시즌', '시즌코드'],
    'style_code':   ['style_code', '스타일', '스타일코드'],
    'style_name':   ['style_name', '스타일명', '상품명', '품명'],
    'item_code':    ['item_code', '아이템', '아이템코드'], 
    'item_name':    ['item_name', '아이템명', '품목명'],
    'price_type':   ['price_type', '단가 유형', '단가유형', '단가'],
    'freshness_type': ['freshness_type', '신선도구분', '신선도'],
    'discount_rate': ['discount_rate', '할인율'],
    'stock_qty':    [
        '판매가 능재고', '판매가능재고', '판매가능 재고', '판매가 능 재고', 
        '현재고', '재고량', '판매가능', '수량', '재고', 'stock_qty'
    ],
    'stock_amt':    ['판매가능 재고금액', '판매가능재고금액', '재고금액', 'stock_amt'],
    'sales_qty':    ['판매', '판매수량', '판매량', 'sales_qty'],
    'sales_amt':    ['실판매금액', '판매금액', '매출액', 'sales_amt'],
    'normal_price': ['normal_price', '현단가', '정상 판매가', '정상가', 'normal_price'],
}

SALES_PRIORITY = {
    'style_code':   ['style_code', '스타일', '스타일코드'],
    'sales_qty':    ['sales_qty', '수량', '판매수량'],
    'sales_amt':    ['sales_amt', '실판매금액', '판매금액'],
    'normal_price': ['normal_price', '정상 판매가', '현단가'],
    'sales_date':   ['sales_date', '일자'],
}

class ElandWorldParser(BaseParser):
    """이랜드월드(로엠, 미쏘) 전용 파서"""

    def __init__(self):
        self.company_name = "ElandWorld"

    def parse_inventory(self, data) -> pd.DataFrame:
        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 스타일 컬럼 탐색
        style_cand = ['스타일', '스타일코드', 'style_code', 'Style']
        style_col = next((c for c in style_cand if c in df.columns), None)
        if style_col is None:
            raise ValueError("[ElandWorld] 재고: 스타일 컬럼을 찾을 수 없습니다.")

        # 기본 필터링
        df = df[df[style_col].notna()].copy()
        df = df[df[style_col].astype(str).str.strip() != '합계'].copy()
        df = df[df[style_col].astype(str).str.match(r'^[A-Za-z]{2}', na=False)].copy()

        parsed_df = self._extract_by_priority(df, INV_PRIORITY)

        # 수치 변환 레이어
        num_cols = ['stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price', 'discount_rate']
        for col in num_cols:
            if col in parsed_df.columns:
                s = parsed_df[col].astype(str).str.replace(',', '', regex=False).str.strip()
                s = s.replace(['None', 'nan', '', 'NaN', 'null'], "0", regex=False)
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

        logger.info(f"[ElandWorld] 재고 파싱 완료: {len(parsed_df)}행")
        return parsed_df[INVENTORY_COLS].reset_index(drop=True)

    def parse_sales(self, data) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'normal_price'])

        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        for check_col in ['순번', '스타일', 'style_code']:
            if check_col in df.columns:
                df = df[df[check_col].astype(str).str.strip() != '합계'].copy()

        parsed_df = self._extract_by_priority(df, SALES_PRIORITY)
        parsed_df = parsed_df[parsed_df['style_code'].notna()].copy()
        parsed_df = parsed_df[parsed_df['style_code'].astype(str).str.match(r'^[A-Za-z]{2}', na=False)].copy()

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

        logger.info(f"[ElandWorld] 판매 파싱 완료: {len(parsed_df)}행")
        return parsed_df
