import pandas as pd
from datetime import datetime, timedelta


def _is_outlet(store_type_val: str) -> bool:
    """상설 매장 여부 판단. '복합'은 상설 로직 동일 적용"""
    v = str(store_type_val).strip().lower()
    return any(k in v for k in ["상설", "outlet", "아울렛", "팩토리", "factory", "복합"]) or v.startswith("상")


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

    DIAG_MONTH = 4  # 진단 기준월 고정 (4월 = SS봄 현시즌)

    def __init__(self, config: dict = None):
        self.today = datetime.now()
        self.current_month = self.DIAG_MONTH
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
        
        # 1. config에 직접 명시된 가중치가 있으면 최우선 (커스터마이징 대응)
        if 'item' in inv_weights:
            return inv_weights['item']
            
        # 2. 데이터프레임에서 카테고리 추출
        cat_group = str(df['category_group'].iloc[0]) if 'category_group' in df.columns and not df.empty else '일반'
        zoning = self.config.get('zoning', '')
        
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
        단순 복종코드("JK") 뿐 아니라 풀 스타일코드("GR3M0JK921")도 처리:
        - 1-3자 → 직접 매핑
        - 4자 이상 → 위치 2-8에서 2자리 슬라이딩 윈도우로 스캔
        """
        self._build_code_index()
        if not raw_code or (isinstance(raw_code, float) and pd.isna(raw_code)):
            return 'Others'

        raw = str(raw_code).strip().upper()

        # 스포츠 전용
        if "RunningShoes" in self.config.get("inv_weights", {}).get("item", {}):
            return 'Top'

        # 남성복 전용 — ITEM_CODE_MENS 사용 (Suits/Shirts/Casual/Knit는 남성 전용 그룹)
        if "Suits" in self.config.get("inv_weights", {}).get("item", {}) or self.config.get('_eff_cat', '') == '신사':
            hit = self.ITEM_CODE_MENS.get(raw)
            if hit: return hit
            hit = self.ITEM_CODE_MENS.get(raw[:2])
            if hit: return hit
            return 'Casual'

        # 공통: 짧은 코드(≤4자) 직접 조회 — ITEM_CODE_DIRECT → ITEM_CODE_KIDS 순
        if len(raw) <= 4:
            hit = self.ITEM_CODE_DIRECT.get(raw)
            if hit: return hit
            hit = self.ITEM_CODE_KIDS.get(raw)
            if hit: return hit

        # 1-3자 복종코드: ITEM_GROUPS 기반 조회
        if len(raw) <= 3:
            hit = self._lookup(raw) or self._lookup(raw[:2]) or self._lookup(raw[:1])
            return hit if hit else 'Others'

        # 풀 스타일코드: 위치 2~8에서 2자리 슬라이딩 스캔 (ITEM_GROUPS → ITEM_CODE_KIDS 순)
        for start in range(2, min(len(raw) - 1, 9)):
            sub = raw[start:start + 2]
            hit = self._lookup(sub)
            if hit: return hit
            hit = self.ITEM_CODE_KIDS.get(sub)  # 슬라이딩에서 못 찾은 코드 보완
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

        # 목표 매출액(tM) 추출 및 목표 총액 설정
        tM = float(df['tM'].iloc[0]) if ('tM' in df.columns and not pd.isna(df['tM'].iloc[0])) else 50_000_000.0
        if tM <= 0: tM = 1.0
        target_total = tM * 2.0  # 목표 재고액 (200%)

        # 매장 유형 판단
        store_type_val = str(df['store_type'].iloc[0]).strip() if 'store_type' in df.columns else "정상"
        is_outlet = _is_outlet(store_type_val)

        # 중복 제거 참조용 함수 (v7 기준 유지)
        def _get_record_ref(mask):
            sub = df[mask]
            if sub.empty: return sub
            if 'inv_uid' in sub.columns and sub['inv_uid'].notna().any():
                return sub.drop_duplicates('inv_uid')
            if is_outlet:
                return sub
            else:
                d_cols = ['style_code', 'year', 'season_code', 'price_type', 'stock_qty', 'stock_amt']
                valid_cols = [c for c in d_cols if c in sub.columns]
                return sub.drop_duplicates(subset=valid_cols) if valid_cols else sub

        # [v107.8] 가중치 설정 (동적 적용)
        final_weights = {
            'dis':   self.config.get('weight_discount', 0.30),
            'fresh': self.config.get('weight_freshness', 0.20),
            'sea':   self.config.get('weight_season', 0.15),
            'best':  self.config.get('weight_best', 0.25),
            'item':  self.config.get('weight_item', 0.10)
        }

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

        # [v4.1] 할인율 데이터가 모두 0인 상설 매장의 경우 연차(Age) 기준으로 자동 Fallback 처리
        has_dis_data = (df['_dis_rate'] > 0).any()
        use_age_for_dis = is_outlet and not has_dis_data

        # [v4.5] 정상 매장도 할인율 데이터가 있으면 rate-based 사용 (로엠 계열 제외)
        _brand_nm_s = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns and not df.empty else ''
        _age_only_brands = {'로엠', '로엠(ROEM)'}

        if (is_outlet and not use_age_for_dis) or is_rate_based or (has_dis_data and _brand_nm_s not in _age_only_brands):
            dis_cfg = [
                {'m': (df['_dis_rate'] >= 70), 'r': dis_inv.get('s70', 0.10)},
                {'m': (df['_dis_rate'] >= 50) & (df['_dis_rate'] < 70), 'r': dis_inv.get('s50', 0.20)},
                {'m': (df['_dis_rate'] >= 30) & (df['_dis_rate'] < 50), 'r': dis_inv.get('s30', 0.30)},
                {'m': (df['_dis_rate'] > 0)   & (df['_dis_rate'] < 30), 'r': dis_inv.get('s10', 0.10)},
                {'m': (df['_dis_rate'] == 0), 'r': dis_inv.get('s0', 0.00)},
            ]
        else:
            dis_cfg = [
                {'m': (df['_age'] == 0), 'r': dis_inv.get('s0', 0.70)},
                {'m': (df['_age'] >= 4), 'r': dis_inv.get('s70', 0.10 if use_age_for_dis else 0.00)},
                {'m': (df['_age'] == 3), 'r': dis_inv.get('s50', 0.20 if use_age_for_dis else 0.05)},
                {'m': (df['_age'] == 2), 'r': dis_inv.get('s30', 0.30 if use_age_for_dis else 0.10)},
                {'m': (df['_age'] == 1), 'r': dis_inv.get('s10', 0.10 if use_age_for_dis else 0.15)},
            ]
        dis_atts = []
        for item in dis_cfg:
            act = _get_record_ref(item['m'])['_amt'].sum()
            tgt = target_total * item['r']
            # [v12.5] tgt가 0인 경우(가중치가 0인 구간): 실제 재고가 있다면 0점, 없다면 100점 처리 (방어적 채점)
            dis_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else (100.0 if act <= 0 else 0.0))
        discount_score = (sum(dis_atts) / len(dis_atts)) if dis_atts else 0.0

        # B. 신선도
        # [v4.4.6] 사용자 요청: year=2026이면 최우선 신상(New), year가 없으면 freshness_type에서 '신상' 확인
        if 'year' in df.columns:
            def _parse_y(val):
                try:
                    if pd.isna(val): return None
                    s = str(val).replace('년', '').strip()
                    if s in ('', 'nan', 'None', '#N/A', '#REF!', '#VALUE!'): return None
                    y_num = int(float(s))
                    if y_num < 100: y_num += 2000
                    return y_num
                except:
                    return None
            parsed_year = df['year'].apply(_parse_y)
        else:
            parsed_year = pd.Series([None] * len(df), index=df.index)

        ft = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series([''] * len(df), index=df.index)
        fresh_inv = inv_weights.get('fresh', {})

        is_year_2026 = (parsed_year == 2026)
        is_year_missing = parsed_year.isna()
        has_fresh_text = ft.str.contains('신상', na=False)

        _new_mask = is_year_2026 | (is_year_missing & has_fresh_text)
        _plan_mask = ft.str.contains('기획', na=False)
        
        if is_outlet:
            fresh_cfg = [
                {'m': _new_mask, 'r': fresh_inv.get('new', 0.10)},
                {'m': _plan_mask, 'r': fresh_inv.get('plan', 0.20)}
            ]
        else:
            fresh_cfg = [
                {'m': _new_mask, 'r': fresh_inv.get('new', 0.70)},
                {'m': _plan_mask, 'r': fresh_inv.get('plan', 0.00)} # 정상 매장의 기획 목표가 0이더라도 재고가 있으면 방어적 채점을 위해 추가
            ]
        
        fresh_atts = []
        for item in fresh_cfg:
            act = _get_record_ref(item['m'])['_amt'].sum()
            tgt = target_total * item['r']
            fresh_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else 0.0)
        freshness_score = (sum(fresh_atts) / len(fresh_atts)) if fresh_atts else 0.0

        # C. 시즌 — DIAG_MONTH(4월) 고정 기준, SS/FW 2시즌 동적 매핑
        month = self.current_month  # 항상 DIAG_MONTH(4)
        sc = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series([''] * len(df))
        CO_SPRING = ['봄', '1', '9', 'SS']; CO_SUMMER = ['여름', '2', '9', 'SS']
        CO_AUTUMN = ['가을', '3', '8', '9', 'FW']; CO_WINTER = ['겨울', '4', '9', 'FW']

        sea_inv = inv_weights.get('season', {})
        non_zero_seasons = sum(1 for v in sea_inv.values() if v > 0)

        if non_zero_seasons <= 2:
            # SS/FW 2시즌 브랜드: 현시즌=primary(0.50), 보조시즌=secondary(0.30) 동적 매핑
            primary_r   = sea_inv.get('spring', sea_inv.get('current', 0.50))
            secondary_r = sea_inv.get('summer', sea_inv.get('other',   0.30))
            if month in [1, 2, 3, 4]:   curr_codes, sub_codes = CO_SPRING, CO_SUMMER
            elif month in [5, 6]:        curr_codes, sub_codes = CO_SUMMER, CO_SPRING
            elif month in [7, 8, 9]:     curr_codes, sub_codes = CO_AUTUMN, CO_WINTER
            else:                         curr_codes, sub_codes = CO_WINTER, CO_AUTUMN
            season_cfg = [
                {'m': sc.isin(curr_codes), 'r': primary_r},
                {'m': sc.isin(sub_codes),  'r': secondary_r},
            ]
        else:
            # 스포츠 등 계절별 고정 비중 (3개 이상 non-zero)
            season_cfg = [
                {'m': sc.isin(CO_SPRING), 'r': sea_inv.get('spring', 0.0)},
                {'m': sc.isin(CO_SUMMER), 'r': sea_inv.get('summer', 0.0)},
                {'m': sc.isin(CO_AUTUMN), 'r': sea_inv.get('autumn', 0.0)},
                {'m': sc.isin(CO_WINTER), 'r': sea_inv.get('winter', 0.0)},
            ]

        season_atts = []
        for item in season_cfg:
            if item['r'] <= 0:
                continue
            act = _get_record_ref(item['m'])['_amt'].sum()
            tgt = target_total * item['r']
            season_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else 0.0)
        season_score = (sum(season_atts) / len(season_atts)) if season_atts else 0.0

        # D. 베스트10
        best_styles = []
        if 'sales_qty' in df.columns:
            sq = pd.to_numeric(df['sales_qty'], errors='coerce').fillna(0)
            # [v3.8] 판매량이 0보다 큰 상품들만 베스트 후보군으로 선정
            sq_df = df.assign(_sq=sq)
            best_candidates = sq_df[sq_df['_sq'] > 0]
            if not best_candidates.empty:
                best_styles = best_candidates.groupby('style_code')['_sq'].sum().sort_values(ascending=False).head(10).index.tolist()
        
        if not best_styles:
            # [v4.2] 스타일별 판매 데이터 부재 시 전체 매출 실적을 기반으로 보정 점수 부여 (0점 방지)
            brand_sales = df['brand_month_sales'].iloc[0] if 'brand_month_sales' in df.columns else 0.0
            if brand_sales > 0:
                overall_perf = (brand_sales / target_total) if target_total > 0 else 0
                best_score = min(40.0, overall_perf * 100)  # [v4.3] 데이터 부족 시 보정 점수 대폭 축소 (0점 방지용 최소치)
            else:
                best_score = 0.0
        else:
            act_best = _get_record_ref(df['style_code'].isin(best_styles))['_amt'].sum()
            tgt_best = target_total * inv_weights.get('best', {}).get('store10', 0.20)
            best_score = min(100.0, (act_best / tgt_best * 100)) if tgt_best > 0 else 0.0

        # E. 아이템
        item_w = self._get_dynamic_item_weights(df)
        item_atts = []
        for g_name, r_val in item_w.items():
            act = _get_record_ref(df['item_group'] == g_name)['_amt'].sum()
            tgt = target_total * r_val
            item_atts.append(min(100.0, (act / tgt * 100)) if tgt > 0 else 0.0)
        item_score = (sum(item_atts) / len(item_atts)) if item_atts else 0.0

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

        drop_cols = ['_amt', '_dis_rate', '_sale_dt', 'item_group']
        return df.drop(drop_cols, axis=1, errors='ignore')

    def get_shortage_segments(self, df: pd.DataFrame) -> dict:
        """현재 브랜드의 구색 부족 세그먼트(Shortage) 분석"""
        if df is None or df.empty: return {}
        df = df.copy()
        df['_amt'] = df['stock_amt'].apply(lambda x: max(0.0, self._safe_float(x)))
        df['item_group'] = df['item_code'].apply(self._get_item_group) if 'item_code' in df.columns else 'Others'
        
        tM = float(df['tM'].iloc[0]) if ('tM' in df.columns and not pd.isna(df['tM'].iloc[0])) else 50_000_000.0
        target_total = tM * 2.0
        is_outlet = _is_outlet(str(df['store_type'].iloc[0])) if 'store_type' in df.columns else False
        inv_weights = self.config.get('inv_weights', {})

        def _get_ref_count(mask):
            sub = df[mask]
            if sub.empty: return 0.0
            if 'inv_uid' in sub.columns: return sub.drop_duplicates('inv_uid')['_amt'].sum()
            d_cols = [c for c in ['style_code','year','season_code'] if c in sub.columns]
            return sub.drop_duplicates(subset=d_cols)['_amt'].sum() if d_cols else sub['_amt'].sum()

        res = {"dis": [], "fresh": [], "season": [], "item": [], "best": []}

        # 할인율 부족
        df['_dis_rate'] = df['discount_rate'].apply(self._parse_discount_rate) if 'discount_rate' in df.columns else 0.0
        dis_inv = inv_weights.get('dis', {})
        
        is_sports = "스포츠" in str(df['category_group'].iloc[0]) if 'category_group' in df.columns else False

        if is_outlet or is_sports:
            dis_cfg = [('70%이상', (df['_dis_rate'] >= 70), dis_inv.get('s70', 0.1)), ('50~70%', (df['_dis_rate']>=50)&(df['_dis_rate']<70), dis_inv.get('s50', 0.2)), ('30~50%', (df['_dis_rate']>=30)&(df['_dis_rate']<50), dis_inv.get('s30', 0.3)), ('30%미만', (df['_dis_rate']>0)&(df['_dis_rate']<30), dis_inv.get('s10', 0.1))]
        else:
            year_base = self.config.get('year_base', 2026)
            df['_age'] = df['year'].apply(lambda y: max(0, year_base-int(str(y).replace('년','')))) if 'year' in df.columns else 10
            dis_cfg = [('4년차+(70%)', (df['_age']>=4), dis_inv.get('s70', 0.0)), ('3년차(50%)', (df['_age']==3), dis_inv.get('s50', 0.05)), ('2년차(30%)', (df['_age']==2), dis_inv.get('s30', 0.1)), ('1년차(10%)', (df['_age']==1), dis_inv.get('s10', 0.15))]
            
        for label, mask, r_val in dis_cfg:
            if r_val > 0 and _get_ref_count(mask) < (target_total * r_val): res["dis"].append(label)

        # 신선도 부족
        ft_s = df['freshness_type'].astype(str).str.strip() if 'freshness_type' in df.columns else pd.Series([''] * len(df))
        _fresh_w = inv_weights.get('fresh', {})
        _has_dis_f = (df['_dis_rate'] > 0).any()
        _brand_nm_f = str(df['brand_name'].iloc[0]).strip() if 'brand_name' in df.columns else ''
        if _brand_nm_f in {'스파오키즈', '뉴발란스키즈'}:
            if is_outlet:
                fresh_cfg = [('신상', ft_s.str.contains('신상', na=False), _fresh_w.get('new', 0.1)), ('기획', ft_s.str.contains('기획', na=False), _fresh_w.get('plan', 0.2))]
            else:
                fresh_cfg = [('신상', (df['_age']==0) | ft_s.str.contains('신상', na=False), _fresh_w.get('new', 0.70)), ('기획', ft_s.str.contains('기획', na=False), _fresh_w.get('plan', 0.10))]
        else:
            _new_m = ft_s.str.contains('신상', na=False) | (df['_dis_rate'] == 0)
            r_n = _fresh_w.get('new', 0.10 if is_outlet else 0.70)
            r_p = _fresh_w.get('plan', 0.20 if is_outlet else 0.10)
            fresh_cfg = [('신상', _new_m, r_n), ('기획', ft_s.str.contains('기획', na=False), r_p)]
        for label, mask, r_val in fresh_cfg:
            if r_val > 0 and _get_ref_count(mask) < (target_total * r_val): res["fresh"].append(label)

        # 시즌 부족 — score()와 동일한 DIAG_MONTH 기준 매핑
        sc = df['season_code'].astype(str).str.strip() if 'season_code' in df.columns else pd.Series([''] * len(df))
        CO_SPRING = ['봄', '1', '9', 'SS']; CO_SUMMER = ['여름', '2', '9', 'SS']
        CO_AUTUMN = ['가을', '3', '8', '9', 'FW']; CO_WINTER = ['겨울', '4', '9', 'FW']
        month = self.current_month  # DIAG_MONTH(4) 고정
        sea_inv = inv_weights.get('season', {})
        non_zero_seasons = sum(1 for v in sea_inv.values() if v > 0)

        if non_zero_seasons <= 2:
            primary_r   = sea_inv.get('spring', sea_inv.get('current', 0.50))
            secondary_r = sea_inv.get('summer', sea_inv.get('other',   0.30))
            if month in [1, 2, 3, 4]:   curr_codes, sub_codes = CO_SPRING, CO_SUMMER
            elif month in [5, 6]:        curr_codes, sub_codes = CO_SUMMER, CO_SPRING
            elif month in [7, 8, 9]:     curr_codes, sub_codes = CO_AUTUMN, CO_WINTER
            else:                         curr_codes, sub_codes = CO_WINTER, CO_AUTUMN
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
