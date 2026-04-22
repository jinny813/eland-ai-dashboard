
import pandas as pd
import io
from parsers.babagroup_parser import BabaGroupParser

def test_babagroup_parsing():
    print("="*60)
    print("   바바그룹(JJ지고트) 파서 정밀 검증 테스트   ")
    print("="*60)
    
    parser = BabaGroupParser()

    # 1. 재고 데이터 샘플 (이중 헤더)
    inv_text = """No	매장코드	매장명	품번	판매구분	출고단가	출고			반품			판매			총재고				처리중재고							가용			
						물류	RT이동	합계	물류	RT이동	합계	판매	반품	합계	수량	TAG금액	최초판매금액	매가	당일출고	RT입고	반품중	수량	TAG금액	최초판매금액	매가	수량	TAG금액	최초판매금액	매가
1	GB0107	NC신구로	GN3A0BL10	균일	35,800	17		17	11		11				6	1,074,000	1,074,000	214,800								6	1,074,000	1,074,000	214,800
2	GB0107	NC신구로	GN3A0BL11	균일	31,800	16		16	9		9	3		3	4	636,000	636,000	127,200								4	636,000	636,000	127,200"""
    
    inv_df = pd.read_csv(io.StringIO(inv_text), sep='\t', header=None)
    parsed_inv = parser.parse_inventory(inv_df)
    
    print("\n[재고 파싱 결과]")
    if not parsed_inv.empty:
        row = parsed_inv.iloc[0]
        print(f" - 품번: {row['style_code']}")
        print(f" - 총재고 수량: {row['stock_qty']} (예상: 6)")
        print(f" - 총재고 금액: {row['stock_amt']} (예상: 1074000)")
        print(f" - 계산된 단가: {row['normal_price']} (금액/수량 = 179000)")
        print(f" - 계산된 할인율: {row['discount_rate']}% (예상: 80.0%)")
        print(f" - 연도: {row['year']} (예상: 0)")
    else:
        print(" - 재고 파싱 실패")

    # 2. 판매 데이터 샘플
    sales_text = """No	판매일자	기판매일자	품번	색상	사이즈	POS	영수증	순번	판매유형	현할인율	실할인율	할인율	TAG가	최초판매가	현판매가	수량	최초판매금액	현판매금액	할인금액	실판매금액	사용마일리지	최종판매금액	마진율	작업자
1	2026-03-01	2026-03-01	GN3A0BL10	BL10	55	P1	22	1	정상	0	0	0	179,000	179,000	179,000	2	179,000	179,000	0	179,000	0	179,000	18	NC신구로"""
    # 수량을 2로 수정하여 단가*수량 계산 검증
    
    sales_df = pd.read_csv(io.StringIO(sales_text), sep='\t', header=None)
    parsed_sales = parser.parse_sales(sales_df)
    
    print("\n[판매 파싱 결과]")
    if not parsed_sales.empty:
        row = parsed_sales.iloc[0]
        print(f" - 품번: {row['style_code']}")
        print(f" - 판매수량: {row['sales_qty']} (피드백 반영: 2)")
        print(f" - 판매금액(총액): {row['sales_amt']} (단가 179000 * 2 = 358000)")
        print(f" - 판매일자: {row['sales_date']}")
    else:
        print(" - 판매 파싱 실패")

if __name__ == "__main__":
    test_babagroup_parsing()
