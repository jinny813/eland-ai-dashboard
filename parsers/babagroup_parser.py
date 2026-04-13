"""
parsers/babagroup_parser.py
===========================
바바그룹 법인 파서 (브랜드: JJ지고트, 바바팩토리)

■ 바바그룹 ERP 컬럼명 특징:
  - 재고: '생산년도', '시즌', '상품코드', '아이템명', '단가유형', '재고수량', '재고금액'
  - 판매: '상품코드', '판매수량', '판매액', '정가'
  - 시즌코드: S(봄여름)=2, F/W(가을겨울)=4 형태
"""

import logging
import pandas as pd
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

# 반환 컬럼 표준
INVENTORY_COLS = [
    'year', 'season_code', 'style_code', 'item_name', 'item_code',
    'price_type', 'freshness_type', 'discount_rate',
    'stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price',
]

# ──────────────────────────────────────────────────────────────
# 재고 파일 컬럼 우선순위 매핑
# ──────────────────────────────────────────────────────────────
INV_PRIORITY = {
    'year':        ['생산년도', '년도', '제조년도', '생산연도'],
    'season_code': ['시즌', '시즌코드', '시즌 코드'],
    'style_code':  ['상품코드', '스타일코드', '품번', '스타일'],
    'item_name':   ['아이템명', '아이템', '품목명', '상품명'],
    'item_code':   ['아이템코드', '아이템 코드', '품목코드'],
    'price_type':  ['단가유형', '단가 유형', '단가구분'],
    'stock_qty':   ['판매가능재고', '판매가 능재고', '재고수량', '가용재고수량', '재고'],
    'stock_amt':   ['판매가능재고금액', '판매가능 재고금액', '재고금액', '가용재고금액'],
    'freshness_type': ['신선도', '신선도구분', 'freshness_type'],
    'discount_rate': ['할인율', 'discount_rate'],
    'sales_qty':   ['판매수량', '판매'],
    'sales_amt':   ['판매액', '판매금액', '실판매금액'],
    'normal_price':['정가', '정상가', '현단가', '공급가'],
}

# ──────────────────────────────────────────────────────────────
# 판매 파일 컬럼 우선순위 매핑
# ──────────────────────────────────────────────────────────────
SALES_PRIORITY = {
    'style_code':  ['상품코드', '스타일코드', '품번'],
    'sales_qty':   ['판매수량', '수량'],
    'sales_amt':   ['판매액', '판매금액', '실판매금액'],
    'normal_price':['정가', '정상가', '현단가'],
    'sales_date':  ['일자', '판매일자', '날짜'],
}


class BabaGroupParser(BaseParser):
    """바바그룹(JJ지고트, 바바팩토리) 전용 파서"""

    def __init__(self):
        self.company_name = "BabaGroup"

    def _normalize_season_code(self, season_series: pd.Series) -> pd.Series:
        """
        바바그룹 시즌 텍스트 → 표준 숫자 코드 변환
        S/SS = 여름(2), F/FW/W = 겨울(4), 기타 = 사계절(9)
        """
        def parse(val):
            s = str(val).upper().strip()
            if s in ('S', 'SS', 'SP', 'SU'):
                return 2
            if s in ('F', 'FW', 'W', 'AW', 'FA'):
                return 4
            return 9
        return season_series.apply(parse)

    def _normalize_year(self, year_series: pd.Series) -> pd.Series:
        """연도 값 정규화: 24 → 2024, 2024 → 2024"""
        def parse(val):
            try:
                y = int(str(val).replace('년', '').strip())
                return 2000 + y if y < 100 else y
            except (ValueError, TypeError):
                return 0
        return year_series.apply(parse)

    def parse_inventory(self, data) -> pd.DataFrame:
        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 스타일 컬럼 탐색
        style_cand = ['상품코드', '스타일코드', '품번', '스타일']
        style_col = next((c for c in style_cand if c in df.columns), None)
        if style_col is None:
            raise ValueError("[BabaGroup] 재고: 스타일(상품코드) 컬럼을 찾을 수 없습니다.")

        # 합계·빈값 행 제거
        df = df[df[style_col].notna()].copy()
        df = df[df[style_col].astype(str).str.strip() != '합계'].copy()
        # 바바그룹 상품코드: 영문+숫자 혼합 (예: JG240001, BF24001)
        df = df[df[style_col].astype(str).str.match(r'^[A-Za-z]{1,3}[0-9]', na=False)].copy()

        parsed_df = self._extract_by_priority(df, INV_PRIORITY)

        # 연도·시즌 정규화
        parsed_df['year']        = self._normalize_year(parsed_df['year'])
        parsed_df['season_code'] = self._normalize_season_code(parsed_df['season_code'])

        # 수치 변환 레이어 (할인율 포함)
        num_cols = ['stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price', 'discount_rate']
        for col in num_cols:
            if col in parsed_df.columns:
                s = parsed_df[col].astype(str).str.replace(',', '', regex=False).str.strip()
                s = s.replace(['None', 'nan', '', 'NaN', 'null'], "0", regex=False)
                parsed_df[col] = pd.to_numeric(s, errors='coerce').fillna(0)

        # [v7.3] 중복 스타일 합산 (사용자 요청: 스타일코드 기준으로 합산)
        agg_cols = {
            'stock_qty': 'sum', 'stock_amt': 'sum', 'sales_qty': 'sum', 'sales_amt': 'sum',
            'normal_price': 'max', 'discount_rate': 'max', 'year': 'first', 'season_code': 'first',
            'style_name': 'first', 'item_code': 'first', 'item_name': 'first', 'price_type': 'first', 'freshness_type': 'first'
        }
        final_agg = {k: v for k, v in agg_cols.items() if k in parsed_df.columns}
        parsed_df = parsed_df.groupby('style_code', as_index=False).agg(final_agg)

        # 필수 컬럼 보장
        for col in INVENTORY_COLS:
            if col not in parsed_df.columns:
                parsed_df[col] = 0 if col in num_cols else ""

        logger.info(f"[BabaGroup] 재고 파싱 완료: {len(parsed_df)}행")
        return parsed_df[INVENTORY_COLS].reset_index(drop=True)

    def parse_sales(self, data) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'normal_price'])

        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        for check_col in ['상품코드', '스타일코드', '순번']:
            if check_col in df.columns:
                df = df[df[check_col].astype(str).str.strip() != '합계'].copy()

        parsed_df = self._extract_by_priority(df, SALES_PRIORITY)
        parsed_df = parsed_df[parsed_df['style_code'].notna()].copy()
        parsed_df = parsed_df[
            parsed_df['style_code'].astype(str).str.match(r'^[A-Za-z]{1,3}[0-9]', na=False)
        ].copy()

        if 'sales_date' in parsed_df.columns and parsed_df['sales_date'].notna().any():
            parsed_df['sales_date'] = pd.to_datetime(
                parsed_df['sales_date'], errors='coerce'
            ).dt.strftime('%Y-%m-%d')

        grp_cols = ['style_code']
        if 'sales_date' in parsed_df.columns and parsed_df['sales_date'].notna().any():
            grp_cols.append('sales_date')

        agg_dict = {'sales_qty': 'sum', 'sales_amt': 'sum', 'normal_price': 'max'}
        parsed_df = parsed_df.groupby(grp_cols, as_index=False).agg(agg_dict)

        for col in ['sales_qty', 'sales_amt', 'normal_price']:
            parsed_df[col] = self._to_int(parsed_df[col])

        logger.info(f"[BabaGroup] 판매 파싱 완료: {len(parsed_df)}행")
        return parsed_df
