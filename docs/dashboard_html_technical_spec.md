# E·LAND AI Assortment Agent — Dashboard HTML 기술 명세서

**대상 파일**: `ui/dashboard_template.html`, `core/html_generator.py`, `core/data_loader.py`  
**연관 파일**: `core/scoring_logic.py`, `core/analyzer.py`, `main.py`, `config/scoring_config.py`  
**문서 목적**: AX 개발팀 인수인계용 전체 구현 로직 및 기능 상세 기술  
**현재 버전**: v17.33 (REPORT_VERSION 기준)

---

## 1. 전체 아키텍처 개요

### 1.1 시스템 구성도

```
Google Sheets (Records)
        │
        ▼
core/data_loader.py  ── preprocess_raw_records()
        │                  └─ Unicode NFC 정규화
        │                  └─ store_name 정규화 (NC/뉴코아/동아/2001 제거)
        │                  └─ year 필터 (정상매장 연도없는 재고 제거)
        │                  └─ storemaster 동적 오버라이드 (평수·매출·목표)
        │
        ├── load_dashboard_data()
        │     ├── P1: scoreData {store → [전체, 여성, 아동, 신사, 캐주얼, 스포츠, 잡화]}
        │     ├── P2: BRANDS [{name, store, category, total, dis, fresh, season, best, ...}]
        │     ├── P3: DETAIL {store → brand → type_label → {item, dis, fresh, season, best}}
        │     ├── P3: BEST_ITEMS {store → brand → type_label → {store: [rank1..10]}}
        │     └── P3: ACTION_PLAN {store → brand → type_label → {ai_unified, push}}
        │
        ▼
main.py ── JSON 직렬화 → HTML 템플릿 <script> 주입
        │
        ▼
ui/dashboard_template.html  (SPA — Single Page Application)
        └── Streamlit st.components.v1.html(final_html, height=5500)
```

### 1.2 데이터 주입 방식

`main.py`에서 JSON을 HTML 템플릿의 첫 번째 `<script>` 태그 앞에 직접 삽입합니다.

```python
# main.py:678
script_inject = (
    f'<script id="__data" type="application/json">{safe_json}</script>\n'
    f'<script>window.__ALL_DATA__ = JSON.parse(document.getElementById("__data").textContent);</script>\n'
)
final_html = html_template.replace("<script>", script_inject + "<script>", 1)
```

브라우저에서는 `window.__ALL_DATA__` 객체가 전역으로 노출되며, JS 초기화 코드가 이를 파싱해 `STORES`, `BRANDS`, `DETAIL`, `BEST_ITEMS`, `ACTION_PLAN`, `SCORING_GUIDE` 변수에 할당합니다.

**다중 월 데이터 구조**:  
`window.__ALL_DATA__`는 `{ "3월": {...}, "4월": {...} }` 형태로 월별 스냅샷을 모두 보유하며, 글로벌 월 셀렉터(`#globalMonthSelector`) 변경 시 해당 월 데이터로 전환합니다.

---

## 2. HTML 구조 — 4개 페이지 (SPA)

```
.app
 ├── .sidebar (좌측 네비게이션 — 245px / 축소 시 70px)
 │     ├── logo-area (E·LAND 로고 + "상품구색 시스템")
 │     ├── nav-item: p1 🏬 지점별 상품 구색 점수판
 │     ├── nav-item: p2 📊 브랜드별 비교 대시보드
 │     ├── nav-item: p3 👚 매장별 상세 현황판
 │     └── nav-item: p4 📥 RAW데이터 입력
 │
 └── .main
       ├── .topbar (브레드크럼 + 글로벌 월 셀렉터)
       └── .content
             ├── #p1 (지점별 점수판)
             ├── #p2 (브랜드 비교)
             ├── #p3 (브랜드 상세)
             └── #p4 (데이터 입력)
```

페이지 전환: `showPage(id, el)` — 현재 `.page.active` 제거 후 대상 페이지에 `active` 추가.

---

## 3. 페이지별 상세 기능

### 3.1 P1 — 지점별 상품 구색 점수판

**목적**: 관리 대상 전 지점의 카테고리별 구색 점수를 한 눈에 비교

#### 3.1.1 테이블 구조

| 지점명 | 전체 | 여성 | 아동 | 신사 | 캐주얼 | 스포츠 | 잡화 |
|--------|------|------|------|------|--------|--------|------|
| 신구로점 | ● | ● | ● | … | | | |

- **지점명 셀**: 클릭 시 `openStoreModal(store, '전체')` — 단, '전체'는 모달 표시하지 않음
- **점수 배지(`.badge-score`)**: 색상은 그라디언트 + 등급 레이블로 표기

```
A (≥80): 파랑  gradient(#3B82F6, #2563EB)
B (60-79): 앰버 gradient(#F59E0B, #D97706)
C (40-59): 빨강 gradient(#EF4444, #DC2626)
D (<40):  진빨 gradient(#991B1B, #7F1D1D)
데이터 없음: —
```

