class AIAgent:
    """
    LLM(OpenAI/Claude 등) API를 호출하여 정성적 진단 리포트를 생성하는 점수 기반 에이전트.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        # TODO: LLM 연동 설정 (모델 선택, 프롬프트 템플릿 준비 등)

    def generate_report(self, brand_name: str, scores: dict, data_summary: dict) -> str:
        """
        계산된 점수와 데이터 요약(ex: 신상품 재고량 부족)을 바탕으로
        해결 방안이 포함된 상품구색 진단 리포트를 작성합니다.
        """
        # TODO: 프롬프트 구성 및 LLM 호출 로직 구현

        # 임시 리포트 반환
        return f"{brand_name} 매장의 종합 점수는 {scores.get('total', 0)}점 입니다.\n세부 진단 내역이 곧 구현될 예정입니다."
