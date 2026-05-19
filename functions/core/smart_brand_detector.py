"""
core/smart_brand_detector.py
=============================
[역할] 업로드된 엑셀 파일의 컬럼명·데이터 패턴을 분석해서
       어느 법인의 파일인지 자동으로 인식하는 AI 엔진

■ 3단계 인식 전략:
  1단계 (파일명/헤더): 브랜드명 텍스트로 즉시 판별 (신뢰도 HIGH)
  2단계 (룰 기반)  : 법인별 고유 컬럼명 패턴 매칭 (신뢰도 HIGH/MEDIUM)
  3단계 (AI 기반)  : 룰 판별 불가 시 Gemini API로 컬럼 의미 해석

■ 반환값:
  { 'company': 'ElandWorld' | 'IndongFN' | 'BabaGroup' | 'LotteGFR' | 'Generic',
    'confidence': 'high' | 'medium' | 'low',
    'matched_cols': [...],
    'reason': '판별 근거 설명' }
"""

import os
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# 각 법인별 고유 컬럼명 시그니처 (많을수록 정확도 ↑)
# 컬럼명이 실제 파일 헤더와 부분 일치(contains)로 비교
# ──────────────────────────────────────────────────────────────────
COMPANY_SIGNATURES = {
    "ElandWorld": {
        # 이랜드 ERP 고유 표현
        "unique": ["단가 유형", "판매가 능재고", "현단가 (세일제외)", "장부재고금액"],
        "common": ["년도", "시즌", "스타일", "단가유형", "아이템"],
        "min_match": 2,  # unique 중 몇 개 이상 매칭되면 확정
    },
    "IndongFN": {
        # 인동FN 고유 표현
        "unique": ["가용재고수량", "가용재고금액", "단가구분", "가용 재고수량"],
        "common": ["시즌", "품번", "아이템", "가용"],
        "min_match": 2,
    },
    "BabaGroup": {
        # 바바그룹 고유 표현
        "unique": ["생산년도", "재고수량", "재고금액", "제조년도"],
        "common": ["생산", "상품코드", "아이템명", "정가"],
        "min_match": 1,
    },
    "LotteGFR": {
        # 롯데GFR 고유 표현
        "unique": ["가용수량", "가용금액", "스타일번호"],
        "common": ["시즌", "년도", "아이템", "정상가"],
        "min_match": 2,
    },
}

# 브랜드명 → 법인 명시적 매핑 (브랜드명이 텍스트로 등장하는 경우)
BRAND_TO_COMPANY_MAP = {
    "로엠": "ElandWorld",
    "ROEM": "ElandWorld",
    "미쏘": "ElandWorld",
    "MIXXO": "ElandWorld",
    "리스트": "IndongFN",
    "LIST": "IndongFN",
    "쉬즈미스": "IndongFN",
    "SHESMISS": "IndongFN",
    "JJ지고트": "BabaGroup",
    "JJIGOT": "BabaGroup",
    "바바팩토리": "BabaGroup",
    "BABAFACTORY": "BabaGroup",
    "나이스클랍": "LotteGFR",
    "NICECLAUP": "LotteGFR",
    "베네통": "Generic",
    "BENETTON": "Generic",
    "시슬리": "Generic",
    "SISLEY": "Generic",
}