- **배지 클릭**: `openStoreModal(store, cat)` → P1 지점 분석 모달 오픈

#### 3.1.2 P1 지점 분석 모달 (`#storeModal`)

특정 지점·카테고리 클릭 시 나타나는 모달. 해당 카테고리의 브랜드별 상세 점수 표시.

| 컬럼 | 내용 |
|------|------|
| 브랜드명 | 이름 + 정상/상설 배지 |
| 월 매출(성장률) | `sales_amt` 백만원 + 전년동월 대비 `growth_pct` (▲빨/▼파) |
| 종합 점수 | `product_score` |
| 목표대비 재고액 | `sM / tM_inv * 100%` — 진행 바 + 충족/부족 배지 |
| 할인율 | `dis` 점수 (빨강) |
| 신선도 | `fresh` 점수 (파랑) |
| 시즌 | `season` 점수 (앰버) |
| BEST | `best` 점수 (초록) |

- 행 클릭: 모달 닫고 `selectBrand(store, b.name)` 호출 → P3로 이동
- 정렬: `dis === 0` 브랜드 후순위, 나머지는 `total` 내림차순

#### 3.1.3 엑셀 다운로드 모달 (`#dl-modal-overlay`)

- 지점 / 카테고리 / 지표 (할인율, 신선도, 시즌, BEST 등) 선택 후 다운로드
- `confirmDownload()` 함수에서 JS로 CSV/XLS 생성

#### 3.1.4 P1 점수 계산 (Python, `data_loader.py`)

```python
# 카테고리별 가중 평균 (매출 비중)
for brand in loop_brands:
    score = _score_df_product(b_df, cfg)          # product_score
    b_sales = prev_benchmark_sales or b_df['sales_amt'].sum()
    cat_scores_with_sales.append((score, b_sales))

# 전체 = 카테고리별 점수를 카테고리 매출 비중으로 재가중
total_sales = sum(s[1] for s in cat_scores_with_sales)
weighted_avg = sum(s[0] * (s[1] / total_sales) for s in cat_scores_with_sales)
```

할인율 점수(dis)가 0인 브랜드는 카테고리 합산에서 제외하고, 제외 후 브랜드가 없으면 전체 포함 폴백 처리.

---

### 3.2 P2 — 브랜드별 비교 대시보드

**목적**: 특정 카테고리 내 전 브랜드 × 입점 매장별 구색 점수 횡단 비교

#### 3.2.1 카테고리 필터

우측 상단 `#p2_category_sel` — `여성 / 스포츠 / 신사 / 아동 / 캐주얼 / 잡화`

`changeP2Category(value)` 호출 시 `buildBrandComparisonTable()` 재실행.

#### 3.2.2 브랜드 비교 테이블 (`#p2BrandTbody`)

선택한 카테고리에 속한 브랜드별 **NC 전체 입점 매장 평균** 점수 표시.

| 컬럼 | 내용 |
|------|------|
| 브랜드명 | 이름 (클릭 시 입점 매장 모달 오픈) |
| 종합점수 | 평균 `total` |
| 할인율 | 평균 `dis` |
| 신선도 | 평균 `fresh` |
| 시즌 | 평균 `season` |
| BEST상품 | 평균 `best` |

- 행 클릭: `openP2BrandModal(brandName)` → 입점 매장별 상세 점수 팝업

#### 3.2.3 입점 매장별 점수 모달 (`#p2BrandModal`)

선택 브랜드의 입점 전 매장을 나열. 매장 행 클릭 시 해당 매장의 P3 상세로 이동.

컬럼 구성: 입점 매장명 / 월 매출(성장률) / 종합 점수 / 목표대비 재고액 / 할인율 / 신선도 / 시즌 / BEST

---

### 3.3 P3 — 매장별 상세 현황판

**목적**: 특정 지점 × 브랜드의 4대 구색 지표 현황 + BEST 상품 + 층장 액션 가이드 표시

#### 3.3.1 상단 헤더

```
[브랜드명]  [지점명]  [정상/상설]   SCORE  [점수] 점
                                     ⓘ (채점 로직 팝업)
          ← 지점 셀렉터 | 카테고리 셀렉터 | 브랜드 셀렉터 →
```

- **점수 계산** (JS): `dis*w_dis/100 + fresh*w_fresh/100 + season*w_sea/100 + bestPct*w_best/100`
- **네비게이터 드롭다운** (`#p2_store_sel`, `#p2_cat_sel`, `#p2_brand_sel`): 연동 변경 지원

#### 3.3.2 경고 배너 (`#alertArea`)

목표재고 미달 시 표시:
```
! 목표 재고 미달 — 필요 재고액(목표매출 × 3) 대비 XX% 보유 (YY%p 부족)
```

#### 3.3.3 KPI 섹션 (`#kpiGrid`)

