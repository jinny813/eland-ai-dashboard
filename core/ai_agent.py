import os
import re
import json
import urllib.request
import urllib.parse
import logging

logger = logging.getLogger(__name__)

class AIAgent:
    """
    Gemini API를 호출하여 데이터 기반 정성적 진단 리포트를 생성하는 MD 에이전트.
    """

    def __init__(self, api_key: str = None):
        if not api_key:
            # 1. 환경변수 우선 조회
            api_key = os.environ.get("GEMINI_API_KEY", "")
            
        if not api_key:
            # 2. .env 파일 직접 파싱 폴백
            try:
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("GEMINI_API_KEY="):
                                api_key = line.strip().split("=", 1)[1].strip()
                                break
            except Exception as e:
                logger.warning(f"Failed to read .env for GEMINI_API_KEY: {e}")
                
        self.api_key = api_key

    def generate_report(self, brand_name: str, scores: dict, data_summary: dict, bp_summary: dict = None, indicator_id: str = "dis") -> dict:
        """
        계산된 점수와 데이터 요약(ex: 신상품 재고량 부족)을 바탕으로
        Gemini를 통해 해결 방안이 포함된 상품구색 진단 리포트를 작성합니다.
        """
        if not self.api_key:
            logger.error("GEMINI_API_KEY is missing. AI diagnosis cannot be generated.")
            return self._fallback_report(brand_name, indicator_id, "API 키 누락")

        indicator_name = {
            "dis": "할인율 구색",
            "fresh": "신선도(신상/기획) 구색",
            "season": "시즌(계절) 구색",
            "best": "BEST 10 인기상품 재고"
        }.get(indicator_id, indicator_id)

        past_summary = bp_summary.pop("__past_summary", {}) if bp_summary else {}

        # ── 프롬프트 조립 ──
        scores_txt = json.dumps(scores, ensure_ascii=False, indent=2)
        data_summary_txt = json.dumps(data_summary, ensure_ascii=False, indent=2)
        bp_summary_txt = json.dumps(bp_summary, ensure_ascii=False, indent=2) if bp_summary else "{}"
        past_summary_txt = json.dumps(past_summary, ensure_ascii=False, indent=2) if past_summary else "{}"

        prompt = f"""
너는 패션 의류 매장의 MD Assortment AI 분석가이다.
아래 매장의 실시간 재고 데이터, 지난달 판매추이, 그리고 1등 매장(BP) 데이터를 정밀 분석하여, 현재 이 매장의 '{indicator_name}' 상태를 진단하고 매장 매니저가 즉각 취해야 할 행동 가이드(Action Plan)를 도출해라.

[분석 대상 매장 정보]
- 브랜드: {brand_name}
- 평가 지표: {indicator_name}

[점수 현황]
{scores_txt}

[본 지점의 현재 월 세부 재고/판매 요약]
{data_summary_txt}

[본 지점의 직전 월(지난달) 세부 재고/판매 요약 - 판매 추이 파악용]
{past_summary_txt}

[1등(BP) 지점의 세부 재고/판매 요약 - 벤치마킹용]
{bp_summary_txt}

[행동 가이드 도출 규칙]
1. 분석 대상 지표인 '{indicator_name}'에 집중하여 구체적이고 실행 가능한 현장 조치 사항을 최소 3개 이상 제시할 것.
2. 타 매장(BP)과의 비중 차이, 혹은 지난달 대비 이번 달의 판매/재고 증감율을 근거로 활용할 것.
3. 구체적인 지침의 예시:
   - 과다 재고인 경우: '~~상품의 재고가 타 매장 대비 과도하므로, 매장 전면 배치 및 가격 인하(할인율 상향) 건의'
   - 부족 재고인 경우: '지난달 판매 속도(Sell-through)가 빠르나 현재고가 부족하므로 추가 물량 ~~장 확보 요청'
   - 밀어내기 필요: '재고는 충분하나 판매가 저조하므로 VMD 연출 변경 또는 층장 푸시 집중'
4. 추상적인 문구(예: '노력하십시오')는 절대 금지.
5. 반드시 한국어로 답변할 것.

출력은 반드시 다음 JSON 스키마를 따르는 JSON 데이터 형태여야 하며, 추가적인 설명 텍스트나 markdown 코드 블록(```json 등) 없이 순수 JSON만 반환해야 한다:
{{
  "actions": [
    "구체적인 조치 사항 1 (근거 및 목표 수치 포함)",
    "구체적인 조치 사항 2 (근거 및 목표 수치 포함)",
    "구체적인 조치 사항 3 (근거 및 목표 수치 포함)"
  ]
}}
"""
        
        # ── Gemini 2.5 Flash API 호출 ──
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                
            # Response 파싱
            candidates = resp_data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates returned from Gemini API")
                
            text_resp = candidates[0]["content"]["parts"][0]["text"].strip()
            
            # JSON 디코딩
            result = json.loads(text_resp)
            if "actions" in result and isinstance(result["actions"], list):
                return result
            else:
                raise ValueError("JSON does not contain 'actions' list")
                
        except Exception as e:
            logger.error(f"Gemini API diagnosis generation failed: {e}")
            return self._fallback_report(brand_name, indicator_id, str(e))

    def _fallback_report(self, brand_name: str, indicator_id: str, error_msg: str) -> dict:
        """AI 호출 실패 시 제공하는 기본 룰 기반 폴백 행동 지침"""
        fallback_actions = {
            "dis": [
                f"[{brand_name}] 매장의 할인율 재고 분포를 확인하십시오. 목표 비중 대비 결품 상태인 할인율 구간(예: 이월 50% 등)의 보충 물량을 검토하십시오.",
                "상설 매장의 경우 연차(year) 재고 비중을 확인하고 2년차 이상 이월 상품의 전면 배치를 조정하십시오.",
                "정상 매장의 경우 신상품(할인율 0%)의 비중을 70% 수준으로 회복하기 위해 추가 신상 입고를 기획하십시오."
            ],
            "fresh": [
                f"[{brand_name}] 신선도 점수 개선을 위해 매장 내 신상품 및 기획상품 진열 비율을 70:30으로 재배치하십시오.",
                "본사에 최근 2주 내 출시된 핵심 신규 아이템 공급 확대를 긴급 요청하십시오.",
                "판매가 저조한 캐리 오버(Carry Over) 상품군을 매장 후방 벽면 또는 행거 하단으로 이동하십시오."
            ],
            "season": [
                f"[{brand_name}] 시즌 지표에 근거하여, 다가오는 계절의 전략 상품군 입고율을 목표 비중(SS시즌 봄 50%, 여름 30%) 수준으로 끌어올리십시오.",
                "날씨 변화에 민감한 얇은 아우터 및 원피스 아이템의 마네킹 피팅을 현시즌 테마에 맞춰 교체하십시오.",
                "지난 계절 재고의 아울렛 매장 이관 및 반품 일정을 단축하여 매장 내 효율 면적을 확보하십시오."
            ],
            "best": [
                f"[{brand_name}] 매장의 자사 BEST 10 인기 상품의 현재고를 모니터링하여 품절 임박(재고 5개 이하) 건에 대해 추가 입고를 즉시 실행하십시오.",
                "1등 매장 대비 미보유 중인 전사 베스트 상품이 있는 경우, 즉각 본사 배분을 요청하십시오.",
                "재고가 충분한 베스트셀러 상품은 매장 입구 및 메인 VP 존에 집중 연출하여 판매 회전율을 극대화하십시오."
            ]
        }
        actions = fallback_actions.get(indicator_id, [
            f"[{brand_name}] 매장의 {indicator_id} 구색 현황을 분석하고 목표 대비 과부족 재고액을 조정하십시오.",
            "1등 매장의 상품 구색 구성을 벤치마킹하여 미입고 품목군의 매장 전개 방안을 수립하십시오."
        ])
        return {
            "actions": [f"{a} (⚠️ AI 진단 엔진 폴백 가이드 적용 - 원인: {error_msg})" for a in actions]
        }
