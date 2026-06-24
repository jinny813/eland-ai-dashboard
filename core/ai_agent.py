import os
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
현장 판매직원(매니저)과 층장이 오늘 당장 실행할 수 있는 매출 증대 진단 리포트를 작성하라.

【최우선 원칙 — 반드시 지킬 것】
1. 데이터 확인 후 작성: 각 비교군(B~F)을 사용하기 전, 해당 값이 "(데이터 없음)"인지 확인.
   - 없는 비교군이 있으면 해당 섹션 첫 줄에 반드시 명시: "⚠️ [전년 동월 / 전월 / 1등 매장 / NC브랜드 / NC카테고리] 데이터 없음 — 가용 데이터만으로 분석"
   - 없는 데이터는 절대 추정하거나 언급하지 말고, 있는 데이터만으로 최대한 깊이 분석.
2. 실제 수치 필수 인용: 금액(원), 비율(%), 건수, 증감(%p) 등 A~F 데이터에서 수치를 직접 꺼내 인용.
3. 추상적 표현 절대 금지: "개선 필요", "노력하십시오" 같은 문구 사용 금지. 복종명·가격대·수량·위치를 직접 지명하는 구체적 액션만 작성.
4. 한국어 작성.

[분석 대상] 브랜드: {brand_name} | 기준 점수: {scores_txt}

[A. 본 매장 현재 월 실데이터 — 항상 존재]
{data_summary_txt}

[B. 전월 본 매장 데이터 — 없으면 "(데이터 없음)"]
{past_summary_txt}

[C. 동일 브랜드 1등(BP) 매장 데이터 — 없으면 "(데이터 없음)"]
{bp_summary_txt}

[D. 동일 브랜드 NC 전체 평균 — 없으면 "(데이터 없음)"]
{nc_brand_txt}

[E. 여성 카테고리 NC 전체 평균 — 없으면 "(데이터 없음)"]
{nc_category_txt}

[F. 본 매장 전년 동월 실적 — 없으면 "(데이터 없음)"]
{past_yr_txt}

---

【섹션1: 📌 구색 진단 — 할인율·신선도·시즌·베스트 5개 관점 비교】
없는 비교군은 첫 줄에 명시 후 건너뛰고, 있는 비교군만으로 수치 기반 정밀 진단하라.

① F(전년 동월 본 매장) 대비:
   - 할인율 구간별(정상/30%/50%/70%) 비중 변화를 %p 단위로 서술
   - 신선도(신상·기획 비중) 및 시즌 구성 개선·악화 여부 수치로 증명
   - 베스트 재고 보유율 변화

② B(전월 본 매장) 대비:
   - 이번 달 할인율·신선도·시즌·베스트 각 지표가 전월보다 개선됐는지 퇴보했는지 수치로 비교
   - 가장 크게 변화한 지표 1~2개를 이유와 함께 지목

③ D(동일 브랜드 NC 전체 평균) 대비:
   - 이 매장이 브랜드 평균보다 뒤처지는 항목을 격차 큰 순서로 나열하고 수치(%p 차이) 제시
   - 브랜드 평균보다 앞서는 항목도 수치로 제시(강점 파악)

④ C(동일 브랜드 1등 BP 매장) 대비:
   - 할인율·신선도·시즌·베스트 각 항목의 격차를 수치로 제시
   - 4개 항목 중 격차가 가장 큰 것 1위를 "즉시 개선 최우선 과제"로 지목

⑤ E(여성 카테고리 NC 전체 평균) 대비:
   - 카테고리 평균 대비 이 브랜드의 구색 강점과 취약 포인트 수치로 분석
   - 카테고리 내 이 브랜드 포지션 평가

【섹션2: 🧥 세부 아이템 진단 — 복종별 5개 관점 비교 및 팔아야 할 것·확보해야 할 것 지목】
A 데이터에 있는 복종(아이템)별로 아래 5개 관점을 비교 진단하라. 없는 비교군은 건너뛰되 첫 줄에 명시.

각 복종마다:
- A 데이터에서 현재 재고금액·수량·할인율 비중 수치 인용
① F(전년 동월) 대비: 이 복종의 재고 구성·수량 변화
② B(전월) 대비: 이 복종의 할인율·신선도·시즌·베스트 지표 변화
③ D(NC 브랜드 전체) 대비: "○○ 복종 현재고 ○만원 — NC 평균(○만원)의 ○% 수준" 형식으로 표현
④ C(1등 BP 매장) 대비: 결품 또는 과다 여부 — "1등 매장 ○개 보유 / 본 매장 ○개 → 즉각 입고 요청" 또는 "과다 재고 ○만원 → 집중 판매 필요"
⑤ E(NC 카테고리) 대비: 카테고리 내 이 복종 포지션

복종 진단 종합:
- 【지금 팔아야 할 것】: 재고 많고 회전 저조한 복종명 직접 지목 + 수치 근거 + 구체적 판매 액션
- 【즉각 추가 확보해야 할 것】: 결품·부족 복종명 직접 지목 + "○개 / ○만원어치 추가 입고 본사 요청" 수준으로 구체화