**좌측 매출현황 카드**:
- `XX년 N월 매출액(성장세)`: `sales_amt` 백만원 + 전년동월 대비 `growth_pct`
- 평당 매출액: `salesAmt * 1,000,000 / days / area` (원/일/평)
  - < 40,000: 빨강/저조
  - ≥ 100,000: 초록/양호
  - 나머지: 검정/평균수준

**우측 재고현황 카드**:
- `N+1월 목표 매출`: `tM` 백만원 (전년동월 × 1.3 자동 계산)
- 재고 현황: `sM M / 목표 tM_inv M`
  - 달성률 바 + 상태 배지 (충족/부족/심각미달)
  - `tM_adjusted = 'cap'`이면 "평매출상한" 뱃지 표시

**목표재고액 공식**: 
- 평수 ≥ 50평: `평수 × 7만원 × 30일 × 3배`
- 평수 > 0: `평수 × 10만원 × 30일 × 3배`
- 평수 미설정: `tM_won × 3`

#### 3.3.4 4대 지표 카드 (`#detailGrid`, `.metrics-4-grid`)

4개 카드가 2×2 그리드로 배치 (1400px 이하: 2열, 768px 이하: 1열).

각 카드 구성:
```
[지표명]  [추정 배지]  [평균할인율 배지]      XX / 100점
---------------------------------------------------------
[목표 부족 알림 박스] ← 부족 구간 있을 때만 표시
---------------------------------------------------------
구간 1:
  목표 재고액 ────────────── N백만원
  보유 재고액 ─────── N백만원 (N EA)
  
구간 2: ...
```

**듀얼 바 게이지 계산**:
- 목표 바 너비: `(seg.opt_pct / maxOptPct) * 100%` (카드 내 상대 비중)
- 보유 바 너비: `min(100, targetW * (달성률/100))`
- 달성률 색상: 100%→초록, 75%→연두, 50%→파랑, 25%→앰버, 나머지→빨강

**달성률 배지**:
- ≥ 140%: `초과` (파랑)
- ≤ 60%: `부족` (빨강)
- `opt_pct === 0`: `-` (목표 없는 비채점 항목)

##### 3.3.4.1 할인율 카드 (`dis`)

| 정상 매장 (연차 기반) | 상설·스포츠 매장 (실제 할인율 기반) |
|---|---|
| 정상가 (0년차) | 70% 이상 |
| 1년차 | 50~70% 미만 |
| 2년차 | 30~50% 미만 |
| 3년차 | 1~30% 미만 |
| 4년차↑ | |

- **실제 할인율 사용 조건**: 상설(`_is_outlet(store_type)`), 스포츠/아웃도어/애슬레저 조닝, 또는 `has_dis_data && 로엠 제외`
- **할인율 미변환 보정**: rate-based 모드에서 전체 재고액 대비 알려진 할인율 재고액 비율로 `dis_scale` 적용
- **평균 할인율 표시**: 카드 헤더에 `평균 XX%` 배지

##### 3.3.4.2 신선도 카드 (`fresh`)

DB의 `freshness_type` 필드 텍스트만 신뢰 (연차/할인율 추정 로직 사용 안 함).

| 타입 | 정상 목표 비중 | 상설 목표 비중 |
|------|------|------|
| 신상 (텍스트에 '신상' 포함) | 70% | 10% |
| 기획 (텍스트에 '기획' 포함) | 0% | 20% |

##### 3.3.4.3 시즌 카드 (`season`)

4개 계절 고정 노출. `data_month` 기준으로 목표 계절 결정.

| data_month | 주력 시즌(50%) | 부 시즌(30%) |
|---|---|---|
| 1~3월 | 봄 | 여름 |
| 4~6월 | 여름 | 봄 |
| 7~9월 | 가을 | 겨울 |
| 10~12월 | 겨울 | 가을 |

계절 코드 매핑 (season_code):
- 봄: `['봄', '1', '9']`
- 여름: `['여름', '2', '9']`  
- 가을: `['가을', '3', '8', '9']`
- 겨울: `['겨울', '4', '9']`

비채점 계절은 달성률 `-` 표기, 색상 회색.

##### 3.3.4.4 BEST 카드 (`best`)

판매 BEST 10 품번(`sales_qty` 합산 상위 10개)에 해당하는 재고 합산.

- 목표 비중: `inv_weights.best.store10` (기본 25%, 상설 20%)
- `best_pct = best_amt / (target_total * best_ratio) * 100`

#### 3.3.5 아이템(복종별) 모니터링 패널 (`#itemMonitoringPanel`)

4대 지표 채점에 포함되지 않는 복종별 재고 배분 현황을 별도 표시.

조닝별 아이템 레이블 매핑:

| 조닝 | 아이템 구성 |
|------|---|
| 여성 | 아우터, 상의, 하의, 스커트, 원피스 |
| 스포츠 | 상의, 하의, 러닝화, 워킹화, 기타신발 |
| 아웃도어 | 아우터, 상의, 하의, 트레킹화, 라이프스타일화 |
| 남성 | 정장, 셔츠, 캐주얼, 니트, 하의 |
| 아동 | 아우터, 상의, 하의, 원피스, 상하세트 |
| 커리어 | 아우터, 상의, 원피스, 하의, 스커트 |

