"""
parsers/indongfn_parser.py
==========================
인동FN 법인 파서 (브랜드: 리스트, 쉬즈미스)

■ 인동FN ERP 컬럼명 특징:
  - 재고: '시즌', '품번', '아이템', '단가구분', '가용재고수량', '가용재고금액'
  - 판매: '품번', '판매수량', '판매금액', '정상가'
  - year 컬럼 없음 → 시즌코드 앞 2자리에서 연도 추출 (예: '24SS' → 2024)
"""

import logging
import pandas as pd
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

# 반환 컬럼 표준 (MASTER_COLUMNS와 일치)
INVENTORY_COLS = [
    'year', 'season_code', 'style_code', 'item_name', 'item_code',
    'price_type', 'freshness_type', 'discount_rate',
    'stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price',
]

# ──────────────────────────────────────────────────────────────
# 재고 파일 컬럼 우선순위 매핑
# ──────────────────────────────────────────────────────────────
INV_PRIORITY = {
    'season_code': ['시즌', '시즌코드', '시즌 코드'],
    'style_code':  ['품번', '스타일', '품번코드', '스타일코드'],
    'item_name':   ['아이템명', '아이템', '품목명', '품명'],
    'item_code':   ['아이템코드', '아이템 코드'],
    'price_type':  ['단가구분', '단가 구분', '단가유형', '단가 유형'],
    'stock_qty':   ['판매가능재고', '판매가 능재고', '가용재고수량', '가용 재고수량', '재고수량', '판매가능수량', '재고'],
    'stock_amt':   ['판매가능재고금액', '판매가능 재고금액', '가용재고금액', '가용 재고금액', '재고금액'],
    'freshness_type': ['신선도', '신선도구분', 'freshness_type'],
    'discount_rate': ['할인율', 'discount_rate'],
    'sales_qty':   ['판매수량', '판매'],
    'sales_amt':   ['판매금액', '실판매금액'],
    'normal_price':['정상가', '정상판매가', '현단가'],
}

# ──────────────────────────────────────────────────────────────
# 판매 파일 컬럼 우선순위 매핑
# ──────────────────────────────────────────────────────────────
SALES_PRIORITY = {
    'style_code':  ['품번', '스타일', '품번코드'],
    'sales_qty':   ['판매수량', '수량'],
    'sales_amt':   ['판매금액', '실판매금액'],
    'normal_price':['정상가', '정상판매가', '현단가'],
    'sales_date':  ['일자', '판매일자', '날짜'],
}


class IndongFnParser(BaseParser):
    """인동FN(리스트, 쉬즈미스) 전용 파서"""

    def __init__(self):
        self.company_name = "IndongFN"

    def _extract_year_from_season(self, season_series: pd.Series) -> pd.Series:
        """
        인동FN은 별도 연도 컬럼 없이 시즌코드에 연도가 포함됨
        예: '24SS' → 2024년, '23FW' → 2023년
        """
        def parse_year(val):
            s = str(val).strip()
            # 앞 2자리가 숫자인 경우 연도로 해석
            if len(s) >= 2 and s[:2].isdigit():
                return 2000 + int(s[:2])
            return 0

        return season_series.apply(parse_year)

    def _extract_season_num(self, season_series: pd.Series) -> pd.Series:
        """
        시즌 텍스트 → 숫자 코드 변환
        SS/SP(봄여름)=1, SS(여름)=2, FW/FA(가을겨울)=3, FW(겨울)=4, 기타=9
        """
        def parse_season(val):
            s = str(val).upper().strip()
            if 'SS' in s or 'SP' in s:
                return 2
            if 'FW' in s or 'FA' in s or 'AW' in s:
                return 4
            return 9  # 사계절/미분류

        return season_series.apply(parse_season)

    def parse_inventory(self, data) -> pd.DataFrame:
        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 스타일(품번) 컬럼 탐색
        style_cand = ['품번', '스타일', '품번코드', '스타일코드']
        style_col = next((c for c in style_cand if c in df.columns), None)
        if style_col is None:
            raise ValueError("[IndongFN] 재고: 스타일(품번) 컬럼을 찾을 수 없습니다.")

        # 합계·빈값 행 제거 및 스타일코드 형식 필터링
        df = df[df[style_col].notna()].copy()
        df = df[df[style_col].astype(str).str.strip() != '합계'].copy()
        # [v7.4] 품번 필터링 완화: 비어있지 않고 '합계'가 아니면 수용 (인동팩토리 비표준 품번 대응)
        df = df[df[style_col].notna()].copy()
        df[style_col] = df[style_col].astype(str).str.strip()
        df = df[~df[style_col].isin(['', '합계', 'nan', 'None'])].copy()

        parsed_df = self._extract_by_priority(df, INV_PRIORITY)

        # 인동FN은 연도 컬럼이 없으므로 시즌코드에서 추출
        parsed_df['year']        = self._extract_year_from_season(parsed_df['season_code'])
        parsed_df['season_code'] = self._extract_season_num(parsed_df['season_code'])

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

        logger.info(f"[IndongFN] 재고 파싱 완료: {len(parsed_df)}행")
        return parsed_df[INVENTORY_COLS].reset_index(drop=True)

    def parse_sales(self, data) -> pd.DataFrame:
        if data is None:
            return pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'normal_price'])

        df = self._to_df(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 합계 행 제거
        for check_col in ['품번', '스타일', '순번']:
            if check_col in df.columns:
                df = df[df[check_col].astype(str).str.strip() != '합계'].copy()

        parsed_df = self._extract_by_priority(df, SALES_PRIORITY)
        parsed_df = parsed_df[parsed_df['style_code'].notna()].copy()
        parsed_df = parsed_df[
            parsed_df['style_code'].astype(str).str.match(r'^[A-Za-z0-9]{2}', na=False)
        ].copy()

        # 판매일자 처리
        if 'sales_date' in parsed_df.columns and parsed_df['sales_date'].notna().any():
            parsed_df['sales_date'] = pd.to_datetime(
                parsed_df['sales_date'], errors='coerce'
            ).dt.strftime('%Y-%m-%d')

        # 날짜별 집계
        grp_cols = ['style_code']
        if 'sales_date' in parsed_df.columns and parsed_df['sales_date'].notna().any():
            grp_cols.append('sales_date')

        agg_dict = {'sales_qty': 'sum', 'sales_amt': 'sum', 'normal_price': 'max'}
        parsed_df = parsed_df.groupby(grp_cols, as_index=False).agg(agg_dict)

        for col in ['sales_qty', 'sales_amt', 'normal_price']:
            parsed_df[col] = self._to_int(parsed_df[col])

        logger.info(f"[IndongFN] 판매 파싱 완료: {len(parsed_df)}행")
        return parsed_df
