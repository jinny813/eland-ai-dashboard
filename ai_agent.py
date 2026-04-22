"""
ai_agent.py — LLM 기반 상품구색 진단 에이전트
================================================
주신 25년 4월 매출 데이터를 목표액으로 설정하여
Claude API가 목표 달성 관점에서 리포트를 생성합니다.
"""

import os
import json
import sys
import time
import requests
from dotenv import load_dotenv

# [v100.1] Windows 콘솔 인코딩 대응: stdout/stderr를 UTF-8로 설정
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 환경변수 로드
load_dotenv()

# 1. 주신 데이터를 바탕으로 한 브랜드별 매출 목표 (단위: 원)
TARGET_REVENUE = {
    '인동팩토리': 36262600,
    '미샤팩토리': 42170750,
    '로엠': 20430250,
    '미쏘': 37203550,
    '베네통': 63001500,
    '시슬리': 33422800,
    'JJ지고트': 44160580,
    '나이스클랍': 18920490,
    '바바팩토리': 45415800
}

class AIAgent:
    """
    Gemini API를 호출해 상품구색 진단 리포트를 생성하는 에이전트.
    """

    MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    # ──────────────────────────────────────────
    # 메인: 진단 리포트 생성
    # ──────────────────────────────────────────
    def generate_report(
        self,
        brand_name: str,
        scores: dict,
        data_summary: dict,
        bp_summary: dict,
        indicator_id: str = None,
    ) -> dict:
        
        # 2. 브랜드명에서 '신구로점' 등을 제외하고 순수 브랜드명만 추출하여 목표액 매칭
        # (예: "로엠신구로점"으로 들어와도 "로엠"을 찾을 수 있게 처리)
        target_revenue = 0
        for key in TARGET_REVENUE:
            if key in brand_name:
                target_revenue = TARGET_REVENUE[key]
                break

        if not self.api_key:
            return self._fallback(brand_name, scores, indicator_id)

        # 프롬프트 생성 시 정확한 목표액 전달
        prompt = self._build_prompt(brand_name, target_revenue, scores, data_summary, bp_summary, indicator_id)

        try:
            result = self._call_gemini(prompt)
            return self._parse_response(result)
        except Exception as e:
            # [v100.1] 인코딩 오류 방지를 위해 에러 메시지를 repr()로 안전하게 출력
            print(f"[AIAgent] API 호출 실패 (fallback 사용): {repr(e)}")
            return self._fallback(brand_name, scores, indicator_id)

    # ──────────────────────────────────────────
    # 프롬프트 구성
    # ──────────────────────────────────────────
    def _build_prompt(
        self,
        brand_name: str,
        target_revenue: int,
        scores: dict,
        data_summary: dict,
        bp_summary: dict,
        indicator_id: str,
    ) -> str:
        ind_filter = ""
        if indicator_id:
            ind_map = {
                "item":   "아이템 구성 비중",
                "dis":    "할인율 구조",
                "fresh":  "신선도(신상 비중)",
                "best":   "BEST 상품 재고 비중",
                "season": "시즌 재고 비중",
            }
            ind_filter = f"\n특히 [{ind_map.get(indicator_id, indicator_id)}] 지표에 집중해서 분석하세요."

        # 목표액 천단위 콤마 표시
        revenue_str = format(target_revenue, ',') if target_revenue > 0 else "미설정"

        return f"""당신은 이랜드 아울렛 상품구색 전문 AI 진단 에이전트입니다.
아래 데이터를 바탕으로 실무자가 바로 실행할 수 있는 진단 리포트를 작성하세요.
{ind_filter}

## 브랜드: {brand_name}
## 25년 4월 목표 매출: {revenue_str}원 
(이 목표 금액 달성을 위한 상품 구색 최적화 관점에서 분석하고 액션 플랜을 제시하세요.)

## 5개 지표 점수 (0~100점)
- 아이템 점수: {scores.get('item', 0)}점
- 할인율 점수: {scores.get('dis', 0)}점
- 신선도 점수: {scores.get('fresh', 0)}점
- BEST 점수:   {scores.get('best', 0)}점
- 시즌 점수:   {scores.get('season', 0)}점
- 최종 점수:   {scores.get('total', 0)}점

## 세부 비중 데이터 (해당 브랜드)
{json.dumps(data_summary, ensure_ascii=False, indent=2)}

## 벤치마크(BP) 매장 세부 비중 데이터 (평매출 1위 기준)
{json.dumps(bp_summary, ensure_ascii=False, indent=2)}

## 진단 작성 가이드
1. 전반적 진단이 아닌, 요청받은 **해당 지표에 대한 분석**에만 엄격하게 집중하세요.
2. BP 매장과의 수치를 비교하여, 구체적으로 **어떤 상품 비중이 부족하여 추가해야 하는지**, **어떤 상품이 과다하여 제거/할인 소진해야 하는지** 짚어주세요.
3. 결과적으로 목표 매출을 올리기 위해 **무엇을 어떻게 팔아야 하는지(매출 증대 체감 액션)**에 대한 제안을 포함하세요.
4. 구구절절한 설명은 빼고, 가독성을 극대화하기 위해 반드시 ⚠️ 이모지를 포함하여 1~2줄 이내의 아주 짧은 개조식 문장(결론/액션 위주)으로만 반환하세요.

## 출력 형식 (JSON만 출력)
{{
  "actions": [
    "⚠️ 70%+ 할인 비중이 BP 매장 대비 14%p 높습니다.",
    "⚠️ 정상가 상품 비중이 BP 매장 대비 낮습니다. 신상 입고가 필요합니다."
  ]
}}"""

    def _call_gemini(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        max_retries = 3
        timeout = 60  # [v100.2] 타임아웃 대폭 연장 (60초)

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                attempt_num = attempt + 1
                if attempt_num < max_retries:
                    print(f"[AIAgent] API 호출 시도 {attempt_num} 실패: {repr(e)}. 2초 후 재시도...")
                    time.sleep(2)
                else:
                    raise e

    def _parse_response(self, text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}") + 1
        parsed = json.loads(text[start:end])
        return {
            "core_title": parsed.get("core_title", "진단 결과"),
            "core_body": parsed.get("core_body", ""),
            "actions": parsed.get("actions", []),
        }

    def _fallback(self, brand_name: str, scores: dict, indicator_id: str) -> dict:
        return {
            "core_title": f"{brand_name} 진단 준비 중",
            "core_body": "API 연결을 확인 중입니다. 목표 매출 데이터를 기반으로 분석을 곧 시작합니다.",
            "actions": ["네트워크 상태 확인", "API 키 유효성 점검"]
        }

    def generate_all(self, brand_name, scores, data_summary, bp_summary):
        results = {}
        for ind_id in ["item", "dis", "fresh", "best", "season"]:
            results[ind_id] = self.generate_report(brand_name, scores, data_summary, bp_summary, ind_id)
        return results
        