아이템 그룹 판별 로직:
1. `item_code` 슬라이딩 스캔 → `ITEM_GROUPS` 매핑
2. 아동 조닝: `ITEM_CODE_KIDS` 우선
3. 남성 조닝: `ITEM_CODE_MENS` 우선
4. 공통: `ITEM_CODE_DIRECT` 폴백
5. 스포츠 조닝: 상품명·카테고리 키워드로 신발류 추가 분기

#### 3.3.6 층장 액션 가이드 (`#actionPanel`)

2컬럼 패널 — 파랑(재고 확보 필요) / 주황(집중 판매 필요)

**좌측: 재고 확보 필요** (자사 판매 BEST 10 중 재고 ≤ 5개 품번)
```
① 품번명 / 품번코드
   확보 필요 (재고 N개)  [사진 버튼]
```

**우측: 집중 판매 필요** (NC 전체 판매 BEST 10 중 자사 재고 > 5개 품번)
```
① 품번명 / 품번코드
   집중 판매 필요 (재고 N개)  [사진 버튼]
```

**[사진 버튼]**: `fetchProductImg(brand, styleCode, styleName)` 호출 → 네이버 쇼핑 API 또는 크롤링으로 이미지 URL 취득 후 모달 표시

**AI 종합 상세 진단 버튼**: `diagnoseComprehensive()` → LocalStorage 이벤트 → Streamlit Python 백엔드의 `core/ai_agent.py` 호출 (comm_plugin 제거 후 LocalStorage 폴링 방식)

#### 3.3.7 판매 BEST 10 테이블 (`#bestItems`)

최근 2주 판매량 기준 상위 10개 품번.

| 컬럼 | 내용 |
|------|------|
| 순위 | 1~10 (검정 배지) |
| 아이템명 | 카테고리 한국어 (ex: 아우터) |
| 품번 | `style_code` (monospace) |
| 스타일명 | 상품명 (GSheet > SQLite > 네이버 크롤링 순) |
| 판매가 | `normal_price` (원) |
| 판매량 | `sales_qty` EA |
| 재고액 | `stock_amt` 원 |
| 재고량 | `stock_qty` EA |

**스타일명 취득 우선순위** (`html_generator.py:_build_best_items`):
1. GSheet 원본 `style_name` (이랜드 ERP 한국어 이름 우선)
2. SQLite `product_master.db` — `products` 테이블
3. 네이버 쇼핑 OpenAPI (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수)
4. 네이버 통합검색 HTML 크롤링 (API 없을 때 폴백)

**단가 보완 로직**:
1. SQLite `normal_price`
2. GSheet의 valid `normal_price` (0 초과 첫 값)
3. `stock_amt / stock_qty` 역산
4. `sales_amt / sales_qty` 역산

#### 3.3.8 전월 대비 점수 변화 차트 (숨김 기본값)

`#momScoreChartContainer` — `renderMoMScoreChart()` 함수로 최근 3개월 막대 차트 렌더링. Chart.js 사용.

---

### 3.4 P4 — RAW 데이터 입력

**목적**: 재고/판매 데이터를 텍스트 붙여넣기 또는 엑셀 파일로 업로드

#### 3.4.1 4단계 선택 흐름

```
1. 지점명 선택 (ux_store)
      ↓ onUxStep(1)
2. 카테고리 선택 (ux_cat)
      ↓ onUxStep(2)
3. 브랜드(매장유형) 선택 (ux_brand)  — 예: "로엠|정상"
      ↓ onUxStep(3)
4. 대상 월 선택 (ux_month)
      ↓ onUxStep(4)
5. 파일/텍스트 영역 노출 → 업로드 버튼 활성화
```

#### 3.4.2 업로드 모드

**텍스트 붙여넣기 (기본)**:
- `#ux_inv_text`: 재고 데이터 (헤더 포함 복사+붙여넣기)
- `#ux_sales_text`: 판매 데이터
- **검증 필드**: `ux_check_qty` (총 재고량), `ux_check_amt` (총 재고액) — 입력 합계와 불일치 시 업로드 차단

**엑셀 파일 업로드**:
- `#ux_inv` (.xls, .xlsx): 재고조회 엑셀
- `#ux_sales` (.xls, .xlsx): 판매조회 엑셀

#### 3.4.3 `handleUpload()` 함수 흐름

```
1. 입력 유효성 검사 (모드별)
2. 텍스트/파일 파싱 → JSON 변환
3. Streamlit 백엔드로 POST (LocalStorage 이벤트 또는 fetch)
4. Google Sheets의 Records 시트에 행 추가
5. 성공/실패 상태 표시
```

---

## 4. 채점 엔진 (`core/scoring_logic.py`, `core/data_loader.py`)

### 4.1 채점 구조