class SmartBrandDetector:
    """
    엑셀 파일을 받아서 어느 법인인지 자동으로 판별하는 클래스
    """

    def __init__(self, gemini_api_key: str = None):
        # Gemini API 키 (환경변수 또는 직접 전달)
        self.api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

    # ──────────────────────────────────────────
    # 메인 진입점
    # ──────────────────────────────────────────
    def detect(self, data, file_name: str = "") -> dict:
        """
        엑셀 파일 → 법인명 자동 판별

        Args:
            data : 파일 객체(UploadedFile) 또는 BytesIO
            file_name : 파일명 (확장자 판별용)

        Returns:
            { 'company', 'confidence', 'matched_cols', 'reason' }
        """
        try:
            df = self._read_excel_preview(data, file_name)
            cols = [str(c).strip() for c in df.columns.tolist()]
        except Exception as e:
            logger.error(f"[SmartDetector] 미리보기 읽기 실패: {e}")
            return self._make_result("Generic", "low", [], f"파일 읽기 실패: {e}")

        # 1단계: 블랙리스트 품목 기반 브랜드명 인식 (파일명 또는 헤더 최상단 셀)
        brand_result = self._detect_by_brand_name(df, file_name)
        if brand_result:
            return brand_result

        # 2단계: 컬럼 시그니처 룰 기반 판별
        rule_result = self._detect_by_column_rules(cols)
        if rule_result and rule_result['confidence'] in ('high', 'medium'):
            return rule_result

        # 3단계: Gemini API 기반 AI 판별 (룰 실패 시)
        if self.api_key:
            logger.info("[SmartDetector] 룰 기반 판별 실패 → Gemini API 호출")
            ai_result = self._detect_by_gemini_api(cols, df)
            if ai_result:
                return ai_result

        # 최종 fallback: Generic
        return self._make_result("Generic", "low", cols[:5], "법인 판별 불가 → 범용 파서 사용")

    # ──────────────────────────────────────────
    # 내부 메서드
    # ──────────────────────────────────────────
    def _read_excel_preview(self, data, file_name: str = "", max_rows: int = 5) -> pd.DataFrame:
        """엑셀 파일을 읽어서 컬럼명 + 상위 N행만 반환 (속도 최적화)"""
        import io

        if isinstance(data, pd.DataFrame):
            return data.head(max_rows)

        fname = getattr(data, 'name', file_name).lower()

        if fname.endswith('.xlsx'):
            try:
                if hasattr(data, 'seek'):
                    data.seek(0)
                return pd.read_excel(data, nrows=max_rows, engine='openpyxl')
            except Exception:
                pass

        # xls(HTML 위장) 폴백
        if hasattr(data, 'seek'):
            data.seek(0)
        raw = data.read() if hasattr(data, 'read') else open(data, 'rb').read()
        try:
            html_str = raw.decode('utf-8')
        except UnicodeDecodeError:
            html_str = raw.decode('euc-kr', errors='replace')

        import io as _io
        tables = pd.read_html(_io.StringIO(html_str))
        if tables:
            return max(tables, key=len).head(max_rows)

        raise ValueError("읽기 가능한 테이블 없음")

    def _detect_by_brand_name(self, df: pd.DataFrame, file_name: str) -> dict | None:
        """파일명·최상단 셀에서 브랜드명 텍스트를 찾아 법인 판별"""
        # 파일명에서 브랜드명 탐색
        for brand, company in BRAND_TO_COMPANY_MAP.items():
            if brand.lower() in file_name.lower():
                return self._make_result(
                    company, "high", [brand],
                    f"파일명에서 브랜드명 '{brand}' 감지 → {company}"
                )

        # DataFrame 최상단 2행 텍스트에서 탐색
        try:
            top_text = df.head(2).to_string()
            for brand, company in BRAND_TO_COMPANY_MAP.items():
                if brand in top_text:
                    return self._make_result(
                        company, "high", [brand],
                        f"파일 헤더에서 브랜드명 '{brand}' 감지 → {company}"
                    )
        except Exception:
            pass

        return None

    def _detect_by_column_rules(self, cols: list) -> dict | None:
        """컬럼명 시그니처 기반 룰 매칭"""
        scores = {}
        matched_cols_map = {}

        for company, sig in COMPANY_SIGNATURES.items():
            unique_matches = [c for c in sig["unique"] if any(c in col for col in cols)]
            common_matches = [c for c in sig["common"] if any(c in col for col in cols)]

            score = len(unique_matches) * 3 + len(common_matches) * 1
            scores[company] = score
            matched_cols_map[company] = unique_matches + common_matches

            # unique 시그니처를 최소 기준 이상 맞추면 즉시 확정
            if len(unique_matches) >= sig["min_match"]:
                return self._make_result(
                    company, "high",
                    unique_matches,
                    f"고유 컬럼 {unique_matches} 매칭 (룰 기반 확정)"
                )

        # 최고 점수 법인 선택 (애매한 경우 medium 신뢰도)
        if scores:
            best = max(scores, key=scores.get)
            best_score = scores[best]
            if best_score >= 4:
                return self._make_result(
                    best, "medium",
                    matched_cols_map[best],
                    f"컬럼 매칭 점수 {best_score}점 (상위 매칭)"
                )

        return None

    def _detect_by_gemini_api(self, cols: list, df: pd.DataFrame) -> dict | None:
        """
        컬럼명 목록을 Gemini API에 전달하고 법인 판별 요청
        응답: JSON { "company": "...", "reason": "..." }
        """
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            sample_data = df.head(3).to_string()
            prompt = f"""다음은 한국 패션 아울렛 브랜드의 ERP 시스템에서 추출된 엑셀 파일의 컬럼명과 샘플 데이터입니다.

컬럼명 목록:
{cols}

샘플 데이터 (상위 3행):
{sample_data}

이 파일이 아래 4개 법인 중 어느 법인의 ERP에서 추출된 것인지 판별해주세요:
- ElandWorld  (브랜드: 로엠, 미쏘)
- IndongFN    (브랜드: 리스트, 쉬즈미스)
- BabaGroup   (브랜드: JJ지고트, 바바팩토리)
- LotteGFR   (브랜드: 나이스클랍)
- Generic     (판별 불가)

반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"company": "법인명", "reason": "판별 근거 1~2문장"}}"""

            response = model.generate_content(prompt)
            raw = response.text.strip()

            # JSON 파싱 (마크다운 코드블록 제거 후 시도)
            raw = raw.replace('```json', '').replace('```', '').strip()
            if raw.startswith('{'):
                result = json.loads(raw)
            else:
                start = raw.find('{')
                end   = raw.rfind('}') + 1
                result = json.loads(raw[start:end])

            company = result.get("company", "Generic")
            reason  = result.get("reason", "Gemini API 판별")

            # 유효한 법인명인지 검증
            valid = {"ElandWorld", "IndongFN", "BabaGroup", "LotteGFR", "Generic"}
            if company not in valid:
                company = "Generic"

            return self._make_result(company, "medium", cols[:3], f"[Gemini AI 판별] {reason}")

        except ImportError:
            logger.warning("[SmartDetector] google-generativeai 미설치 → Gemini API 건너뜀")
            return None
        except Exception as e:
            logger.error(f"[SmartDetector] Gemini API 오류: {e}")
            return None

    @staticmethod
    def _make_result(company: str, confidence: str, matched_cols: list, reason: str) -> dict:
        return {
            "company":      company,
            "confidence":   confidence,  # 'high' | 'medium' | 'low'
            "matched_cols": matched_cols,
            "reason":       reason,
        }
