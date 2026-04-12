"""
ai_agent.py — LLM 기반 상품구색 진단 에이전트
================================================
주신 25년 4월 매출 데이터를 목표액으로 설정하여
Claude API가 목표 달성 관점에서 리포트를 생성합니다.
"""

import os
import json
import urllib.request
import urllib.error

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
    Claude API를 호출해 상품구색 진단 리포트를 생성하는 에이전트.
    """

    MODEL = "claude-3-5-sonnet-20240620"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    # ──────────────────────────────────────────
    # 메인: 진단 리포트 생성
    # ──────────────────────────────────────────
    def generate_report(
        self,
        brand_name: str,
        scores: dict,
        data_summary: dict,
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
        prompt = self._build_prompt(brand_name, target_revenue, scores, data_summary, indicator_id)

        try:
            result = self._call_claude(prompt)
            return self._parse_response(result)
        except Exception as e:
            print(f"[AIAgent] API 호출 실패 — fallback 사용: {e}")
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

## 세부 비중 데이터
{json.dumps(data_summary, ensure_ascii=False, indent=2)}

## 출력 형식 (JSON만 출력)
{{
  "core_title": "핵심 문제 요약 (20자 이내)",
  "core_body": "목표 매출 달성을 위한 현재 구색의 문제점과 해결 방향 진단",
  "actions": [
    "즉시 실행 액션 1 (구체적)",
    "즉시 실행 액션 2 (구체적)",
    "즉시 실행 액션 3 (구체적)"
  ]
}}"""

    def _call_claude(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        req = urllib.request.Request(
            self.API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]

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

    def generate_all(self, brand_name, scores, data_summary):
        results = {}
        for ind_id in ["item", "dis", "fresh", "best", "season"]:
            results[ind_id] = self.generate_report(brand_name, scores, data_summary, ind_id)
        return results
        