```
product_score = 
    dis_score   * weight_discount   (기본: 정상 30%, 상설 30%)
  + fresh_score * weight_freshness  (기본: 정상 20%, 상설 20%)
  + season_score * weight_season    (기본: 정상 15%, 상설 15%)
  + best_score  * weight_best       (기본: 정상 35%, 상설 35%)
```

채점 가중치는 `config/scoring_config.py`의 `SCORING_CONFIG`에서 카테고리+매장유형+브랜드 조합으로 관리.

### 4.2 설정 조회 우선순위 (`_get_config`)

```python
key_brand = f"{category}_{normalized_type}_{brand}"  # 예: 여성_정상_로엠
key_type  = f"{category}_{normalized_type}"           # 예: 여성_정상
# → SCORING_CONFIG[key_brand] or SCORING_CONFIG[key_type] or SCORING_CONFIG["기본_설정"]
```

### 4.3 목표 매출액 (`get_tm`)

1. `MONTHLY_TM[store][ym_key][brand]` — storemaster 직접 지정값 최우선
2. `PREV_YEAR_MONTHLY_SALES[store][prev_ym_key][brand] * 1.3` — 전년동월 × 130%
3. `PREV_YEAR_SALES[store][brand]` — 전년 합산 (fallback)
4. 데이터 없으면 `area * 100,000 * 30` (평수 기반 추정)

### 4.4 고유 재고 추출 (`_get_stock_ref_gen`)

중복 제거 방법:
- `inv_uid` 컬럼 유효한 경우: `drop_duplicates('inv_uid')`
- 상설 매장 + inv_uid 없으면: 행 그대로 사용 (SKU 중복 허용)
- 나머지: `[style_code, year, season_code, price_type, stock_qty, stock_amt]` 기준 중복 제거

### 4.5 성장률 계산

```python
# 1순위: 전년동월
prev_yr_sales = PREV_YEAR_MONTHLY_SALES[store][prev_yr_mk][brand_norm]

# 2순위: PREV_YEAR_SALES (전년 전체)
prev_yr_sales = PREV_YEAR_SALES[store][brand_norm]

# 3순위: MoM fallback (MONTHLY_TM target vs PREV_MONTH_SALES)
g_pct = (mom_cur - mom_base) / mom_base * 100
```

---

## 5. 데이터 파이프라인 상세

### 5.1 Google Sheets 시트 구조

| 시트명 | 용도 |
|--------|------|
| Records | ERP 재고·판매 원시 레코드 |
| BrandMaster | 브랜드 → 조닝 매핑 |
| StoreMaster | 지점×브랜드 평수·유형·매출·목표 오버라이드 |

### 5.2 전처리 단계 (`preprocess_raw_records`)

1. **텍스트 정규화**: 모든 문자열 컬럼 `.strip()`, Unicode NFC 정규화
2. **지점명 정규화**: `NC / 뉴코아 / 동아 / 2001` 접두사 제거. `강남` → `강남점`, `불광` → `불광점`
3. **수치형 변환**: `stock_amt, stock_qty, sales_qty, sales_amt, normal_price` → `pd.to_numeric`
4. **storemaster 정적 오버라이드** (`config/storemaster_override.py`): 평수, 매장유형, 전년 매출, 목표 일괄 주입
5. **storemaster 동적 오버라이드** (GSheet StoreMaster 시트): 컬럼 패턴 `YY_MM`, `목표_MM` 파싱 → 매출/목표 딕셔너리 갱신
6. **year 필터**: 정상 매장 중 연도 없는 재고(신상 제외, 판매 없는 항목) 삭제

### 5.3 특수 브랜드 처리

| 브랜드 | 처리 |
|--------|------|
| 압소바, 더레노마 | `store_type` 강제 `상설` |
| 스파오키즈, 뉴발란스키즈 | `store_type` 강제 `정상` |
| 지오지아 계열 | `store_type` 강제 `상설` |
| 로엠, 미쏘, 에잇컨셉 | `store_type` 강제 `정상` |
| 스케쳐스 | `category_group` → `스포츠` |
| 골프웨어 카테고리 | `category_group` → `신사` |

### 5.4 마스터 브랜드 리스트 (`MASTER_CATEGORY_BRANDS`)

데이터가 없어도 특정 브랜드를 노출할 수 있는 고정 리스트. 현재 신구로점 여성(21개), 스포츠(1개), 부천점 아동(18개) 등 관리.

---

## 6. 핵심 Python 모듈

### 6.1 `core/html_generator.py`

| 함수 | 역할 |
|------|------|
| `_build_detail(df, config, tM)` | 브랜드 상세 JSON 생성 (item/dis/fresh/best/season 5개 구간) |
| `_build_best_items(df)` | 판매 BEST 10 품번 + 상품명 조회 |
| `_build_action_plan(b_df, bp_brand_df)` | 층장 액션 가이드 (ActionAnalyzer 위임) |
| `_naver_search_style_name(brand, style_code, item_code)` | 네이버 API → 크롤링 순 상품명 취득 |
| `_crawl_naver_shopping_title(brand, style_code, item_code)` | 네이버 통합검색 HTML 스크래핑 |
| `_get_dynamic_color(pct, p_type)` | 달성률 25% 구간별 색상 반환 |
| `_item_code_to_ko(item_code)` | item_code → 한국어 카테고리명 |
| `render_dashboard_html()` | HTML 템플릿 파일 읽어 문자열 반환 |

