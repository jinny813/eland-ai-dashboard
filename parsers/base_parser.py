"""
parsers/base_parser.py
======================
[버전] v2 — 공통 유틸 메서드 강화

ElandWorldParser에서 사용하던 유틸 메서드를 BaseParser로 이관해
모든 파서가 재사용할 수 있도록 표준화.

■ 공통 제공 메서드:
  - _read_excel_safe()     : xlsx/xls(HTML형식) 둘 다 안전하게 읽기
  - _to_df()               : DataFrame/파일 구분 처리
  - _extract_by_priority() : 컬럼명 후보군 중 우선순위대로 추출
  - _to_int()              : 쉼표 제거 후 정수 변환
  - standardize()          : 컬럼명 매핑 + 필수컬럼 보장 (기존 기능 유지)
"""

import io
import logging
from abc import ABC, abstractmethod

import pandas as pd

logger = logging.getLogger(__name__)


class BaseParser(ABC):

    # ──────────────────────────────────────────
    # 추상 메서드 (각 파서에서 반드시 구현)
    # ──────────────────────────────────────────
    @abstractmethod
    def parse_inventory(self, data) -> pd.DataFrame:
        """재고조회 엑셀 파싱 → INVENTORY_COLS 형식 반환"""
        pass

    @abstractmethod
    def parse_sales(self, data) -> pd.DataFrame:
        """판매조회 엑셀 파싱 → ['style_code','sales_qty','sales_amt','normal_price'] 형식 반환"""
        pass

    # ──────────────────────────────────────────
    # 공통 유틸 메서드
    # ──────────────────────────────────────────
    def _read_excel_safe(self, data, header_row: int = 0) -> pd.DataFrame:
        """
        xlsx → openpyxl로 읽기 시도,
        실패 또는 xls(HTML 위장 파일) → HTML 파싱으로 폴백
        """
        file_name = getattr(data, 'name', '').lower()

        if file_name.endswith('.xlsx'):
            try:
                return pd.read_excel(data, header=header_row, engine='openpyxl')
            except Exception as e:
                logger.warning(f"[BaseParser] xlsx 읽기 실패, HTML 폴백 시도: {e}")

        # xls 또는 xlsx 실패 시 → HTML 테이블 파싱 (일부 ERP 시스템은 xls를 HTML로 저장)
        try:
            if hasattr(data, 'seek'):
                data.seek(0)
            raw = data.read() if hasattr(data, 'read') else open(data, 'rb').read()

            try:
                html_str = raw.decode('utf-8')
            except UnicodeDecodeError:
                html_str = raw.decode('euc-kr', errors='replace')

            tables = pd.read_html(io.StringIO(html_str))
            if not tables:
                raise ValueError("HTML 내부 테이블 없음")
            # 가장 행이 많은 테이블 선택
            return max(tables, key=len)

        except Exception as e:
            raise ValueError(f"[BaseParser] 파일 파싱 최종 실패: {e}")

    def _to_df(self, data, header_row: int = 0) -> pd.DataFrame:
        """이미 DataFrame이면 그대로, 파일이면 read_excel_safe 호출"""
        if isinstance(data, pd.DataFrame):
            return data.copy()
        return self._read_excel_safe(data, header_row=header_row)

    def _extract_by_priority(self, df: pd.DataFrame, priority_map: dict) -> pd.DataFrame:
        """
        priority_map = { '표준컬럼명': ['후보1', '후보2', ...], ... }
        후보 목록 순서대로 실제 컬럼을 찾아 표준명으로 추출.
        중복 컬럼이 있어도 첫 번째 매칭만 사용 (안전 처리).
        """
        new_df = pd.DataFrame(index=df.index)
        for target, candidates in priority_map.items():
            found = False
            for cand in candidates:
                if cand in df.columns:
                    val = df[cand]
                    # 동명 컬럼이 여러 개일 경우 첫 번째 Series만 추출
                    if isinstance(val, pd.DataFrame):
                        val = val.iloc[:, 0]
                    new_df[target] = val
                    found = True
                    break
            if not found:
                # 미발견: 텍스트 컬럼은 빈 문자열, 수치 컬럼은 0으로 채움
                text_cols = ('style_code', 'sales_date', 'item_code', 'item_name',
                             'price_type', 'season_code', 'year')
                new_df[target] = "" if target in text_cols else 0
        return new_df

    @staticmethod
    def _to_int(series) -> pd.Series:
        """쉼표 제거 후 정수 변환 (변환 불가 값은 0)"""
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        return pd.to_numeric(
            series.astype(str).str.replace(',', '', regex=False).str.strip(),
            errors='coerce'
        ).fillna(0).astype(int)

    def standardize(self, df: pd.DataFrame, mapping: dict, required_cols: list) -> pd.DataFrame:
        """컬럼명 매핑 + 필수 컬럼 보장 (기존 기능 유지)"""
        df = df.rename(columns=mapping)
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0 if ('qty' in col or 'amt' in col) else None
        return df[required_cols]
