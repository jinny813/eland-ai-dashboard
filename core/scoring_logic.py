import pandas as pd
from datetime import datetime, timedelta


def _is_outlet(store_type_val: str) -> bool:
    """상설 매장 여부 판단. '복합'은 상설 로직 동일 적용"""
    v = str(store_type_val).strip().lower()
    return any(k in v for k in ["상설", "outlet", "아울렛", "팩토리", "factory", "복합"]) or v.startswith("상")


# ── 채점 상수 ──────────────────────────────────────────────────────────
# 구간 점수 가중치 = 구간 점수 / 지표 내 점수 합계 (점수 0인 구간 제외 후 정규화)
# 재고비중(목표 배분용)과 점수(가중치 산출용)는 역할이 다름 — 절대 혼용 금지

DIS_SCORES = {
    # 할인율 구간별 점수. 0점 구간은 점수 가중치 산출 시 제외.
    # 경계값 기준: 이상(≥) / 미만(<), 높은 구간부터 체크
    "normal": {"s70": 0, "s50": 5, "s30": 10, "s10": 15},   # 합계 30점
    "outlet": {"s70": 10, "s50": 10, "s30": 15, "s10": 5},  # 합계 40점
}
FRESH_SCORES = {
    # 신선도 구간별 점수. 정상 기획은 0점 → 가중치 산출 제외
    "normal": {"new": 20, "plan": 0},   # 합계 20점
    "outlet": {"new": 5,  "plan": 10},  # 합계 15점
}
# 시즌 구간별 점수 (정상/상설 공통)
# 당시즌 계절 10점, 동일 시즌 나머지 계절 5점, 반대 시즌 0점(제외)
SEASON_SCORE_CURRENT = 10
SEASON_SCORE_OTHER   = 5

# 목표 재고액 산출 상수
_UNIT_PRICE_LARGE = 70_000   # 50평 이상: 7만원/평/일
_UNIT_PRICE_SMALL = 100_000  # 50평 미만: 10만원/평/일
_STORE_DAYS       = 30       # 월 30일 기준
_STOCK_MULTI      = 3        # 재고배수


def calc_target_total(area: float, tM_won: float = 0.0) -> float:
    """목표 총 재고액 산출.

    50평 미만: 평수 × 10만원 × 30일 × 3배
    50평 이상: 평수 × 7만원 × 30일 × 3배
    평수 미입력(0): tM_won × 3배 fallback
    """
    if area >= 50:
        return area * _UNIT_PRICE_LARGE * _STORE_DAYS * _STOCK_MULTI
    if area > 0:
        return area * _UNIT_PRICE_SMALL * _STORE_DAYS * _STOCK_MULTI
    return max(tM_won * _STOCK_MULTI, 1.0)


def get_season_targets(month: int) -> tuple:
    """시스템 날짜의 월을 읽어 당시즌/나머지시즌 계절코드를 반환.

    계절: 1~3월=봄, 4~6월=여름, 7~9월=가을, 10~12월=겨울
    시즌: SS(봄·여름) / FW(가을·겨울)
    절대 하드코딩 금지 — 월을 직접 읽어 동적으로 판단.

    Returns:
        (당시즌_계절코드_리스트, 나머지시즌_계절코드_리스트)
    """
    CO_SPRING = ['봄', '1', 'SS']
    CO_SUMMER = ['여름', '2', 'SS']
    CO_AUTUMN = ['가을', '3', 'FW']
    CO_WINTER = ['겨울', '4', 'FW']
    if month in [1, 2, 3]:   return CO_SPRING, CO_SUMMER   # 봄이 당시즌
    if month in [4, 5, 6]:   return CO_SUMMER, CO_SPRING   # 여름이 당시즌
    if month in [7, 8, 9]:   return CO_AUTUMN, CO_WINTER   # 가을이 당시즌
    return CO_WINTER, CO_AUTUMN                             # 겨울이 당시즌