### 6.2 `core/data_loader.py`

| 함수 | 역할 |
|------|------|
| `preprocess_raw_records(mgr, raw_recs)` | Stage 1 전처리 (정규화, 오버라이드) |
| `load_dashboard_data(mgr, selected_month, ...)` | 전체 대시보드 JSON 생성 |
| `_get_config(category, store_type, brand)` | SCORING_CONFIG 조회 (3단계 우선순위) |
| `_score_df(df, config)` | DataFrame → total_score 반환 |
| `_score_df_product(df, config)` | DataFrame → product_score 반환 |

### 6.3 `core/analyzer.py` — `ActionAnalyzer`

```python
def get_action_recommendations(b_df, bp_brand_df) -> dict:
    # ai_unified: 자사 BEST 10 중 재고 ≤ 5개 → 확보 필요
    # push: NC 전체 BEST 10 중 자사 재고 > 5개 → 집중 판매 필요
    # has_bp_data: bp_brand_df 존재 여부
```

### 6.4 `core/scoring_logic.py` — `AssortmentScorer`

5개 지표 채점 엔진. 주요 정적 속성:

| 속성 | 설명 |
|------|------|
| `ITEM_GROUPS` | 품번 코드 앞 2자리 → 아이템 그룹 매핑 |
| `ITEM_CODE_KIDS` | 아동 전용 item_code 직접 매핑 |
| `ITEM_CODE_MENS` | 남성 전용 item_code 직접 매핑 |
| `ITEM_CODE_DIRECT` | 공통 item_code 직접 매핑 |
| `ZONING_ITEM_WEIGHTS` | 조닝별 아이템 가중치 |

### 6.5 `core/ai_agent.py`

AI 종합 진단 리포트 생성. Claude API 호출 (Anthropic). 다차원 비교 데이터 포함:
- 자사 vs 전년동월
- 자사 vs NC 동일 브랜드 평균
- 자사 vs NC 동일 카테고리 평균

---

## 7. 핵심 JavaScript 함수

| 함수 | 위치(줄) | 역할 |
|------|------|------|
| `showPage(id, el)` | ~2704 | SPA 페이지 전환 |
| `buildMainTable()` | ~2791 | P1 지점별 점수 테이블 렌더링 |
| `openStoreModal(store, cat)` | ~2823 | P1 지점 분석 모달 오픈 |
| `buildBrandComparisonTable()` | ~2650 | P2 브랜드 비교 테이블 렌더링 |
| `openP2BrandModal(brandName)` | ~2670 | P2 브랜드 입점 매장 모달 오픈 |
| `selectBrand(store, name)` | ~2930 | 브랜드 선택 → P3 렌더링 |
| `renderBrandDetail()` | ~2968 | P3 전체 렌더링 (헤더·KPI·4카드·BEST·액션) |
| `renderActionPanel()` | ~3395 | 층장 액션 가이드 패널 렌더링 |
| `renderItemMonitoringPanel(b, d)` | - | 복종별 재고 모니터링 패널 |
| `renderMoMScoreChart(b)` | - | 전월 대비 점수 차트 (Chart.js) |
| `showScoringLogicModal(cat)` | - | 채점 로직 ⓘ 팝업 |
| `fetchProductImg(brand, code, name)` | - | 네이버 이미지 조회 버튼 |
| `changeGlobalMonth(month)` | - | 글로벌 월 전환 |
| `initP2Selectors()` | ~2720 | P3 네비게이터 드롭다운 초기화 |
| `confirmDownload()` | - | P1 엑셀 다운로드 |
| `handleUpload()` | - | P4 데이터 업로드 처리 |
| `diagnoseComprehensive()` | - | AI 종합 진단 요청 |

---

## 8. 디자인 시스템 (CSS 변수)

```css
:root {
  --bg-main: #F8F9FA;       /* 배경 */
  --bg-card: #FFFFFF;       /* 카드 배경 */
  --bg-sidebar: #111111;    /* 사이드바 */
  --red: #E30019;           /* 이랜드 레드 (할인율 지표색) */
  --blue: #2563EB;          /* 신선도 지표색 */
  --green: #10B981;         /* BEST 지표색 */
  --amber: #F59E0B;         /* 시즌 지표색 */
  --radius-lg: 20px;
  --radius-md: 12px;
  --transition: all 0.2s ease-in-out;
}
```

**폰트**: `Outfit` (숫자/영문) + `Noto Sans KR` (한글) — Google Fonts CDN

**반응형 브레이크포인트**:
- > 1400px: 4열 그리드
- 1100~1400px: 2열 그리드
- 768~1100px: 사이드바 자동 축소 (70px), 2열
- < 768px: 사이드바 오버레이, 1열