【섹션3: 💰 가격 진단 — 아이템별 잘 팔리는 가격대·악성 재고 가격대 분석】
A 데이터에서 복종별 가격대별 재고·판매 현황을 분석하라. C가 없으면 A 데이터만으로 분석 후 명시.

각 복종마다:
- 가장 잘 팔리는 가격대와 재고만 쌓인 가격대를 원 단위로 제시
- C(1등 매장) 있을 때: "1등 매장은 ○만원대에 집중인데 본 매장은 ○만원대 재고가 ○%로 주를 이룸" 형식으로 비교
- 악성 재고 가격대 상품의 즉각 실행 전략(추가 할인율·이관·기획 판매 등)을 수치 근거와 함께 제시

【섹션4: 🚀 종합 결론 — 층장·매니저 즉시 실행 액션 플랜 (우선순위 순 6가지 이상)】
층장과 매장 매니저가 내일 출근해서 바로 실행할 수 있는 액션 6가지 이상을 우선순위 순으로 작성하라.

각 액션 형식:
[우선순위N] (담당: 층장/매니저/공동) 액션 내용
→ 수치 근거: 왜 지금 해야 하는지 데이터로 증명
→ 기대 효과: 매출·회전율에 어떤 영향 예상

반드시 포함할 항목:
- VMD 연출 변경 대상(복종명·상품명·매장 내 구체적 위치 지정)
- 본사에 즉각 요청해야 할 물량(복종·수량·이유 구체화)
- 집중 판매 할인율 구간·상품군 지정
- 층장이 점장·본사에 보고해야 할 핵심 이슈 1~2가지
- 향후 2주 집중 모니터링 지표

[출력 규칙 — 절대 준수]
1. 반드시 아래 JSON 형식으로만 출력. 다른 텍스트 일절 금지.
2. JSON 문자열 값 안에 실제 줄바꿈(엔터) 절대 금지. 줄바꿈은 반드시 <br> 태그만 사용.
3. 마크다운 코드블록(```json) 절대 금지.
4. 각 섹션 최대한 길고 구체적으로 작성. 요약·생략 금지.

{{"actions":["📌 [구색 진단] <br>여기에 섹션1 내용","🧥 [세부 아이템 진단] <br>여기에 섹션2 내용","💰 [가격 진단] <br>여기에 섹션3 내용","🚀 [종합 결론: 층장/매니저 액션 플랜] <br>여기에 섹션4 내용"]}}"""
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

        # ── Gemini API 호출 (429 지수 백오프 + 모델 폴백) ──
        try:
            MODELS = [
                "gemini-2.0-flash",   # 안정적, 우선 시도
                "gemini-2.5-flash",   # 차선
            ]
            base_url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
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
            req_data = json.dumps(payload).encode('utf-8')

            q = queue.Queue()

            def _api_call():
                for model in MODELS:
                    url = base_url.format(model=model, key=self.api_key)
                    retries = 3
                    for attempt in range(retries + 1):
                        try:
                            req = urllib.request.Request(
                                url, data=req_data,
                                headers={"Content-Type": "application/json"},
                                method="POST"
                            )
                            with urllib.request.urlopen(req, timeout=90) as resp:
                                q.put(json.loads(resp.read().decode('utf-8')))
                                return
                        except urllib.error.HTTPError as e:
                            if e.code == 429 and attempt < retries:
                                # 429 지수 백오프: 15→30→60초
                                wait = 15.0 * (2 ** attempt)
                                logger.warning(f"[{model}] 429 Rate Limit. {wait}s 대기 후 재시도 ({attempt+1}/{retries})")
                                time.sleep(wait)
                                continue
                            # 404·429(최종)·500·503 → 다음 모델로 전환
                            logger.warning(f"[{model}] HTTP {e.code} — 다음 모델로 전환")
                            break
                        except Exception as ex:
                            if attempt < retries:
                                time.sleep(5.0)
                                continue
                            logger.warning(f"[{model}] 오류: {ex} — 다음 모델로 전환")
                            break
                q.put(Exception("모든 모델(gemini-2.0/2.5-flash) 호출 실패"))

            t = threading.Thread(target=_api_call)
            t.daemon = True
            t.start()
            # 최대 6분 대기 (모델별 재시도 포함)
            t.join(360.0)

            if t.is_alive():
                raise TimeoutError("Gemini API 통신 지연 (360초 초과)")

            try:
                res = q.get_nowait()
            except queue.Empty:
                raise TimeoutError("Gemini API 응답 없음")

            if isinstance(res, Exception):
                raise res

            candidates = res.get("candidates", [])
            if not candidates:
                finish = res.get("promptFeedback", {}).get("blockReason", "unknown")
                raise ValueError(f"No candidates returned. blockReason: {finish}")

            text_resp = candidates[0]["content"]["parts"][0]["text"].strip()
            result = json.loads(text_resp)
            if "actions" in result and isinstance(result["actions"], list):
                result["actions"] = [str(a).replace('\\n', '<br>').replace('\n', '<br>') for a in result["actions"]]
                return result
            raise ValueError("JSON에 'actions' 키 없음")

        except Exception as e:
            logger.error(f"Gemini API 진단 생성 실패: {e}")
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