class AssortmentScorer:
    """상품구색 5개 지표 채점 엔진 — v11.0 평매출 반영 이중 채점 체계 도입"""

    ITEM_GROUPS = {
        'Outer':  ['JK', 'JA', 'JD', 'JE', 'JH', 'JJ', 'JL', 'JP', 'JT', 'JV', 'JW', 'SJ', 'VK', 'VW', 'CK', 'CM', 'VT', 'CT', 'BY', 'KC', 'PD', 'FU', 'U', 'E', 'J', 'C', 'D', 'Y', 'L',
                   'CO', 'OT', 'JU'],                                          # 코트·오버코트·점퍼
        'Top':    ['BL', 'BA', 'BB', 'BN', 'BW', 'GM', 'HA', 'HS', 'HW', 'KA', 'KN', 'KR', 'KV', 'KW', 'LA', 'LS', 'LW', 'MA', 'MB', 'MH', 'MW', 'MZ', 'RA', 'RB', 'RN', 'RP', 'RS', 'RW', 'SM', 'YA', 'YC', 'YH', 'YS', 'YW', 'XH', 'MN', 'MR', 'PP', 'GN', 'BR', 'FZ', 'FW', 'TS', 'ST', 'PO', 'SH', 'WS', 'KO', 'KP', 'B', 'K', 'T',
                   'MT', 'NT', 'CD', 'SW', 'HD', 'HN', 'GT', 'PW', 'LT', 'DS', 'SF'],  # 맨투맨·니트·가디건·스웨터·후드·셔츠
        'Bottom': ['SL', 'PT', 'TA', 'TC', 'TH', 'TJ', 'TM', 'TN', 'TR', 'IL', 'YI', 'YF', 'XF', 'XD', 'WP', 'WQ', 'XV', 'YV', 'SP', 'LE', 'DK', 'N', 'P',
                   'CH', 'DN', 'GP', 'PA', 'BD'],                             # 청바지·데님·반바지·팬츠
        'Skirt':  ['SK', 'WH', 'WJ', 'WK', 'WM', 'KS', 'S'],
        'Dress':  ['OP', 'OJ', 'OK', 'OM', 'ON', 'OW', 'YO', 'LO', 'YJ', 'DP', 'O',
                   'DR', 'JR', 'PL', 'ONE'],                                  # 드레스·주름원피스·플리츠
    }
    # 잡화·소품 등 계산 제외 코드
    ITEM_EXCLUDE = {'SO','SF','MF','HT','BT','BG','GL','CP','ET','WL','XP','ZY',
                    'AY','AS','AU','AW','AP','AG','AJ','AK','AM','ARJ'}

    # [v4.9c] DB item_code 직접 매핑 테이블 (카테고리별)
    ITEM_CODE_KIDS = {
        # 상하세트
        'ST':'Set',  'SET':'Set', 'SU':'Set',
        # 아우터
        'JK':'Outer','OT':'Outer','PD':'Outer','CO':'Outer',
        # 상의
        'TS':'Top',  'BD':'Top', 'MT':'Top', 'SH':'Top', 'NT':'Top', 'BL':'Top',
        # 하의
        'PT':'Bottom','SK':'Bottom','CH':'Bottom','SL':'Bottom',
        # 원피스
        'OP':'Dress','DR':'Dress','ONE':'Dress',
    }
    ITEM_CODE_MENS = {
        # 수트/셋업
        'ST':'Suits','SU':'Suits','SET':'Suits','JK':'Suits','SJ':'Suits',
        # 드레스셔츠
        'DS':'Shirts','SH':'Shirts',
        # 캐주얼/티셔츠
        'TS':'Casual','HN':'Casual','GT':'Casual','AC':'Casual',
        'JA':'Casual','JH':'Casual','OT':'Casual','PD':'Casual',
        # 니트/가디건
        'NT':'Knit','SW':'Knit','CD':'Knit','PW':'Knit','VT':'Knit',
        # 하의
        'SL':'Bottom','PT':'Bottom','DN':'Bottom','CH':'Bottom',
    }
    # 공통 직접 매핑 (여성·캐주얼·스포츠 등, 위 전용 맵 다음에 시도)
    ITEM_CODE_DIRECT = {
        # 아우터
        'CO':'Outer','OT':'Outer','JU':'Outer','TR':'Outer',
        'DXBK':'Outer','DWWJ':'Outer','DXBG':'Outer','DMTR':'Outer',
        'DXCP':'Outer','DXCR':'Outer','DXTG':'Outer',
        # 상의/블라우스/니트
        'BL':'Top','MT':'Top','DS':'Top','NT':'Top','CD':'Top',
        'PO':'Top','SW':'Top','HD':'Top','HN':'Top','GT':'Top',
        'PW':'Top','LT':'Top','TC':'Top','HT':'Top',
        'B':'Top','K':'Top','X':'Top',
        'DXSH':'Top','DKSH':'Top','DXHS':'Top','DXSO':'Top','DMMT':'Top','DMSP':'Top',
        # 하의
        'CH':'Bottom','DN':'Bottom','GP':'Bottom','PA':'Bottom',
        'DXLP':'Bottom','DXMR':'Bottom','DXTR':'Bottom',
        'DMRS':'Bottom','DXRS':'Bottom','DXBN':'Bottom',
        # 스커트
        'S':'Skirt',
        # 원피스
        'ONE':'Dress','JR':'Dress','PL':'Dress','O':'Dress',
        'DMPD':'Dress','DMSS':'Dress',
        # 상하세트
        'SET':'Set','SU':'Set',
        # 신발
        'MC':'CasualShoes','WC':'CasualShoes','MB':'CasualShoes',
        'MS':'RunningShoes','WS':'RunningShoes',
        'MW':'OtherShoes','WW':'OtherShoes','MO':'OtherShoes','WO':'OtherShoes','WD':'OtherShoes',
        'MD37':'OtherShoes','MD38':'OtherShoes',
        # 잡화
        'AC':'Others','GL':'Others','BP':'Others','BK':'Others',
        'HA':'Others','QV':'Others','QC':'Others',
    }

    # [v13.5] 카테고리별/조닝별 아이템 가중치 정의
    ZONING_ITEM_WEIGHTS = {
        '여성': {
            '커리어': {'Outer': 0.45, 'Top': 0.25, 'Bottom': 0.10, 'Skirt': 0.05, 'Dress': 0.15},
            '캐주얼': {'Outer': 0.35, 'Top': 0.25, 'Bottom': 0.10, 'Skirt': 0.15, 'Dress': 0.15},
            '캐릭터': {'Outer': 0.25, 'Top': 0.15, 'Bottom': 0.15, 'Skirt': 0.10, 'Dress': 0.35},
            '시니어': {'Outer': 0.30, 'Top': 0.15, 'Bottom': 0.15, 'Skirt': 0.05, 'Dress': 0.35},
        }
    }
    DEFAULT_ITEM_WEIGHTS = {'Outer': 0.30, 'Top': 0.30, 'Bottom': 0.20, 'Skirt': 0.10, 'Dress': 0.10}

    def __init__(self, config: dict = None):
        self.today = datetime.now()
        self.current_month = self.today.month  # 시스템 날짜 기준 (data_month 없을 때 fallback)
        self.config = config if config else {}
        self.best_cutoff = self.today - timedelta(days=14)

    @staticmethod
    def _safe_float(val) -> float:
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', '').strip())
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_discount_rate(val) -> float:
        try:
            s = str(val).replace('%', '').replace(' ', '').strip()
            if not s or s in ('nan', 'None', '', '#N/A', '#REF!', '#VALUE!'):
                return -1.0
            f = float(s)
            if 0.0 < f <= 1.0:
                f = f * 100.0
            return f
        except (TypeError, ValueError):
            return -1.0

    # 알려진 모든 아이템 코드 집합 (fast-lookup용 캐시)
    _ALL_ITEM_CODES: dict = {}  # {'코드': '그룹명'} — 첫 호출 시 빌드

    def _build_code_index(self):
        if not self._ALL_ITEM_CODES:
            for grp, codes in self.ITEM_GROUPS.items():
                for c in codes:
                    AssortmentScorer._ALL_ITEM_CODES[c] = grp

    def _lookup(self, candidate: str) -> str:
        """candidate(1-2자리 대문자) → 그룹명 or ''"""
        if not candidate or candidate in self.ITEM_EXCLUDE:
            return ''
        return self._ALL_ITEM_CODES.get(candidate, '')

    def _get_dynamic_item_weights(self, df: pd.DataFrame) -> dict:
        """[v13.5] 카테고리 및 조닝(zoning) 기반 동적 아이템 가중치 산출"""
        inv_weights = self.config.get('inv_weights', {})

        # 2. 데이터프레임에서 카테고리 추출 (신사 여부 판단에 필요하므로 먼저 실행)
        cat_group = str(df['category_group'].iloc[0]) if 'category_group' in df.columns and not df.empty else '일반'
        zoning = self.config.get('zoning', '')

        # 1. config에 직접 명시된 가중치가 있으면 최우선 (커스터마이징 대응)
        # 단, 신사 브랜드인데 남성 전용 키(Suits)가 없으면 → 여성 기본값 상속 오류이므로 무시하고 category 기반으로 낙하
        if 'item' in inv_weights:
            item_cfg = inv_weights['item']
            if cat_group != '신사' or 'Suits' in item_cfg:
                return item_cfg
        
        # 3. 여성 카테고리 특화 조닝 가중치 적용
        if cat_group == '여성' and zoning in self.ZONING_ITEM_WEIGHTS['여성']:
            return self.ZONING_ITEM_WEIGHTS['여성'][zoning]

        # 4. [v4.9] category_group 기반 폴백: 스포츠/아동/신사/캐주얼 전용 가중치
        _CAT_ITEM_WEIGHTS = {
            '스포츠':   {'Top': 0.40, 'Bottom': 0.30, 'RunningShoes': 0.20, 'OtherShoes': 0.10},
            '아동':     {'Outer': 0.30, 'Top': 0.30, 'Bottom': 0.25, 'Dress': 0.05, 'Set': 0.10},
            '신사':     {'Suits': 0.40, 'Shirts': 0.20, 'Casual': 0.20, 'Knit': 0.10, 'Bottom': 0.10},
            '캐주얼':   {'Outer': 0.35, 'Top': 0.25, 'Bottom': 0.10, 'Skirt': 0.15, 'Dress': 0.15},
        }
        if cat_group in _CAT_ITEM_WEIGHTS:
            return _CAT_ITEM_WEIGHTS[cat_group]

        # 5. Fallback: 기본 가중치 (여성 일반)
        return self.DEFAULT_ITEM_WEIGHTS

    def _get_item_group(self, raw_code: str) -> str:
        """
        item_code 또는 style_code → 아이템 그룹 매핑.
        - 남성: ITEM_CODE_MENS 전용 경로
        - 아동(Set 가중치 존재): ITEM_CODE_KIDS 우선 (ST→Set, SK→Bottom, BD→Top 보장)
        - 스포츠/여성/캐주얼: ITEM_CODE_DIRECT → ITEM_GROUPS 순
        """
        self._build_code_index()
        if not raw_code or (isinstance(raw_code, float) and pd.isna(raw_code)):
            return 'Others'

        raw = str(raw_code).strip().upper()
        item_cfg = self.config.get('inv_weights', {}).get('item', {})

        # 남성복 전용 — ITEM_CODE_MENS 슬라이딩 스캔
        if 'Suits' in item_cfg or self.config.get('_eff_cat', '') == '신사':
            hit = self.ITEM_CODE_MENS.get(raw) or (self.ITEM_CODE_MENS.get(raw[:2]) if len(raw) >= 2 else None)
            if hit: return hit
            for _s in range(2, min(len(raw) - 1, 10)):
                hit = self.ITEM_CODE_MENS.get(raw[_s:_s + 2])
                if hit: return hit
            return 'Casual'

        # 아동 여부: Set 가중치가 있으면 아동 모드 (ITEM_CODE_KIDS 우선)
        is_kids = 'Set' in item_cfg

        # 짧은 코드(≤4자) 직접 조회
        if len(raw) <= 4:
            # 1. 공통 직접 매핑 (신발 코드 포함)
            hit = self.ITEM_CODE_DIRECT.get(raw)
            if hit: return hit
            # 2. 아동: ITEM_CODE_KIDS 우선 (ST→Set, SK→Bottom, BD→Top)
            if is_kids:
                hit = self.ITEM_CODE_KIDS.get(raw)
                if hit: return hit
            # 3. ITEM_GROUPS (여성/캐주얼: SK→Skirt, BD→Bottom 등 정확 분류)
            hit = self._lookup(raw)
            if hit: return hit

        # 1-3자 복종코드: ITEM_GROUPS 기반 조회 (접두 fallback 포함)
        if len(raw) <= 3:
            hit = self._lookup(raw) or self._lookup(raw[:2]) or self._lookup(raw[:1])
            return hit if hit else 'Others'

        # 풀 스타일코드: 위치 2~8에서 2자리 슬라이딩 스캔
        for start in range(2, min(len(raw) - 1, 9)):
            sub = raw[start:start + 2]
            # 아동: ITEM_CODE_KIDS 우선 (ST→Set이 ITEM_GROUPS ST→Top보다 우선)
            if is_kids:
                hit = self.ITEM_CODE_KIDS.get(sub)
                if hit: return hit
            hit = self._lookup(sub)
            if hit: return hit
        return 'Others'

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        df = df.copy()
        
        # [v12.5] 아이템 그룹 매핑 (스포츠/아동 등 브랜드 특성 반영 고도화)
        df['_amt'] = df['stock_amt'].apply(lambda x: max(0.0, self._safe_float(x)))
        def _get_group_smart(row):
            # item_code 우선, 비어있으면 style_code fallback
            ic = str(row.get('item_code', '')).strip()
            # [v3.7] 네파 전용 아이템코드 매핑 (사용자 요청)
            b_name = str(row.get('brand_name', '')).strip()
            # 인코딩 문제 대응: '네파'라는 글자가 포함되거나 특정 깨진 패턴 대응 (v3.9)
            if "네파" in b_name or b_name.startswith("네") or b_name.startswith("네파"):
                nepa_map = {
                    '05': 'Outer', '06': 'Outer', '09': 'Outer', '10': 'Outer', '13': 'Outer', '14': 'Outer', '20': 'Outer',
                    '15': 'Top', '51': 'Top', '52': 'Top', '53': 'Top', '54': 'Top', '56': 'Top', '57': 'Top', '60': 'Top',
                    '16': 'Bottom', '17': 'Bottom', '18': 'Bottom'
                }
                ic_key = ic.zfill(2) if ic.isdigit() else ic
                if ic_key in nepa_map:
                    return nepa_map[ic_key]

            code = ic if ic and ic not in ('nan', '0') else str(row.get('style_code', '')).strip()
            cat_group = str(row.get('category_group', '')).strip()
            # [v4.9] category_group 기반 아동/남성 경로 강제 진입
            if cat_group == '아동':
                self.config['_eff_cat'] = '아동'
            elif cat_group == '신사' and 'Suits' not in self.config.get('inv_weights', {}).get('item', {}):
                self.config['_eff_cat'] = '신사'
            group = self._get_item_group(code)
            self.config.pop('_eff_cat', None)

            # 2. 스포츠/아웃도어 브랜드 특화: 품번 매핑 실패 시 상품명/카테고리 키워드 분석
            zoning = self.config.get('zoning', '')
            is_sports_logic = zoning in ["스포츠", "아웃도어", "애슬레저"] or cat_group in ["스포츠", "아웃도어"]
            if is_sports_logic and group in ['Top', 'Bottom', 'Others']:
                name = str(row.get('style_name', row.get('item_name', ''))).strip()
                cat = str(row.get('category_group', '')).strip()
                full_text = (name + cat).upper()
                
                # 러닝/기능성 슈즈 판별
                if any(k in full_text for k in ['러닝', 'RUNNING', '맥스', 'MAX', '쿠셔닝', '퍼포먼스', '신발', '슈즈', '운동화', 'SHOES']):
                    return 'RunningShoes'
                # 캐주얼/라이프스타일 슈즈 판별
                if any(k in full_text for k in ['워킹', 'WALKING', '고워크', 'GOWALK', '슬립온', '캐주얼', '라이프']):
                    return 'CasualShoes'
                # 기타 신발류
                if any(k in full_text for k in ['스니커즈', 'SNEAKERS', '샌들', 'SANDAL', '슬리퍼']):
                    return 'OtherShoes'
                
                # [v3.6] 의류 키워드 보강 (아웃도어/스포츠 의류 대응)
                if any(k in full_text for k in ['티셔츠', 'T-SHIRT', '상의', 'TOP', '폴로', 'POLO', '반팔', '긴팔']):
                    return 'Top'
                if any(k in full_text for k in ['팬츠', 'PANTS', '바지', '하의', 'BOTTOM', '레깅스', '트레이닝']):
                    return 'Bottom'
                if any(k in full_text for k in ['자켓', 'JACKET', '점퍼', 'JUMPER', '아우터', 'OUTER', '코트', '베스트', 'VEST', '고어텍스', 'GORE-TEX', '다운', 'DOWN', '파카']):
                    return 'Outer'
            
            return group

        df['item_group'] = df.apply(_get_group_smart, axis=1)

        # 목표 총 재고액 산출 — 평수 기반 (calc_target_total), 평수 미입력 시 tM × 3 fallback
        tM = float(df['tM'].iloc[0]) if ('tM' in df.columns and not pd.isna(df['tM'].iloc[0])) else 50_000_000.0
        if tM <= 0: tM = 1.0
        area = 0.0
        if 'area' in df.columns:
            _a = df['area'].iloc[0]
            if _a is not None and not (isinstance(_a, float) and pd.isna(_a)):
                area = max(0.0, float(_a))
        target_total = calc_target_total(area, tM)

        # 매장 유형 판단
        store_type_val = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
        is_outlet = _is_outlet(store_type_val)

        # 중복 제거 참조용 함수
        def _get_record_ref(mask):
            sub = df[mask]
            if sub.empty: return sub
            
            has_valid_uid = False
            if 'inv_uid' in sub.columns and sub['inv_uid'].notna().any():
                if not (sub['inv_uid'].astype(str).str.strip().eq('') | sub['inv_uid'].astype(str).str.strip().eq('nan')).all():
                    has_valid_uid = True
                    
            if has_valid_uid:
                return sub.drop_duplicates('inv_uid')
            else:
                d_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
                valid_cols = [c for c in d_cols if c in sub.columns]
                return sub.drop_duplicates(subset=valid_cols) if valid_cols else sub

        # [v107.8] 가중치 설정 (동적 적용)
        final_weights = {
            'dis':   self.config.get('weight_discount', 0.30),
            'fresh': self.config.get('weight_freshness', 0.20),
            'sea':   self.config.get('weight_season', 0.15),
            'best':  self.config.get('weight_best', 0.35),
            'item':  self.config.get('weight_item', 0.00)
        }
        # 잡화 카테고리: 할인율 60% + 베스트 40% (신선도/시즌/아이템 제외)
        _cat_grp_s = str(df['category_group'].iloc[0]).strip() if 'category_group' in df.columns and not df.empty else ''
        if _cat_grp_s == '잡화':
            final_weights = {'dis': 0.60, 'fresh': 0.00, 'sea': 0.00, 'best': 0.40, 'item': 0.00}

        inv_weights = self.config.get('inv_weights', {})

        # [v8.7] 연차(Age) 계산
        year_base = self.config.get('year_base', 2026)
        if year_base < 100: year_base += 2000
        ref_y = year_base

        def _get_age_sync(y):
            try:
                if not y or pd.isna(y) or str(y).strip() in ('#N/A', '#REF!', '#VALUE!'): return 0
                val = str(y).replace('년','').replace('20','', 1).strip() # '2024' -> '24' 대응
                y_num = int(val)
                if y_num < 100: y_num += 2000
                return max(0, ref_y - y_num)
            except: return 0

        df['_age'] = df['year'].apply(_get_age_sync) if 'year' in df.columns else 0

        # A. 할인율
        df['_dis_rate'] = df['discount_rate'].apply(self._parse_discount_rate) if 'discount_rate' in df.columns else 0.0
        dis_inv = inv_weights.get('dis', {})
        
        # [v11.1] 스포츠 카테고리 대응: 정상 매장이라도 실제 할인율 필드 사용 (아동은 정상매장 시 연차기반 허용)
        zoning = self.config.get('zoning', '')
        is_rate_based = zoning in ["스포츠", "아웃도어", "애슬레저"]
        if not is_rate_based and 'category_group' in df.columns and not df['category_group'].empty:
            cg = str(df['category_group'].iloc[0])
            if any(k in cg for k in ["스포츠", "아웃도어"]):
                is_rate_based = True

        # [v4.1→v17.31] 상설은 항상 실할인율 기준 채점 (연차 폴백 제거)
        # 구 로직: has_dis_data=(>=0) → 0%/미입력 구분 불가 → 연차 폴백 시 1년차 재고 10점 오산정
        has_dis_data = (df['_dis_rate'] > 0).any()
        use_age_for_dis = False  # 상설은 rate-based 고정; 정상 매장은 _use_rate_dis=False 분기에서 처리

        # [v4.5] 정상 매장도 할인율 데이터가 있으면 rate-based 사용 (로엠 계열 제외)
        _brand_nm_s = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns and not df.empty else ''
        _age_only_brands = {'로엠', '로엠(ROEM)'}

        _use_rate_dis = (is_outlet and not use_age_for_dis) or is_rate_based or (has_dis_data and _brand_nm_s not in _age_only_brands)
        # 점수 테이블 선택 (정상/상설 구분)
        _dis_score_tbl = DIS_SCORES["outlet"] if is_outlet else DIS_SCORES["normal"]
        if _use_rate_dis:
            # 정상/상설에 맞는 재고비중 기본값. s0는 연차기반 전용 키이므로 rate-based에서 제외.
            # 경계값 기준: ≥70%, ≥50%<70%, ≥30%<50%, ≥1%<30% (높은 구간부터 체크)
            _d_s70 = dis_inv.get('s70', 0.10 if is_outlet else 0.00)
            _d_s50 = dis_inv.get('s50', 0.20 if is_outlet else 0.05)
            _d_s30 = dis_inv.get('s30', 0.30 if is_outlet else 0.10)
            _d_s10 = dis_inv.get('s10', 0.10 if is_outlet else 0.15)
            dis_cfg = [
                {'m': (df['_dis_rate'] >= 70), 'r': _d_s70, 's': _dis_score_tbl['s70']},
                {'m': (df['_dis_rate'] >= 50) & (df['_dis_rate'] < 70), 'r': _d_s50, 's': _dis_score_tbl['s50']},
                {'m': (df['_dis_rate'] >= 30) & (df['_dis_rate'] < 50), 'r': _d_s30, 's': _dis_score_tbl['s30']},
                {'m': (df['_dis_rate'] > 0)   & (df['_dis_rate'] < 30), 'r': _d_s10, 's': _dis_score_tbl['s10']},
                # 0% 할인(신상)은 할인율 지표 배분 대상에서 제외
            ]
        else:
            # 연차(Age) 기반 — 로엠 계열 등 할인율 데이터 없는 브랜드 전용
            dis_cfg = [
                {'m': (df['_age'] == 0), 'r': 0.70, 's': 0},                       # 정상가: 0점
                {'m': (df['_age'] >= 4), 'r': 0.00, 's': 0},                       # 0점
                {'m': (df['_age'] == 3), 'r': 0.05, 's': _dis_score_tbl['s50']},
                {'m': (df['_age'] == 2), 'r': 0.10, 's': _dis_score_tbl['s30']},
                {'m': (df['_age'] == 1), 'r': 0.15, 's': _dis_score_tbl['s10']},
            ]
        _total_d_amt = _get_record_ref(pd.Series(True, index=df.index))['_amt'].sum()

        # 점수 가중치 = 구간 점수 / 지표 내 점수 합계 (점수 0인 구간 제외 후 정규화)
        sum_s = sum(item['s'] for item in dis_cfg if item.get('s', 0) > 0)
        discount_score = 0.0
        if sum_s > 0:
            for item in dis_cfg:
                seg_score = item.get('s', 0)
                if item['r'] > 0 and seg_score > 0:
                    act = _get_record_ref(item['m'])['_amt'].sum()
                    tgt = target_total * item['r']
                    segment_pct = (min(act, tgt) / tgt * 100.0) if tgt > 0 else 0.0
                    discount_score += segment_pct * (seg_score / sum_s)

        # B. 신선도 — freshness_type 또는 is_new 컬럼 기준
        ft = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series([''] * len(df), index=df.index)
        fresh_inv = inv_weights.get('fresh', {})

        _fresh_score_tbl = FRESH_SCORES["outlet"] if is_outlet else FRESH_SCORES["normal"]
        if is_outlet:
            # 상설: 명시적 0% 할인만 신상 (미입력 항목 포함 시 구형 재고 과다 계상 위험)
            _plan_mask = ft.str.contains('기획', na=False)
            _new_mask = ft.str.contains('신상', na=False) | (df['_dis_rate'] == 0)
            fresh_cfg = [
                {'m': _new_mask, 'r': fresh_inv.get('new', 0.10), 's': _fresh_score_tbl['new']},
                {'m': _plan_mask, 'r': fresh_inv.get('plan', 0.20), 's': _fresh_score_tbl['plan']},
            ]
        else:
            # [정상매장] 신선도 = 신상품 비중만 측정 (목표비중 70%)
            # is_new==1 또는 freshness_type에 '신상' 포함된 상품만 신상으로 판별
            # 이월/기타 상품은 신선도 점수 계산에서 완전 제외 (기여도 0)
            if 'is_new' in df.columns:
                _is_new_col = pd.to_numeric(df['is_new'], errors='coerce').fillna(0).astype(int)
                _new_mask = (_is_new_col == 1) | ft.str.contains('신상', na=False)
            else:
                # is_new 컬럼 없을 경우: freshness_type='신상' 만으로 판별
                _new_mask = ft.str.contains('신상', na=False)
            fresh_cfg = [
                {'m': _new_mask, 'r': 0.70, 's': _fresh_score_tbl['new']},
                # 이월/기타는 아예 r=0 → tgt=0 → 점수 기여 없음
            ]

        # 점수 가중치 = 구간 점수 / 지표 내 점수 합계 (점수 0인 구간 제외)
        sum_s = sum(item['s'] for item in fresh_cfg if item.get('s', 0) > 0)
        freshness_score = 0.0
        if sum_s > 0:
            for item in fresh_cfg:
                seg_score = item.get('s', 0)
                if item['r'] > 0 and seg_score > 0:
                    act = _get_record_ref(item['m'])['_amt'].sum()
                    # 신선도 목표비중(70%)으로 목표재고액을 산출함
                    tgt = target_total * item['r']
                    segment_pct = (min(act, tgt) / tgt * 100.0) if tgt > 0 else 0.0
                    freshness_score += segment_pct * (seg_score / sum_s)

        # C. 시즌 — data_month 기준 동적 판단 (get_season_targets 사용, 하드코딩 금지)
        _raw_m = df['data_month'].iloc[0] if 'data_month' in df.columns and not df.empty else ''
        _m_str = str(_raw_m).replace('월', '').strip()
        month = int(_m_str) if _m_str.isdigit() else self.current_month  # fallback = 시스템 날짜
        sc = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series([''] * len(df))

        sea_inv = inv_weights.get('season', {})
        non_zero_seasons = sum(1 for v in sea_inv.values() if v > 0)

        if non_zero_seasons <= 2:
            # SS/FW 2시즌 브랜드: get_season_targets()로 당시즌/나머지시즌 동적 결정
            primary_r   = sea_inv.get('spring', sea_inv.get('current', 0.50))
            secondary_r = sea_inv.get('summer', sea_inv.get('other',   0.30))
            curr_codes, sub_codes = get_season_targets(month)
            season_cfg = [
                {'m': sc.isin(curr_codes), 'r': primary_r,   's': SEASON_SCORE_CURRENT},
                {'m': sc.isin(sub_codes),  'r': secondary_r, 's': SEASON_SCORE_OTHER},
            ]
        else:
            # 스포츠 등 계절별 고정 비중 (3개 이상 non-zero)
            CO_SPRING = ['봄', '1', 'SS']; CO_SUMMER = ['여름', '2', 'SS']
            CO_AUTUMN = ['가을', '3', 'FW']; CO_WINTER = ['겨울', '4', 'FW']
            curr_codes, sub_codes = get_season_targets(month)
            season_cfg = [
                {'m': sc.isin(CO_SPRING), 'r': sea_inv.get('spring', 0.0),
                 's': SEASON_SCORE_CURRENT if CO_SPRING == curr_codes else (SEASON_SCORE_OTHER if CO_SPRING == sub_codes else 0)},
                {'m': sc.isin(CO_SUMMER), 'r': sea_inv.get('summer', 0.0),
                 's': SEASON_SCORE_CURRENT if CO_SUMMER == curr_codes else (SEASON_SCORE_OTHER if CO_SUMMER == sub_codes else 0)},
                {'m': sc.isin(CO_AUTUMN), 'r': sea_inv.get('autumn', 0.0),
                 's': SEASON_SCORE_CURRENT if CO_AUTUMN == curr_codes else (SEASON_SCORE_OTHER if CO_AUTUMN == sub_codes else 0)},
                {'m': sc.isin(CO_WINTER), 'r': sea_inv.get('winter', 0.0),
                 's': SEASON_SCORE_CURRENT if CO_WINTER == curr_codes else (SEASON_SCORE_OTHER if CO_WINTER == sub_codes else 0)},
            ]

        # 점수 가중치 = 구간 점수 / 지표 내 점수 합계 (반대 시즌 0점 → 제외)
        # 당시즌 계절 66.7% / 나머지 계절 33.3% (10점/15점, 5점/15점)
        sum_s = sum(item['s'] for item in season_cfg if item.get('s', 0) > 0)
        season_score = 0.0
        if sum_s > 0:
            for item in season_cfg:
                seg_score = item.get('s', 0)
                if item['r'] > 0 and seg_score > 0:
                    act = _get_record_ref(item['m'])['_amt'].sum()
                    tgt = target_total * item['r']
                    segment_pct = (min(act, tgt) / tgt * 100.0) if tgt > 0 else 0.0
                    season_score += segment_pct * (seg_score / sum_s)

        # D. 베스트10
        best_styles = []
        if 'sales_qty' in df.columns:
            sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
            # [v3.8] 판매량이 0보다 큰 상품들만 베스트 후보군으로 선정
            sq_df = df.assign(_sq=sq)
            best_candidates = sq_df[sq_df['_sq'] > 0]
            if not best_candidates.empty and 'style_code' in best_candidates.columns:
                best_styles = best_candidates.groupby('style_code')['_sq'].sum().sort_values(ascending=False).head(10).index.tolist()
        
        act_best = 0.0
        if best_styles and 'style_code' in df.columns:
            act_best = _get_record_ref(df['style_code'].isin(best_styles))['_amt'].sum()
            
        tgt_best = target_total * inv_weights.get('best', {}).get('store10', 0.20)
        best_score = (min(act_best, tgt_best) / tgt_best * 100.0) if tgt_best > 0 else 0.0

        # 아이템 지표 내 명시적 구간별 가중 평균
        item_w = self._get_dynamic_item_weights(df)
        sum_r = sum(item_w.values())
        item_score = 0.0
        if sum_r > 0:
            for g_name, r_val in item_w.items():
                if r_val > 0:
                    act = _get_record_ref(df['item_group'] == g_name)['_amt'].sum()
                    tgt = target_total * r_val
                    segment_pct = (min(act, tgt) / tgt * 100.0) if tgt > 0 else 0.0
                    item_score += segment_pct * (r_val / sum_r)

        # ──────────────────────────────────────────
        # 최종 총점 산출 (v11.0 이중 채점 체계)
        # ──────────────────────────────────────────
        product_score = (
            discount_score  * final_weights['dis']   +
            freshness_score * final_weights['fresh'] +
            season_score    * final_weights['sea']   +
            best_score      * final_weights['best']  +
            item_score      * final_weights['item']
        )
        
        # [v12.0] 평매출(eff_score) 및 종합점수(total_score) 로직 사용자 요청으로 완전 삭제
        df['product_score'] = int(round(product_score))
        df['total_score'] = df['product_score']

        # 지표별 개별 점수 보존
        df['discount_score'] = int(round(discount_score))
        df['freshness_score'] = int(round(freshness_score))
        df['season_score'] = int(round(season_score))
        df['best_score'] = int(round(best_score))
        df['item_score'] = int(round(item_score))
        df['dis_estimated'] = False  # [v17.12]

        drop_cols = ['_amt', '_dis_rate', '_sale_dt', 'item_group']
        return df.drop(drop_cols, axis=1, errors='ignore')

    def get_shortage_segments(self, df: pd.DataFrame) -> dict:
        """현재 브랜드의 구색 부족 세그먼트(Shortage) 분석"""
        if df is None or df.empty: return {}
        df = df.copy()
        df['_amt'] = df['stock_amt'].apply(lambda x: max(0.0, self._safe_float(x)))
        df['item_group'] = df['item_code'].apply(self._get_item_group) if 'item_code' in df.columns else 'Others'
        
        tM = float(df['tM'].iloc[0]) if ('tM' in df.columns and not pd.isna(df['tM'].iloc[0])) else 50_000_000.0
        _area = 0.0
        if 'area' in df.columns:
            _a2 = df['area'].iloc[0]
            if _a2 is not None and not (isinstance(_a2, float) and pd.isna(_a2)):
                _area = max(0.0, float(_a2))
        target_total = calc_target_total(_area, tM)
        is_outlet = _is_outlet(str(df['store_type'].iloc[0])) if 'store_type' in df.columns else False
        inv_weights = self.config.get('inv_weights', {})

        def _get_ref_count(mask):
            sub = df[mask]
            if sub.empty: return 0.0
            if 'inv_uid' in sub.columns: return sub.drop_duplicates('inv_uid')['_amt'].sum()
            d_cols = [c for c in ['style_code','year','season_code'] if c in sub.columns]
            return sub.drop_duplicates(subset=d_cols)['_amt'].sum() if d_cols else sub['_amt'].sum()

        res = {"dis": [], "fresh": [], "season": [], "item": [], "best": []}

        # 잡화 카테고리: 신선도/시즌 부족 분석 생략 (할인율 + 베스트만 채점)
        _cat_grp_sh = str(df['category_group'].iloc[0]).strip() if 'category_group' in df.columns and not df.empty else ''
        _is_jabh_sh = (_cat_grp_sh == '잡화')

        # 할인율 부족
        df['_dis_rate'] = df['discount_rate'].apply(self._parse_discount_rate) if 'discount_rate' in df.columns else 0.0
        dis_inv = inv_weights.get('dis', {})
        
        is_sports = "스포츠" in str(df['category_group'].iloc[0]) if 'category_group' in df.columns else False

        _dis_hint_scale = 1.0
        if is_outlet or is_sports:
            dis_cfg = [('70%이상', (df['_dis_rate'] >= 70), dis_inv.get('s70', 0.1)), ('50~70%', (df['_dis_rate']>=50)&(df['_dis_rate']<70), dis_inv.get('s50', 0.2)), ('30~50%', (df['_dis_rate']>=30)&(df['_dis_rate']<50), dis_inv.get('s30', 0.3)), ('30%미만', (df['_dis_rate']>0)&(df['_dis_rate']<30), dis_inv.get('s10', 0.1))]
            # [v17.11] 할인율 미변환 품번 보정
            _sh_total = _get_ref_count(pd.Series(True, index=df.index))
            _sh_known = _get_ref_count(df['_dis_rate'] >= 0)
            if 0 < _sh_known < _sh_total:
                _dis_hint_scale = _sh_total / _sh_known
        else:
            year_base = self.config.get('year_base', 2026)
            df['_age'] = df['year'].apply(lambda y: max(0, year_base-int(str(y).replace('년','')))) if 'year' in df.columns else 10
            dis_cfg = [('4년+(70%)', (df['_age']>=4), 0.0), ('3년(50%)', (df['_age']==3), 0.05), ('2년(30%)', (df['_age']==2), 0.1), ('1년(10%)', (df['_age']==1), 0.15)]

        for label, mask, r_val in dis_cfg:
            if r_val > 0 and _get_ref_count(mask) * _dis_hint_scale < (target_total * r_val): res["dis"].append(label)

        if not _is_jabh_sh:
            # 신선도 부족
            ft_s = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series([''] * len(df))
            _fresh_w = inv_weights.get('fresh', {})
            _has_dis_f = (df['_dis_rate'] > 0).any()
            _brand_nm_f = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns else ''
            if _brand_nm_f in {'스파오키즈', '뉴발란스키즈'}:
                if is_outlet:
                    fresh_cfg = [('신상', ft_s.str.contains('신상', na=False), _fresh_w.get('new', 0.1)), ('기획', ft_s.str.contains('기획', na=False), _fresh_w.get('plan', 0.2))]
                else:
                    # 정상매장: is_new 또는 freshness_type='신상' 기준
                    if 'is_new' in df.columns:
                        _is_new_c = pd.to_numeric(df['is_new'], errors='coerce').fillna(0).astype(int)
                        _new_m2 = (_is_new_c == 1) | ft_s.str.contains('신상', na=False)
                    else:
                        _new_m2 = ft_s.str.contains('신상', na=False)
                    fresh_cfg = [('신상', _new_m2, _fresh_w.get('new', 0.70))]
            else:
                if is_outlet:
                    _new_m = ft_s.str.contains('신상', na=False) | (df['_dis_rate'] == 0)
                    r_n = _fresh_w.get('new', 0.10)
                    r_p = _fresh_w.get('plan', 0.20)
                    fresh_cfg = [('신상', _new_m, r_n), ('기획', ft_s.str.contains('기획', na=False), r_p)]
                else:
                    # [정상매장] is_new==1 또는 freshness_type='신상' 만으로 신상 판별
                    # 이월/기타는 신선도 부족 판단에서 완전 제외
                    if 'is_new' in df.columns:
                        _is_new_c = pd.to_numeric(df['is_new'], errors='coerce').fillna(0).astype(int)
                        _new_m = (_is_new_c == 1) | ft_s.str.contains('신상', na=False)
                    else:
                        _new_m = ft_s.str.contains('신상', na=False)
                    r_n = 0.70
                    fresh_cfg = [('신상', _new_m, r_n)]
            for label, mask, r_val in fresh_cfg:
                if r_val > 0 and _get_ref_count(mask) < (target_total * r_val): res["fresh"].append(label)

            # 시즌 부족 — score()와 동일한 data_month 기준 매핑
            sc = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series([''] * len(df))
            CO_SPRING = ['봄', '1', '9', 'SS']; CO_SUMMER = ['여름', '2', '9', 'SS']
            CO_AUTUMN = ['가을', '3', '8', '9', 'FW']; CO_WINTER = ['겨울', '4', '9', 'FW']
            _raw_m2 = df['data_month'].iloc[0] if 'data_month' in df.columns and not df.empty else ''
            _m_str2 = str(_raw_m2).replace('월', '').strip()
            month = int(_m_str2) if _m_str2.isdigit() else self.current_month
            sea_inv = inv_weights.get('season', {})
            non_zero_seasons = sum(1 for v in sea_inv.values() if v > 0)

            if non_zero_seasons <= 2:
                primary_r   = sea_inv.get('spring', sea_inv.get('current', 0.50))
                secondary_r = sea_inv.get('summer', sea_inv.get('other',   0.30))
                if month in [1, 2, 3]:      curr_codes, sub_codes = CO_SPRING, CO_SUMMER
                elif month in [4, 5, 6]:    curr_codes, sub_codes = CO_SUMMER, CO_SPRING
                elif month in [7, 8, 9]:    curr_codes, sub_codes = CO_AUTUMN, CO_WINTER
                else:                        curr_codes, sub_codes = CO_WINTER, CO_AUTUMN
                season_checks = [('봄(현시즌)', curr_codes, primary_r), ('여름(보조)', sub_codes, secondary_r)]
            else:
                season_checks = [
                    ('봄', CO_SPRING, sea_inv.get('spring', 0.0)),
                    ('여름', CO_SUMMER, sea_inv.get('summer', 0.0)),
                    ('가을', CO_AUTUMN, sea_inv.get('autumn', 0.0)),
                    ('겨울', CO_WINTER, sea_inv.get('winter', 0.0)),
                ]

            for label, codes, r_val in season_checks:
                if r_val > 0 and _get_ref_count(sc.isin(codes)) < (target_total * r_val): res["season"].append(label)

        # BEST 부족
        if 'sales_qty' in df.columns:
            sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
            b_list = df.assign(_sq=sq).groupby('style_code')['_sq'].sum().sort_values(ascending=False).head(10).index.tolist()
            best_r = inv_weights.get('best', {}).get('store10', 0.20)
            if best_r > 0 and _get_ref_count(df['style_code'].isin(b_list)) < (target_total * best_r): res["best"] = ["TOP 10"]

        # 아이템 부족
        item_w = self._get_dynamic_item_weights(df)
        for g_name, r_val in item_w.items():
            if r_val > 0 and _get_ref_count(df['item_group'] == g_name) < (target_total * r_val): res["item"].append(g_name)

        return res