---

## 9. 모달 시스템

| 모달 ID | 용도 | 오픈 함수 |
|---------|------|-----------|
| `#storeModal` | P1 지점 분석 (브랜드 목록) | `openStoreModal()` |
| `#p2BrandModal` | P2 브랜드 입점 매장 점수 | `openP2BrandModal()` |
| `#dl-modal-overlay` | P1 엑셀 다운로드 옵션 | `openDownloadModal()` |

**모달 애니메이션**:
- 오픈: `modalSlideIn` (scale 0.93→1 + translateY -24px→0, 0.3s)
- 닫힘: `modalSlideOut` (scale 1→0.95 + translateY 0→12px, 0.22s)
- 오버레이: `fadeOverlay` / `fadeOverlayOut` (opacity 0.28s)

**커서 위치 자동 배치** (`_openModalAtCursor`): 마우스 클릭 좌표 기준 모달 위치 조정.

---

## 10. 캐싱 전략

### Python 서버 사이드

| 대상 | 캐싱 위치 | TTL |
|------|-----------|-----|
| 네이버 API 상품명 조회 | `_NAME_SEARCH_CACHE` (메모리 dict) | 6시간 |
| 상품명·이미지 | `database/product_master.db` → `products` 테이블 | 영구 |
| 상품명 | `core/style_master.json` | 영구 |

### Streamlit 세션 캐시

- `st.cache_data` / `st.cache_resource` 적용 (GSheetManager, 전처리 결과)
- `_preprocessed` 튜플 주입으로 Stage 1 전처리 1회만 실행 (월 변경 시 재사용)

---

## 11. 보안 및 성능 고려사항

### JS 에러 오버레이

```html
<div id="js-error-overlay">...</div>
<script>
  window.onerror = function(msg, url, lineNo, ...) { ... }
  window.addEventListener('unhandledrejection', ...)
</script>
```

렌더링 실패 시 에러 내용을 화면 상단에 표시.

### XSS 방지

JSON 주입 시 `</script>` 이스케이프:
```python
safe_json = all_data_json.replace("</script>", "<\\/script>")
```

### 메모리 관리

Streamlit Cloud 1GB 한도 대응:
```python
del all_data_json, final_html, script_inject
gc.collect()
```

### comm_plugin 제거 이유

`components.declare_component`가 Streamlit Cloud에서 invisible iframe 오버레이를 생성해 대시보드 클릭을 차단. → LocalStorage 폴링 방식으로 AI 진단 요청 전달.

---

## 12. 주요 설정 파일

| 파일 | 내용 |
|------|------|
| `config/scoring_config.py` | 카테고리×매장유형별 채점 가중치·inv_weights |
| `config/brand_targets.py` | 지점×브랜드별 목표매출, 전월·전년 실적 |
| `config/area_config.py` | 지점×브랜드 평수 |
| `config/store_type_config.py` | 지점×브랜드 매장유형 + display_label |
| `config/storemaster_override.py` | 정적 오버라이드 (평수·매출·목표) |
| `database/product_master.db` | 상품명·가격 캐시 (SQLite) |
| `core/style_master.json` | 네이버 크롤링 결과 누적 캐시 |

---

## 13. 데이터 구조 — JS 전역 변수

