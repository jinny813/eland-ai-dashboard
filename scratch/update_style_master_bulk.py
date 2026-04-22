import json
import os

def update_master():
    path = "d:/AI Assortment Agent/core/style_master.json"
    with open(path, "r", encoding="utf-8") as f:
        master = json.load(f)
        
    new_data = {
        # 시슬리
        "SAWSF6431": { "item_name": "셔츠", "style_name": "베이직 루즈핏 셔츠", "brand": "시슬리" },
        "SAPTF3631": { "item_name": "팬츠", "style_name": "밴딩 슬림핏 팬츠", "brand": "시슬리" },
        "SAJKF1611": { "item_name": "자켓", "style_name": "라운드넥 트위드 자켓", "brand": "시슬리" },
        "SADPA1611": { "item_name": "팬츠", "style_name": "워싱 디테일 와이드 데님 팬츠", "brand": "시슬리" },
        "SATSF3631": { "item_name": "티셔츠", "style_name": "헤이니 포켓 린넨 티셔츠", "brand": "시슬리" },
        # 플라스틱아일랜드
        "PQ1CL201": { "item_name": "티셔츠", "style_name": "스트라이프 보트넥 티셔츠", "brand": "플라스틱아일랜드" },
        "PQ1CL702": { "item_name": "가디건", "style_name": "배색 라운드넥 가디건", "brand": "플라스틱아일랜드" },
        "PR2WS362": { "item_name": "스커트", "style_name": "트위드 A라인 미니 스커트", "brand": "플라스틱아일랜드" },
        "PR2WJ361": { "item_name": "자켓", "style_name": "벨트옵션 박시핏 싱글 반우라 자켓", "brand": "플라스틱아일랜드" },
        "PR4HJ561": { "item_name": "자켓", "style_name": "트위드 숏 자켓", "brand": "플라스틱아일랜드" },
        # 샤틴
        "S261K153A": { "item_name": "원피스", "style_name": "레이스 배색 원피스", "brand": "샤틴" },
        "S254K953A": { "item_name": "니트", "style_name": "진주 가디건 니트", "brand": "샤틴" },
        "S261K954A": { "item_name": "니트", "style_name": "프릴 배색 브이넥 니트", "brand": "샤틴" },
        "S261K959A": { "item_name": "가디건", "style_name": "라인 배색 크롭 가디건", "brand": "샤틴" },
        "S261K752A": { "item_name": "스커트", "style_name": "플라워 패턴 벨티드 스커트", "brand": "샤틴" },
        # 제시뉴욕
        "ME45NRKG5190": { "item_name": "가디건", "style_name": "알렉시스앤 자가드 브이넥 니트 가디건", "brand": "제시뉴욕" },
        "ME45NRKO6230": { "item_name": "니트", "style_name": "알렉시스앤 골지 라운드 니트", "brand": "제시뉴욕" },
        "AEM5NSDP2280": { "item_name": "팬츠", "style_name": "밑단 디테일 와이드 데님 팬츠", "brand": "제시뉴욕" },
        "AEM5NSTZ2160": { "item_name": "팬츠", "style_name": "스트레이트핏 생지 데님", "brand": "제시뉴욕" },
        "BGM1OKPO5040": { "item_name": "니트", "style_name": "알렉시스앤 넥쉬폰 포인트 니트", "brand": "제시뉴욕" },
        # 안지크
        "AH4TS5120": { "item_name": "티셔츠", "style_name": "그래픽 베이직 티셔츠", "brand": "안지크" },
        "AI3BR5130": { "item_name": "블라우스", "style_name": "셔츠형 레귤러 블라우스", "brand": "안지크" },
        "AK1BR5100": { "item_name": "코트", "style_name": "디테일꼬마후드집업코트", "brand": "안지크" },
        "AG4JK3000": { "item_name": "자켓", "style_name": "더블 코튼 트렌치 자켓", "brand": "안지크" },
        "AJ3LP5900": { "item_name": "팬츠", "style_name": "세미 배기 린넨 팬츠", "brand": "안지크" },
        # 로엠
        "RMCKF23R98": { "item_name": "가디건", "style_name": "[올데이가디건] 브이넥 가디건", "brand": "로엠" },
        "RMJKG12ST1": { "item_name": "자켓", "style_name": "칼라리스 트위드자켓", "brand": "로엠" },
        "RMJKF4TR15": { "item_name": "자켓", "style_name": "테일러드 자켓", "brand": "로엠" },
        "RMCKF23R99": { "item_name": "가디건", "style_name": "[올데이가디건] 라운드넥 가디건", "brand": "로엠" },
        "RMTWG23R12": { "item_name": "팬츠", "style_name": "[올데이슬랙스] 원턱 와이드 밴딩슬랙스", "brand": "로엠" },
        # 보니스팍스
        "B3H12KVT010": { "item_name": "가디건", "style_name": "앞 포켓 후드 KV", "brand": "보니스팍스" },
        "B3G22KPO010": { "item_name": "니트", "style_name": "오픈카라 KP", "brand": "보니스팍스" },
        "B3H12KPO010": { "item_name": "니트", "style_name": "라운드 꼬마포켓 7부소매 KP", "brand": "보니스팍스" },
        "B3H12KPO020": { "item_name": "니트", "style_name": "반하이넥 배색 스티치 KP", "brand": "보니스팍스" },
        "B1H11WBL020": { "item_name": "블라우스", "style_name": "니트카라 아우터형 BL", "brand": "보니스팍스" }
    }
    
    master.update(new_data)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print("style_master.json successfully updated with 35 new items.")

if __name__ == "__main__":
    update_master()
