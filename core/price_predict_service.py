import os
import sqlite3
import requests
import re
import time
import logging
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class PricePredictService:
    """
    [v1.0] 상품 품번 기준 온라인 판매가 및 할인율 예측 코어 서비스
    - 네이버 쇼핑 검색 API 연동
    - 품번 - 상품명 매칭 신뢰도 검증
    - 안전 마진 기반의 할인율 계산 및 격리 컬럼 업데이트
    """
    def __init__(self, db_path: str = "database/product_master.db"):
        self.db_path = db_path
        self.naver_client_id = os.environ.get("NAVER_CLIENT_ID", "").strip()
        self.naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()

    def _sanitize_string(self, text: str) -> str:
        """비교 정합성을 위해 특수문자 및 공백을 제거하고 소문자로 치환"""
        if not text:
            return ""
        # <b> 태그 제거 (네이버 검색 결과 등)
        cleaned = re.sub(r'<[^>]*>', '', text)
        # 알파벳과 숫자만 추출
        return re.sub(r'[^a-zA-Z0-9]', '', cleaned).lower()

    def verify_match(self, style_code: str, search_title: str) -> bool:
        """품번이 검색 상품명에 정확히 부합하는지 텍스트 유사성 검증"""
        clean_code = self._sanitize_string(style_code)
        clean_title = self._sanitize_string(search_title)
        
        if not clean_code:
            return False
        # 공백/특수문자 제거 후 품번이 검색 타이틀에 온전히 박혀있는지 판별
        return clean_code in clean_title

    def fetch_online_price_via_naver(self, style_code: str) -> tuple[int | None, str | None]:
        """네이버 쇼핑 API를 통한 최저가 및 상품명 탐색"""
        if not self.naver_client_id or not self.naver_client_secret:
            logger.warning("[PredictService] Naver API credentials are empty. Please check .env file.")
            return None, None

        url = "https://openapi.naver.com/v1/search/shop.json"
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret
        }
        # exclude=used:cb (중고/대여 상품 제외)
        params = {
            "query": style_code,
            "display": 5,
            "exclude": "used:cb"
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                logger.error(f"[NaverAPI] HTTP {resp.status_code}: {resp.text}")
                return None, None

            data = resp.json()
            items = data.get("items", [])
            if not items:
                logger.info(f"[NaverAPI] No items found for style_code: {style_code}")
                return None, None

            # 최적의 상품 매칭 탐색 (유사도 체크)
            for item in items:
                title = item.get("title", "")
                lprice_str = item.get("lprice", "0")
                
                if self.verify_match(style_code, title):
                    try:
                        lprice = int(lprice_str)
                        if lprice > 0:
                            return lprice, title
                    except ValueError:
                        continue

            logger.info(f"[NaverAPI] No matching items passed the verification for: {style_code}")
            return None, None

        except Exception as e:
            logger.error(f"[NaverAPI] Request failed for {style_code}: {e}")
            return None, None

    def run_prediction_batch(self, limit: int = 50) -> int:
        """할인율 예측 파이프라인 일괄 실행"""
        if not os.path.exists(self.db_path):
            logger.error(f"Database not found at: {self.db_path}")
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # tag_price가 존재하고, 예측 데이터가 아직 채워지지 않은 상품 추출
        cursor.execute("""
            SELECT style_code, tag_price 
            FROM products 
            WHERE tag_price > 0 
              AND (predicted_discount_rate IS NULL OR predicted_discount_rate = 0.0)
            LIMIT ?
        """, (limit,))

        targets = cursor.fetchall()
        if not targets:
            logger.info("No targets found for discount rate prediction.")
            conn.close()
            return 0

        logger.info(f"Starting price prediction batch for {len(targets)} styles...")
        updated_count = 0

        for style_code, tag_price in targets:
            logger.info(f"Processing style: {style_code} (TAG Price: {tag_price})")
            
            # API 호출
            online_price, matched_title = self.fetch_online_price_via_naver(style_code)
            
            if online_price is not None:
                # 할인율 계산 (정상 범주 확인 및 예외 차단)
                discount_rate = ((tag_price - online_price) / tag_price) * 100
                discount_rate = Math_bound(discount_rate) # 안전 마진
                
                # DB 업데이트
                cursor.execute("""
                    UPDATE products 
                    SET predicted_online_price = ?,
                        predicted_discount_rate = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE style_code = ?
                """, (online_price, discount_rate, style_code))
                
                logger.info(f"--> Predicted Online Price: {online_price}원, Discount Rate: {discount_rate:.2f}% (Matched: {matched_title})")
                updated_count += 1
            else:
                logger.info(f"--> Skipping style {style_code} due to missing or unverified online price.")
            
            # 외부 API 호출 제한 고려한 약간의 텀 (0.1초)
            time.sleep(0.1)

        if updated_count > 0:
            conn.commit()
            logger.info(f"Batch completed. Successfully updated {updated_count} products.")
        else:
            logger.info("Batch completed. No products were updated.")

        conn.close()
        return updated_count

def Math_bound(val: float) -> float:
    """할인율 안전 마진 범위 한정"""
    return max(0.0, min(100.0, val))

if __name__ == "__main__":
    # 독립 실행 시 배치 50개 동작
    service = PricePredictService()
    service.run_prediction_batch(limit=50)
