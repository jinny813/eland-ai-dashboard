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
            # 2. st.secrets 조회 (Streamlit Cloud 대응)
            try:
                import streamlit as st
                if "GEMINI_API_KEY" in st.secrets:
                    api_key = st.secrets["GEMINI_API_KEY"]
            except Exception:
                pass
                
        if not api_key:
            # 3. .env 파일 직접 파싱 폴백
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
            "best": "BEST 10 인기상품 재고",
            "comprehensive": "NC전체 및 1등 매장 대비 종합 진단 (상품/시즌/가격/신선도/할인율)"
        }.get(indicator_id, indicator_id)

        past_summary = bp_summary.pop("__past_summary", {}) if bp_summary else {}

        # ── 프롬프트 조립 ──
        def minify_summary(summary):
            if not isinstance(summary, dict): return summary
            minified = {}
            for k, v in summary.items():
                if k == "best" and isinstance(v, dict):
                    min_v = v.copy()
                    if "store" in min_v and isinstance(min_v["store"], list): min_v["store"] = min_v["store"][:10]
                    if "all" in min_v and isinstance(min_v["all"], list): min_v["all"] = min_v["all"][:10]
                    minified[k] = min_v
                elif k == "item" and isinstance(v, dict) and "segs" in v and isinstance(v["segs"], list):
                    min_v = v.copy()
                    # Preserve item segs so AI can cross-compare them
                    minified[k] = min_v
                else:
                    minified[k] = v
            return minified

        scores_txt = json.dumps(scores, ensure_ascii=False, separators=(',', ':'))
        data_summary_txt = json.dumps(minify_summary(data_summary), ensure_ascii=False, separators=(',', ':'))
        bp_summary_txt = json.dumps(minify_summary(bp_summary), ensure_ascii=False, separators=(',', ':')) if bp_summary else "{}"
        past_summary_txt = json.dumps(minify_summary(past_summary), ensure_ascii=False, separators=(',', ':')) if past_summary else "{}"

        if indicator_id == "comprehensive":
            prompt = f"""
너는 NC백화점 패션 의류 매장의 수석 MD 및 AI 진단 전문가이다.
아래 자사 매장의 데이터와 다차원 비교 데이터(전월, 1등 매장, NC전체 평균 등)를 심층 분석하여, 매우 구체적이고 실전적인 종합 진단 리포트를 작성해라.

[분석 대상 매장 정보]
- 브랜드: {brand_name}
- 평가 지표: 종합 구색 및 세부 현황 진단

[현재 지점 점수 (100점 만점 기준)]
{scores_txt}

[본 지점의 현재 월 세부 요약]
{data_summary_txt}

[비교군 1: 본 지점의 직전 월(지난달) 세부 요약 - 추이 파악용]
{past_summary_txt}

[비교군 2: 1등(BP) 지점의 세부 요약 - 벤치마킹용]
{bp_summary_txt}

[비교군 3: 동일 브랜드 NC 전체 평균 요약]
{bp_summary.get('__nc_brand_summary', '데이터 없음')}

[비교군 4: 여성 카테고리 NC 전체 평균 요약]
{bp_summary.get('__nc_category_summary', '데이터 없음')}

[비교군 5: 본 지점 전년도 매출 실적 요약]
{bp_summary.get('__past_yr_summary', '데이터 없음')}

[진단 필수 포함 사항 - 반드시 4개의 섹션으로 나누어 JSON 배열에 담을 것]
0. 데이터 결측치 처리: 만약 특정 비교군(전월, 전년, 1등 매장, 카테고리 평균 등)이 '데이터 없음'이거나 비어 있다면, 결과의 첫 부분에 "ㅇㅇ 데이터가 부족하여 보유 데이터 기반으로 분석했습니다."라고 명시하고 있는 데이터만으로 분석해라.
1. 구색 진단: 전체적인 할인율/신선도/시즌/베스트 분포를 전월, NC전체, 1등매장, 여성카테고리 전체와 비교하여 진단.
2. 세부 아이템 진단: 주요 복종(아우터, 상의 등)별로 재고/판매 비중, 신선도, 시즌, 베스트 상품 현황을 타 매장(1등매장, NC전체)과 정밀 비교. (예: "아우터의 경우 1등 매장 대비 할인폭이 큰 상품이 결품됨")
3. 가격 진단: 아이템별로 현재 잘 팔리는 주력 가격대(Price Point)를 진단하고 가격 저항선 분석.
4. 종합 결론: 층장과 본 매장 매니저가 당장 내일 매출을 올리기 위해 실행해야 할 구체적인 액션 아이템(VMD 연출, 본사 물량 요청, 가격 인하 등). 추상적인 말 금지.

[출력 형식 제한 (매우 중요)]
- 반드시 아래 JSON 스키마를 따르는 순수 JSON 객체 1개만 반환해라.
- JSON 내부의 문자열 값 안에는 **절대 실제 줄바꿈(엔터)을 넣지 마라**. 줄바꿈이 필요하면 `<br>` 태그를 대신 사용해라.
- 마크다운 블록(```json 등)도 쓰지 말고 순수 JSON만 출력해라.

{{
  "actions": [
    "📌 [구색 진단] <br>(상세 내용 작성...)",
    "🧥 [세부 아이템 진단] <br>(상세 내용 작성...)",
    "💰 [가격 진단] <br>(상세 내용 작성...)",
    "🚀 [종합 결론: 매니저/층장 액션 플랜] <br>(상세 내용 작성...)"
  ]
}}
"""
        else:
            prompt = f"""
너는 패션 의류 매장의 MD Assortment AI 분석가이다.
아래 자사 매장의 실시간 재고/판매 데이터와 NC 전체 데이터(1등 매장 및 평균)를 정밀 비교 분석하여, 현재 이 매장의 '{indicator_name}' 상태를 진단하고 매니저가 즉각 취해야 할 행동 가이드(Action Plan)를 도출해라.
특히 브랜드별 진단 관점에서 가격(할인율), 시즌, 상품(아이템), 소진율(Sell-through), 정판율 등을 종합적으로 고려할 것.

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
                "responseMimeType": "application/json",
                "maxOutputTokens": 1500
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
            import threading
            import queue
            import time
            
            q = queue.Queue()
            def _api_call():
                retries = 3
                for attempt in range(retries + 1):
                    try:
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            q.put(json.loads(resp.read().decode('utf-8')))
                            return
                    except urllib.error.HTTPError as e:
                        if e.code in [503, 500, 429] and attempt < retries:
                            time.sleep(3.0)
                            continue
                        else:
                            q.put(e)
                            return
                    except Exception as e:
                        if attempt < retries:
                            time.sleep(3.0)
                            continue
                        q.put(e)
                        return
            
            t = threading.Thread(target=_api_call)
            t.daemon = True
            t.start()
            t.join(40.0)  # 하드 타임아웃 40초로 대폭 상향
            
            if t.is_alive():
                raise TimeoutError("Gemini API 통신 지연 (40초 초과)")
                
            res = q.get()
            if isinstance(res, Exception):
                raise res
                
            resp_data = res
                
            # Response 파싱
            candidates = resp_data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates returned from Gemini API")
                
            text_resp = candidates[0]["content"]["parts"][0]["text"].strip()
            
            # ── Step 1: Markdown 백틱 블록 제거 ──
            text_resp = re.sub(r"^```json\s*", "", text_resp, flags=re.MULTILINE)
            text_resp = re.sub(r"^```\s*", "", text_resp, flags=re.MULTILINE)
            text_resp = re.sub(r"\s*```\s*$", "", text_resp, flags=re.MULTILINE)
            text_resp = text_resp.strip()
            
            # ── Step 2: JSON 블록만 추출 (앞뒤 불필요 텍스트 제거) ──
            start_idx = text_resp.find("{")
            end_idx = text_resp.rfind("}") + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON object found in response")
            text_resp = text_resp[start_idx:end_idx]
            
            # ── Step 3: JSON 문자열 내부의 실제 개행 → \n 이스케이프 처리 ──
            # Gemini가 JSON value 안에 실제 엔터를 넣을 때 Unterminated string 방지
            def escape_inner_newlines(m):
                return m.group(0).replace('\n', '\\n').replace('\r', '')
            text_resp = re.sub(
                r'(?s)"(.*?)"',  # JSON 문자열 값 내부
                escape_inner_newlines,
                text_resp
            )
            
            # ── Step 4: 파싱 ──
            result = json.loads(text_resp)
            if "actions" in result and isinstance(result["actions"], list):
                # \n → <br> 변환하여 UI에서 줄바꿈 표시
                result["actions"] = [str(a).replace('\\n', '<br>').replace('\n', '<br>') for a in result["actions"]]
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
            ],
            "comprehensive": [
                f"[{brand_name}] NC 전체 및 1등 매장(BP) 대비 현재고 분포(할인율, 신선도, 시즌)를 확인하여 전반적인 밸런스를 조정하십시오.",
                "1등 매장에서 잘 팔리는 주력 아이템(예: 고할인 아우터) 중 자사 매장에 결품된 상품의 긴급 물량을 본사에 요청하십시오.",
                "현재 보유 중인 BEST 아이템임에도 판매가 저조한 상품은 매장 내 전면 VP 연출 및 마네킹 피팅을 통해 즉각적인 소진을 유도하십시오."
            ]
        }
        actions = fallback_actions.get(indicator_id, [
            f"[{brand_name}] 매장의 {indicator_id} 구색 현황을 분석하고 목표 대비 과부족 재고액을 조정하십시오.",
            "1등 매장의 상품 구색 구성을 벤치마킹하여 미입고 품목군의 매장 전개 방안을 수립하십시오."
        ])
        return {
            "actions": [f"{a} (⚠️ AI 진단 엔진 폴백 가이드 적용 - 원인: {error_msg})" for a in actions]
        }
