"""
parsers/babagroup_parser.py
===========================
바바그룹 법인 파서 (브랜드: JJ지고트, 바바팩토리)

■ [v100.5] 최종 정밀 수정 내역:
  1. JJ지고트 특유의 이중 헤더(총재고/처리중재고/가용 하위 수량/금액) 완벽 지원
  2. 할인율 공식: (TAG금액 - 매가) / TAG금액 * 100
  3. 재고단가 공식: 최초판매금액 / 수량
  4. 판매금액 계산: 실판매금액(단가) * 수량(판매수)
  5. 연도 자동 추측 제거 (사용자 요청)
"""

import logging
import pandas as pd
import numpy as np
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

# 반환 컬럼 표준
INVENTORY_COLS = [
    'year', 'season_code', 'style_code', 'item_name', 'item_code', 'price_type',
    'freshness_type', 'discount_rate', 'stock_qty', 'stock_amt', 'sales_qty', 'sales_amt', 'normal_price'
]

# ──────────────────────────────────────────────────────────────
# 재고 파일 컬럼 우선순위 매핑 (이중 헤더 병합 명칭 포함)
# ──────────────────────────────────────────────────────────────
INV_PRIORITY = {
    'year':        ['생산년도', '년도', '제조년도', '생산연도', 'YEAR', '연도'],
    'season_code': ['시즌', '시즌코드', '계절'],
    'style_code':  ['품번', '상품코드', '스타일코드', '모델명'],
    'item_name':   ['아이템명', '아이템', '품목명', '상품명', 'ITEM_NAME'],
    'item_code':   ['아이템코드', '품목코드', '복종코드', 'ITEM_CODE'],
    'price_type':  ['판매구분', '단가유형', '구분'],
    'stock_qty':   ['총재고_수량', '가용_수량', '재고수량', '재고', '수량'],
    'stock_amt':   ['총재고_최초판매금액', '총재고_TAG금액', '재고금액', '최초판매금액'],
    'tag_price':   ['총재고_TAG금액', 'TAG금액', '최초판매가', '정상가'],
    'selling_price':['총재고_매가', '매가', '판매가', '현판매가'],
    'freshness_type': ['신선도', '신선도구분'],
    # [v100.6] 재고 파일 내 판매 데이터 대응 추가
    'sales_qty':   ['판매_합계', '판매_판매', '판매수량', '판매수'],
    'sales_amt':   ['판매_매가', '판매액', '실판매금액'] 
}

# ──────────────────────────────────────────────────────────────
# 판매 파일 컬럼 우선순위 매핑
# ──────────────────────────────────────────────────────────────
SALES_PRIORITY = {
    'style_code':  ['품번', '상품코드', '스타일코드', '모델명'],
    'sales_qty':   ['수량', '판매수량', '실판매수량', '판매수'],
    'sales_amt_unit': ['실판매금액', '현판매금액', '현판매가', '판매액'], # 개당 단가로 수신됨
    'normal_price':['TAG가', 'TAG금액', '최초판매가', '정상가'],
    'sales_date':  ['판매일자', '일자', '매출일자', '날짜'],
}

