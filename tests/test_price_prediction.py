import unittest
from unittest.mock import patch, MagicMock
from core.price_predict_service import PricePredictService, Math_bound

class TestPricePredictService(unittest.TestCase):
    def setUp(self):
        self.service = PricePredictService(db_path="database/mock_product_master.db")

    def test_sanitize_string(self):
        """특수문자, HTML 태그, 대소문자 제거 정제 기능 테스트"""
        test_cases = [
            ("<b>Nike Air Max 97</b>", "nikeairmax97"),
            ("CV1234-100", "cv1234100"),
            ("  [뉴에라] 12345_ABC  ", "12345abc"),
            ("", ""),
            (None, "")
        ]
        for input_str, expected in test_cases:
            with self.subTest(input_str=input_str):
                self.assertEqual(self.service._sanitize_string(input_str), expected)

    def test_verify_match(self):
        """품번이 검색 상품 타이틀 내 포함되어 있는지 확인하는 매칭 검증 테스트"""
        # 1. 완벽 매칭
        self.assertTrue(self.service.verify_match("CV1234-100", "나이키 에어맥스 97 CV1234-100 화이트"))
        # 2. 특수문자 차이 매칭
        self.assertTrue(self.service.verify_match("CV1234100", "나이키 에어맥스 [CV1234-100]"))
        # 3. 불일치 품번
        self.assertFalse(self.service.verify_match("CV1234-100", "나이키 에어맥스 CV9999-100"))
        # 4. 빈 문자열
        self.assertFalse(self.service.verify_match("", "어떤 상품"))

    def test_discount_rate_bounding(self):
        """할인율 연산 및 안전 범위 바운딩 테스트"""
        # 정상 범위
        self.assertEqual(Math_bound(35.5), 35.5)
        # 마이너스 할인율 (TAG가보다 비싼 온라인 최저가) -> 0%로 조정
        self.assertEqual(Math_bound(-10.2), 0.0)
        # 100% 이상 할인율 (극단적 오류) -> 100%로 조정
        self.assertEqual(Math_bound(105.0), 100.0)

    @patch('core.price_predict_service.requests.get')
    def test_fetch_online_price_via_naver_success(self, mock_get):
        """네이버 검색 API 성공 시의 가격 및 타이틀 매칭 반환 테스트"""
        # API 인증 정보 모킹 설정
        self.service.naver_client_id = "test_id"
        self.service.naver_client_secret = "test_secret"

        # Mock API 응답
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "정품 아디다스 스니커즈 [FV3001]",
                    "lprice": "89000"
                }
            ]
        }
        mock_get.return_value = mock_response

        price, title = self.service.fetch_online_price_via_naver("FV3001")
        self.assertEqual(price, 89000)
        self.assertIn("FV3001", title)

    @patch('core.price_predict_service.requests.get')
    def test_fetch_online_price_via_naver_mismatch(self, mock_get):
        """네이버 API에 결과는 왔지만 품번 매칭 검증을 통과하지 못해 건너뛰는 사례 테스트"""
        self.service.naver_client_id = "test_id"
        self.service.naver_client_secret = "test_secret"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "title": "아디다스 샌들 다른품번 FV9999",
                    "lprice": "45000"
                }
            ]
        }
        mock_get.return_value = mock_response

        price, title = self.service.fetch_online_price_via_naver("FV3001")
        self.assertIsNone(price)
        self.assertIsNone(title)

if __name__ == "__main__":
    unittest.main()
