import os
import re
import json
import urllib.request
import logging
import threading
import queue
import time

logger = logging.getLogger(__name__)

class AIAgent:
    """
    Gemini API를 호출하여 데이터 기반 정성적 진단 리포트를 생성하는 MD 에이전트.
    """

    def __init__(self, api_key: str = None):
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY", "")

        if not api_key:
            try:
                import streamlit as st
                if "GEMINI_API_KEY" in st.secrets:
                    api_key = st.secrets["GEMINI_API_KEY"]
            except Exception:
                pass

        if not api_key:
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
        if not self.api_key:
            logger.error("GEMINI_API_KEY is missing.")
            return self._fallback_report(brand_name, indicator_id, "API 키 누락")

        indicator_name = {
            "dis": "할인율 구색",
            "fresh": "신선도(신상/기획) 구색",
            "season": "시즌(계절) 구색",
            "best": "BEST 10 인기상품 재고",
            "comprehensive": "종합 진단"
        }.get(indicator_id, indicator_id)

        past_summary = bp_summary.pop("__past_summary", {}) if bp_summary else {}
        nc_brand_summary = bp_summary.pop("__nc_brand_summary", None) if bp_summary else None
        nc_category_summary = bp_summary.pop("__nc_category_summary", None) if bp_summary else None
        past_yr_summary = bp_summary.pop("__past_yr_summary", None) if bp_summary else None

        def minify_summary(summary):
            if not isinstance(summary, dict): return summary
            minified = {}
            for k, v in summary.items():
                if k == "best" and isinstance(v, dict):
                    min_v = v.copy()
                    if "store" in min_v and isinstance(min_v["store"], list): min_v["store"] = min_v["store"][:10]
                    if "all" in min_v and isinstance(min_v["all"], list): min_v["all"] = min_v["all"][:10]
                    minified[k] = min_v
                else:
                    minified[k] = v
            return minified

        scores_txt = json.dumps(scores, ensure_ascii=False, separators=(',', ':'))
        data_summary_txt = json.dumps(minify_summary(data_summary), ensure_ascii=False, separators=(',', ':'))
        bp_summary_txt = json.dumps(minify_summary(bp_summary), ensure_ascii=False, separators=(',', ':')) if bp_summary else "{}"
        past_summary_txt = json.dumps(minify_summary(past_summary), ensure_ascii=False, separators=(',', ':')) if past_summary else "(데이터 없음)"
        nc_brand_txt = json.dumps(nc_brand_summary, ensure_ascii=False) if nc_brand_summary else "(데이터 없음)"
        nc_category_txt = json.dumps(nc_category_summary, ensure_ascii=False) if nc_category_summary else "(데이터 없음)"
        past_yr_txt = json.dumps(past_yr_summary, ensure_ascii=False) if past_yr_summary else "(데이터 없음)"

        if indicator_id == "comprehensive":
            prompt = f"""너는 10년차 경영컨설턴트이자 패션 리테일 전문 데이터 분석가다. 
주어진 실제 데이터를 바탕으로 현장 판매직원(매니저)과 층장에게 실질적인 매출 증대 지침이 될 수 있는 전문 분석 리포트를 작성하라.
- 반드시 데이터에 있는 실제 수치(금액, 비율, 건수)를 직접 인용해 분석할 것.
- "데이터 없음"으로 표시된 비교군(전년, 전월, 1등 매장 등)이 있다면 첫 문장에 "ㅇㅇ 데이터가 없어 현재 가용한 데이터만으로 분석했습니다"라고 명시하고, 나머지 있는 데이터로 최대한 깊이 있게 분석할 것.
- 추상적 표현("개선 필요", "노력하십시오") 절대 금지. 현장에서 바로 실행할 수 있는 액션 위주로 작성.
- 한국어로 작성.

[분석 대상] 브랜드: {brand_name} | 기준 점수: {scores_txt}

[A. 본 매장 현재 월 실데이터]
{data_summary_txt}

[B. 전월 본 매장 데이터]
{past_summary_txt}

[C. 1등(BP) 매장 데이터]
{bp_summary_txt}

[D. 동일 브랜드 NC 전체 평균]
{nc_brand_txt}

[E. 여성 카테고리 NC 전체 평균]
{nc_category_txt}

[F. 본 매장 전년 동월 실적]
{past_yr_txt}

[작성 지침 - 아래 4개 섹션 각각 최대한 구체적인 수치와 인사이트를 담아 길게 작성]

섹션1 구색 진단: 할인율/신선도/시즌/베스트 세부 진단
- A 데이터를 바탕으로 전년 본 매장(F), 전월 본 매장(B), 동일 브랜드 NC 전체(D), 1등 매장(C), 카테고리 전체(E)와 비교하여 현재 구색의 밸런스(할인율 분포, 신선도, 시즌 비중, 베스트 상품 비중)를 정밀 진단.

섹션2 세부 아이템 진단: 아이템별 할인율/신선도/시즌/베스트 세부 진단
- A 데이터의 아이템(복종)별로 전년(F), 전월(B), NC전체(D), 1등매장(C), 카테고리(E)와 비교 진단.
- 1등 매장 및 타 지점과 비교해 결품된 핵심 복종이 무엇인지, 재고가 과다한 복종이 무엇인지 수치로 증명.
- 현장 직원을 위해 "어떤 세부 아이템을 집중적으로 팔아야 하고, 어떤 아이템 물량을 더 확보해야 하는지" 명확히 지목.

섹션3 가격 진단: 아이템별 잘 팔리는 가격대 진단
- A 데이터에서 아이템별 주력 판매 가격대 분포를 실제 수치로 분석.
- 잘 팔리는 가격대 vs 재고만 쌓인 가격대를 비교하고, 1등 매장(C) 대비 가격대 포지셔닝 차이를 분석.

섹션4 종합 결론: 층장 및 본 매장 매니저 매출 증대 액션 플랜
- 층장과 매장 매니저가 당장 내일 출근해서 매출을 올리기 위해 실행해야 할 구체적인 액션 아이템 5가지 이상 (우선순위순).
- VMD 연출 변경 대상 상품, 본사 즉각 요청 물량, 집중 푸시할 할인율 구간 등 현장 친화적 지침 제공.

[출력 규칙 - 절대 준수]
1. 반드시 아래 JSON 형식으로만 출력해라. 다른 텍스트 일절 금지.
2. JSON 문자열 값 안에 실제 줄바꿈(엔터) 절대 금지. 줄바꿈은 반드시 <br> 태그만 사용.
3. 마크다운 코드블록(```json) 절대 금지.
4. 각 섹션 최대한 길고 구체적으로 작성. 요약 금지.

{{"actions":["📌 [구색 진단] <br>여기에 섹션1 내용 작성","🧥 [세부 아이템 진단] <br>여기에 섹션2 내용 작성","💰 [가격 진단] <br>여기에 섹션3 내용 작성","🚀 [종합 결론: 층장/매니저 액션 플랜] <br>여기에 섹션4 내용 작성"]}}"""
        else:
            prompt = f"""너는 패션 의류 매장의 MD Assortment AI 분석가다. 아래 데이터를 정밀 비교 분석하여 현재 이 매장의 '{indicator_name}' 상태를 진단하고 즉각 취할 행동 가이드를 도출해라.

[브랜드: {brand_name} | 지표: {indicator_name}]
[점수] {scores_txt}
[본 매장 현재 월] {data_summary_txt}
[전월] {past_summary_txt}
[1등 매장] {bp_summary_txt}

[도출 규칙]
1. '{indicator_name}'에 집중하여 구체적 조치 사항 3개 이상 제시.
2. BP 대비 수치 차이, 전월 대비 증감율을 근거로 활용.
3. 추상적 문구 절대 금지. 실제 수치 인용 필수.
4. 한국어로 작성.

[출력 규칙] 순수 JSON만 출력. 마크다운 블록 금지. JSON 문자열 안 실제 줄바꿈 금지(<br> 사용).

{{"actions":["조치 사항 1 (수치 근거 포함)","조치 사항 2 (수치 근거 포함)","조치 사항 3 (수치 근거 포함)"]}}"""

        # ── Gemini 2.5 Flash API 호출 ──
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 8000,
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "actions": {
                            "type": "ARRAY",
                            "items": { "type": "STRING" }
                        }
                    },
                    "required": ["actions"]
                }
            }
        }

        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            q = queue.Queue()

            def _api_call():
                retries = 3
                for attempt in range(retries + 1):
                    try:
                        with urllib.request.urlopen(req, timeout=60) as resp:
                            q.put(json.loads(resp.read().decode('utf-8')))
                            return
                    except urllib.error.HTTPError as e:
                        if e.code in [503, 500, 429] and attempt < retries:
                            # 429(Too Many Requests)일 경우 넉넉하게 10초 이상 대기 (지수 백오프)
                            sleep_time = 5.0 * (attempt + 1) if e.code == 429 else 3.0
                            logger.warning(f"Gemini API {e.code} Error. Retrying in {sleep_time}s... (Attempt {attempt+1}/{retries})")
                            time.sleep(sleep_time)
                            continue
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
            t.join(70.0)  # 8000토큰 응답 대기용 70초 타임아웃

            if t.is_alive():
                raise TimeoutError("Gemini API 통신 지연 (70초 초과)")

            res = q.get()
            if isinstance(res, Exception):
                raise res

            candidates = res.get("candidates", [])
            if not candidates:
                finish = res.get("promptFeedback", {}).get("blockReason", "unknown")
                raise ValueError(f"No candidates returned. blockReason: {finish}")

            text_resp = candidates[0]["content"]["parts"][0]["text"].strip()

            # responseSchema를 통해 완벽한 JSON 포맷이 보장되므로, 정규식 전처리 없이 바로 파싱
            result = json.loads(text_resp)
            if "actions" in result and isinstance(result["actions"], list):
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
                f"[{brand_name}] 시즌 지표에 근거하여, 다가오는 계절의 전략 상품군 입고율을 목표 비중 수준으로 끌어올리십시오.",
                "날씨 변화에 민감한 얇은 아우터 및 원피스 아이템의 마네킹 피팅을 현시즌 테마에 맞춰 교체하십시오.",
                "지난 계절 재고의 아울렛 매장 이관 및 반품 일정을 단축하여 매장 내 효율 면적을 확보하십시오."
            ],
            "best": [
                f"[{brand_name}] 매장의 자사 BEST 10 인기 상품의 현재고를 모니터링하여 품절 임박(재고 5개 이하) 건에 대해 추가 입고를 즉시 실행하십시오.",
                "1등 매장 대비 미보유 중인 전사 베스트 상품이 있는 경우, 즉각 본사 배분을 요청하십시오.",
                "재고가 충분한 베스트셀러 상품은 매장 입구 및 메인 VP 존에 집중 연출하여 판매 회전율을 극대화하십시오."
            ],
            "comprehensive": [
                f"📌 [구색 진단] <br>[{brand_name}] NC 전체 및 1등 매장(BP) 대비 현재고 분포(할인율, 신선도, 시즌)를 확인하여 전반적인 밸런스를 조정하십시오.",
                "🧥 [세부 아이템 진단] <br>1등 매장에서 잘 팔리는 주력 아이템 중 자사 매장에 결품된 상품의 긴급 물량을 본사에 요청하십시오.",
                "💰 [가격 진단] <br>잘 팔리는 주력 가격대의 상품이 결품되지 않도록 지속 모니터링하고, 악성 재고는 추가 할인을 검토하십시오.",
                "🚀 [종합 결론: 층장/매니저 액션 플랜] <br>현재 보유 중인 BEST 아이템임에도 판매가 저조한 상품은 매장 내 전면 VP 연출 및 마네킹 피팅을 통해 즉각적인 소진을 유도하십시오."
            ]
        }
        actions = fallback_actions.get(indicator_id, [
            f"[{brand_name}] 매장의 {indicator_id} 구색 현황을 분석하고 목표 대비 과부족 재고액을 조정하십시오.",
            "1등 매장의 상품 구색 구성을 벤치마킹하여 미입고 품목군의 매장 전개 방안을 수립하십시오."
        ])
        return {
            "actions": [f"{a} (⚠️ AI 진단 엔진 폴백 가이드 적용 - 원인: {error_msg})" for a in actions]
        }