class BabaGroupParser(BaseParser):
    """바바그룹(JJ지고트, 바바팩토리) 전용 파서 [v100.5]"""

    def __init__(self):
        self.company_name = "BabaGroup"

    def _normalize_year(self, year_series: pd.Series) -> pd.Series:
        def parse(val):
            try:
                s = str(val).strip().replace('년', '')
                if not s or s in ('None', 'nan', '0'): return 0
                y = int(s)
                return 2000 + y if y < 100 else y
            except: return 0
        return year_series.apply(parse)

    def _season_from_style_char(self, s: str) -> int:
        """품번 3번째 글자 기반 시즌 코드 판별"""
        try:
            val = str(s).strip()
            if len(val) < 3: return 0
            ch = val[2].upper()
            if ch in ('1', '2', '3'): return 1
            if ch in ('4', '5', '6'): return 2
            if ch in ('7', '8', '9'): return 3
            if ch in ('A', 'B', 'C'): return 4
            return 0
        except: return 0

    def _find_header_row(self, data) -> pd.DataFrame:
        """이중 헤더 지원: 'No' 행과 그 아래 행을 병합하여 고유 컬럼명 생성"""
        raw = self._to_df(data) if isinstance(data, pd.DataFrame) else self._read_excel_safe(data, header_row=None)
        
        for i in range(len(raw)):
            row_vals = [str(v).strip().upper() for v in raw.iloc[i].values]
            if 'NO' in row_vals or '품번' in row_vals:
                # 메인 헤더 발견
                main_header = [str(v).strip() if str(v).strip() != 'nan' else "" for v in raw.iloc[i].values]
                
                # 다음 행이 서브 헤더인지 확인 (수량, 매가 등이 포함되어 있는지)
                if i + 1 < len(raw):
                    next_row = [str(v).strip() if str(v).strip() != 'nan' else "" for v in raw.iloc[i+1].values]
                    if any(k in "".join(next_row) for k in ['수량', 'TAG', '매가', '최초']):
                        logger.info(f"[BabaGroup] 이중 헤더 감지 (행 {i}, {i+1}). 병합 처리.")
                        
                        last_m = ""
                        merged_header = []
                        for m, s in zip(main_header, next_row):
                            m_raw = str(m).strip()
                            s_raw = str(s).strip()
                            
                            # 메인 헤더 Forward Fill (병합 셀 대응)
                            current_m = m_raw if m_raw and 'Unnamed' not in m_raw else last_m
                            last_m = current_m
                            
                            if current_m and s_raw:
                                # 공백 제거 후 병합
                                merged_header.append(f"{current_m}_{s_raw}".replace(" ", ""))
                            else:
                                merged_header.append((m_raw or s_raw or "unknown").replace(" ", ""))
                        
                        raw.columns = merged_header
                        return raw.iloc[i+2:].reset_index(drop=True)
                
                # 단일 헤더인 경우
                raw.columns = main_header
                return raw.iloc[i+1:].reset_index(drop=True)
        return raw.reset_index(drop=True)

    def parse_inventory(self, data) -> pd.DataFrame:
        if data is None: return pd.DataFrame(columns=INVENTORY_COLS)

        df = self._find_header_row(data)
        df.columns = [str(c).strip() for c in df.columns]

        # 1. 컬럼 매핑
        parsed_tmp = self._extract_by_priority(df, INV_PRIORITY)
        
        # 2. 스타일 코드 필터링
        if 'style_code' not in parsed_tmp.columns or parsed_tmp['style_code'].isna().all():
            logger.warning("[BabaGroup-Inv] 스타일 코드를 찾지 못해 종료합니다.")
            return pd.DataFrame(columns=INVENTORY_COLS)

        parsed_tmp['style_code'] = parsed_tmp['style_code'].astype(str).str.strip().str.upper()
        # 유효 품번 패턴 필터 (영문+숫자 혼합)
        mask = parsed_tmp['style_code'].str.match(r'^[A-Za-z]{1,6}[0-9]', na=False)
        parsed_tmp = parsed_tmp[mask].copy()

        # 3. 수치 변환 도우미
        def _to_num(series):
            return pd.to_numeric(series.astype(str).str.replace(',', '', regex=False).str.strip(), errors='coerce').fillna(0)

        # 4. 수치 계산 (할인율 및 단가)
        s_qty = _to_num(parsed_tmp['stock_qty'])
        s_amt = _to_num(parsed_tmp['stock_amt'])
        tag_p = _to_num(parsed_tmp['tag_price'])
        sell_p = _to_num(parsed_tmp['selling_price'])
        
        # [v100.6] 판매 수치 추출
        sales_q = _to_num(parsed_tmp['sales_qty']) if 'sales_qty' in parsed_tmp.columns else pd.Series(0, index=parsed_tmp.index)
        sales_a = _to_num(parsed_tmp['sales_amt']) if 'sales_amt' in parsed_tmp.columns else pd.Series(0, index=parsed_tmp.index)

        # 단가(normal_price) = 재고금액 / 재고수량
        normal_p = (s_amt / s_qty.where(s_qty != 0)).fillna(0).astype(int)
        parsed_tmp['normal_price'] = normal_p
        
        # 할인율(discount_rate) = (TAG금액 - 매가) / TAG금액 (구글 시트 서식 호환을 위해 소수점 형태 저장)
        parsed_tmp['discount_rate'] = ((tag_p - sell_p) / tag_p.where(tag_p != 0)).fillna(0).round(3)
        
        # [v100.6] 판매금액 폴백: 금액이 0이고 단가가 있으면 단가 * 수량으로 계산
        if sales_a.sum() == 0 and sales_q.sum() > 0:
            sales_a = normal_p * sales_q
            logger.info("[BabaGroup-Inv] 판매금액 부재로 단가 기반 추산 적용")

        parsed_tmp['stock_qty'] = s_qty
        parsed_tmp['stock_amt'] = s_amt
        parsed_tmp['sales_qty'] = sales_q
        parsed_tmp['sales_amt'] = sales_a
        
        # 5. 연도 및 시즌
        parsed_tmp['year'] = self._normalize_year(parsed_tmp['year'])
        parsed_tmp['season_code'] = parsed_tmp['style_code'].apply(self._season_from_style_char)

        # [v100.6] ITEM_CODE 폴백 (비어있으면 STYLE_CODE 복사)
        if 'item_code' in parsed_tmp.columns:
            empty_mask = (parsed_tmp['item_code'].astype(str).str.strip() == "") | (parsed_tmp['item_code'] == 0)
            parsed_tmp.loc[empty_mask, 'item_code'] = parsed_tmp.loc[empty_mask, 'style_code']

        # 중복 스타일 합산
        agg_cols = {
            'stock_qty': 'sum', 'stock_amt': 'sum', 
            'sales_qty': 'sum', 'sales_amt': 'sum',
            'normal_price': 'max', 'discount_rate': 'max',
            'year': 'first', 'season_code': 'first', 'item_name': 'first', 'item_code': 'first',
            'price_type': 'first', 'freshness_type': 'first'
        }
        final_agg = {k: v for k, v in agg_cols.items() if k in parsed_tmp.columns}
        parsed_df = parsed_tmp.groupby('style_code', as_index=False).agg(final_agg)

        # 필수 컬럼 보장
        for col in INVENTORY_COLS:
            if col not in parsed_df.columns:
                parsed_df[col] = 0 if col in ['sales_qty', 'sales_amt'] else ""

        return parsed_df[INVENTORY_COLS].reset_index(drop=True)

    def parse_sales(self, data) -> pd.DataFrame:
        if data is None: return pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'sales_date'])

        df = self._find_header_row(data)
        df.columns = [str(c).strip() for c in df.columns]

        parsed_tmp = self._extract_by_priority(df, SALES_PRIORITY)
        
        if 'style_code' not in parsed_tmp.columns or parsed_tmp['style_code'].isna().all():
            return pd.DataFrame(columns=['style_code', 'sales_qty', 'sales_amt', 'sales_date'])

        # 수치 보정
        qty = pd.to_numeric(parsed_tmp['sales_qty'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
        amt_unit = pd.to_numeric(parsed_tmp['sales_amt_unit'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
        
        # [최종 공식] sales_amt = 단가 * 수량
        parsed_tmp['sales_qty'] = qty.astype(int)
        parsed_tmp['sales_amt'] = (amt_unit * qty).astype(int)
        
        # 날짜 정규화
        parsed_tmp['sales_date'] = pd.to_datetime(parsed_tmp['sales_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 그룹화
        parsed_tmp['style_code'] = parsed_tmp['style_code'].astype(str).str.strip().str.upper()
        grp_cols = ['style_code']
        if 'sales_date' in parsed_tmp.columns: grp_cols.append('sales_date')

        agg_res = parsed_tmp.groupby(grp_cols, as_index=False).agg({'sales_qty': 'sum', 'sales_amt': 'sum'})
        return agg_res