```js
// 월별 전체 데이터 (window.__ALL_DATA__)
{
  "3월": {
    CATS: ["전체", "여성", "아동", "신사", "캐주얼", "스포츠", "잡화"],
    STORES: ["신구로점", "부천점", ...],
    AVAILABLE_MONTHS: ["6월", "5월", ...],
    SELECTED_MONTH: "3월",
    
    scoreData: {
      "신구로점": [85, 90, 70, 0, 0, 80, 0],  // CATS 순서
      ...
    },
    
    BRANDS: [
      {
        name: "로엠", store: "신구로점", category: "여성",
        type: "normal",               // "normal" | "outlet"
        type_label: "정상",           // display_label (storemaster)
        total: 78,                    // total_score
        product_score: 78,            // 4대 지표 합산
        eff_score: 65,                // 효율 점수 (미사용)
        item: 0,                      // 복종 점수 (미채점)
        dis: 85, fresh: 70, season: 60, best: 80,
        dis_estimated: false,
        avg_discount_rate: 24.5,
        zoning: "커리어",
        tM: 15.0,      // 목표매출 (백만원)
        tM_inv: 45.0,  // 목표재고 (백만원) = tM * 3 or 평수 기반
        tM_adjusted: "cap",  // null | "cap"
        sM: 38.5,      // 현재고액 (백만원)
        sQ: 1250,      // 현재고량 (EA)
        sales_amt: 12.3,      // 당월 매출 (백만원)
        prev_sales: 11.8,     // 전월(또는 기준월) 매출
        prev_yr_sales_amt: 9.5,
        growth_pct: 25.3,     // 전년동월 대비 성장률 (%)
        area: 45.0,           // 평수
        month: "3월",
        data_month: "3월",
        scoring_guide: {
          score_weights: { dis:30, fresh:20, sea:15, best:35, item:0 },
          item_w: { Outer:30, Top:30, Bottom:20, Skirt:10, Dress:10 },
          dis_w: { s0:70, s10:15, s30:10, s50:5, s70:0 },
          fresh_w: { new:70, plan:0 },
          sea_w: { spring:50, summer:30 },
          best_pct: 25,
          is_outlet: false
        }
      }, ...
    ],
    
    DETAIL: {
      "신구로점": {
        "로엠": {
          "정상": {               // type_label 키
            item: { segs: [
              { key:"Outer", l:"아우터", valM:12.5, qty:180,
                c:"#7C3AED", weight:30, pct:95.0,
                targetM:13.2, mix_pct:32.5, opt_pct:30 }, ...
            ]},
            dis: { segs: [...] },
            fresh: { segs: [...] },
            best: { segs: [...] },
            season: { segs: [
              { key:"spring", l:"봄 (SS)", ..., is_score_target:true }, ...
            ]},
            total_qty_unique: 1250
          }
        }
      }
    },
    
    BEST_ITEMS: {
      "신구로점": {
        "로엠": {
          "정상": {
            store: [
              { rank:1, item_name:"아우터", style_code:"ABCD1234",
                style_name:"[로엠] 울혼방 더블 코트", price:189000,
                sales:48, valWon:5670000, qty:30 }, ...
            ]
          }
        }
      }
    },
    
    ACTION_PLAN: {
      "신구로점": {
        "로엠": {
          "정상": {
            ai_unified: [
              { rank:1, icon:"⚠️", tag:"확보 필요",
                style_code:"ABCD1234", style_name:"...",
                action_msg:"<span ...>확보 필요 (재고 3개)</span>",
                keywords:["재고부족","인기상품","추가입고"],
                sub_info:"현재고 3EA / 2주 판매 48EA" }
            ],
            push: [
              { rank:1, style_code:"...", style_name:"...",
                sales_qty:120, stock_qty:25,
                tag:"집중 판매 필요",
                reason:"<span ...>집중 판매 필요 (재고 25개)</span>" }
            ],
            has_bp_data: true
          }
        }
      }
    },
    
    SCORING_GUIDE: {
      "여성": {
        normal: {
          score_weights: { dis:30, fresh:20, sea:15, best:35 },
          dis_w: { s0:70, s10:15, s30:10, s50:5 },
          fresh_w: { new:70 },
          sea_w: { spring:50, summer:30 },
          best_pct: 25
        },
        outlet: { ... },
        zonings: { "커리어": {...}, "캐릭터": {...} }
      }, ...
    }
  }
}
```

---

## 14. 버전 관리 및 변경 이력 (주요)

| 버전 | 핵심 변경 |
|------|-----------|
| v17.33 | 상설 매장 할인율 로직 rate-based 강제 (html_generator ↔ scoring_logic 동기화) |
| v202.4 | 재고액 누락 방지 — 판매 중복행 `drop_duplicates` 대신 sales 컬럼만 0 처리 |
| v200.0 | ActionAnalyzer 분리 (core/analyzer.py) |
| v176.0 | 목표재고액 공식 통일 (평수 × 10만 × 30일 × 3배) |
| v146.0 | 매출현황·재고현황 통합 레이아웃 |
| v121.0 | inv_uid 기반 중복 제거 도입 |
| v114.0 | 데이터 없는 브랜드 P1 합산 제외 |
| v107.0 | 특정 브랜드 정상/상설 고정 처리 |
| v100.x | P2 네비게이터 개편, 스타일 대규모 리팩토링 |
| v68.4 | 마스터 브랜드 리스트 도입 (데이터 없어도 브랜드 노출) |

---

## 15. 개발 환경 및 의존성

| 패키지 | 용도 |
|--------|------|
| `streamlit` | 웹 앱 프레임워크 |
| `pandas` | 데이터 처리 |
| `gspread` / `google-auth` | Google Sheets API |
| `sqlite3` (표준) | 상품 마스터 DB |
| `anthropic` | Claude AI API |
| `plotly` | Streamlit 차트 (ui/dashboard_view.py) |
| Chart.js (CDN) | 대시보드 내부 Bar 차트 |
| Google Fonts (CDN) | Outfit, Noto Sans KR |

**환경변수**:
```
NAVER_CLIENT_ID      # 네이버 쇼핑 OpenAPI ID
NAVER_CLIENT_SECRET  # 네이버 쇼핑 OpenAPI Secret
ANTHROPIC_API_KEY    # Claude AI 진단용
GOOGLE_SHEETS_ID     # 대상 Google Spreadsheet ID
```

---

*이 문서는 `dashboard_template.html` (4,710 lines), `html_generator.py`, `data_loader.py`, `scoring_logic.py`, `analyzer.py`, `main.py`를 기반으로 작성되었습니다.*  
*작성일: 2026-06-25*
