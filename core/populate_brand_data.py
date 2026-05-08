import pandas as pd
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.append(os.getcwd())

from database.gsheet_manager import GSheetManager

def populate_mock_best_items():
    mgr = GSheetManager()
    
    # 1. 시슬리 (SISLEY) 데이터 구성
    sisley_items = [
        ["SAJK22311", "라이트 싱글 쓰리 버튼 자켓", "자켓", 358000, 42, 15000000],
        ["SABL75311", "드레이프 넥 버튼 다운 블라우스", "블라우스", 218000, 38, 8000000],
        ["SATS76311", "제리 JERSEY 턱 꼬임 티셔츠", "티셔츠", 138000, 56, 7500000],
        ["SAKP50011", "밴딩 와이드 슬랙스", "팬츠", 238000, 31, 7200000],
        ["SAOP90011", "브이넥 셔링 원피스", "원피스", 378000, 24, 9000000],
        ["SAJK21311", "노카라 싱글 레이어드 자켓", "자켓", 398000, 18, 7000000],
        ["SAKP21311", "와이드 턱 데님 팬츠", "팬츠", 258000, 22, 5500000],
        ["SAOP70311", "리사 드로잉 프린팅 원피스", "원피스", 438000, 15, 6500000],
    ]
    
    # 2. 베네통 (BENETTON) 데이터 구성
    benetton_items = [
        ["BAKCF1611", "애플하트 포인트 후드 니트 가디건", "니트", 299000, 48, 14000000],
        ["BATSF7541", "애플 자수 포인트 티셔츠", "티셔츠", 119000, 62, 7000000],
        ["BAOP94331", "스트라이프 배색 카라 원피스", "원피스", 359000, 35, 12500000],
        ["BAJP16411", "밀라노 점퍼", "점퍼", 399000, 26, 10000000],
        ["BADPA3611", "부클 와펜 쉐브론 데님 팬츠", "팬츠", 219000, 41, 8500000],
        ["BAJP01611", "니트 배색 볼륨 소매 점퍼", "점퍼", 459000, 19, 8500000],
        ["BAKCA1111", "컬러 배색 하이넥 집업 니트", "니트", 259000, 28, 7000000],
        ["BABLA7631", "딸기 스트라이프 블라우스", "블라우스", 199000, 33, 6500000],
    ]
    
    records = []
    store_name = "NC신구로점"
    cat_group = "여성"
    store_type = "상설"
    data_month = "2026-04"
    
    def add_brand_records(brand_name, items):
        for it in items:
            code, s_name, i_name, price, s_qty, s_amt = it
            records.append({
                "year": "2024",
                "season_code": "1", # 봄
                "style_code": code,
                "style_name": s_name,
                "item_name": i_name,
                "normal_price": price,
                "sales_qty": s_qty,
                "sales_amt": s_amt,
                "stock_qty": s_qty * 3, # 테스트용 재고
                "stock_amt": s_amt * 2.5,
                "brand_name": brand_name,
                "store_name": store_name,
                "category_group": cat_group,
                "store_type": store_type,
                "data_month": data_month,
                "sales_date": "2026-04-10",
                "inv_uid": f"{brand_name}_{code}_MOCK"
            })

    add_brand_records("시슬리", sisley_items)
    add_brand_records("베네통", benetton_items)
    
    df = pd.DataFrame(records)
    print(f"Uploading {len(df)} records for Sisley and Benetton...")
    
    # append_record는 데이터가 중복될 수 있으므로, 해당 월/브랜드 데이터를 먼저 지우고 넣는 overwrite_record가 적합할 수 있음.
    # 하지만 여기선 간단히 append_record를 사용 (기능 확인용)
    success = mgr.append_record(df)
    
    if success:
        print("Successfully populated BEST items data.")
    else:
        print(f"Failed to populate data: {mgr.error_msg}")

if __name__ == "__main__":
    populate_mock_best_items()
