-- [대시보드 데이터 매핑 정의서 기반] 21개 컬럼 스키마 및 인덱스 생성 스크립트

-- 1. 트랜잭션 데이터 테이블 생성 (21개 컬럼 반영)
CREATE TABLE IF NOT EXISTS records (
    no INTEGER PRIMARY KEY AUTOINCREMENT,        -- 순번
    year INTEGER,                                -- 연도
    season_code VARCHAR(10) NOT NULL,            -- 시즌코드
    style_code VARCHAR(50) NOT NULL,             -- 스타일코드
    style_name VARCHAR(255),                     -- 스타일명
    item_code VARCHAR(20) NOT NULL,              -- 아이템코드
    item_name VARCHAR(100),                      -- 아이템명
    price_type VARCHAR(20),                      -- 가격구분
    stock_qty INTEGER NOT NULL,                  -- 재고수량
    stock_amt BIGINT NOT NULL,                   -- 재고금액
    sales_qty INTEGER,                           -- 판매수량
    sales_amt BIGINT,                            -- 판매금액
    normal_price INTEGER NOT NULL,               -- 정상가
    sales_date DATE,                             -- 판매일자
    brand_name VARCHAR(50) NOT NULL,             -- 브랜드명
    store_name VARCHAR(50) NOT NULL,             -- 매장명
    category_group VARCHAR(50) NOT NULL,         -- 복종그룹
    store_type VARCHAR(30) NOT NULL,             -- 매장형태
    data_month VARCHAR(10) NOT NULL,             -- 데이터월
    freshness_type VARCHAR(20),                  -- 신선도구분
    discount_rate DECIMAL(5,2)                   -- 할인율
);

-- 2. 성능 최적화를 위한 인덱스 설정
CREATE INDEX IF NOT EXISTS idx_dashboard_filter ON records(brand_name, store_name, data_month, category_group);
CREATE INDEX IF NOT EXISTS idx_sales_trend ON records(sales_date, sales_amt) WHERE sales_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_style_performance ON records(style_code, sales_qty DESC);

-- 3. 집계 속도 향상을 위한 뷰(View)
CREATE VIEW IF NOT EXISTS v_monthly_brand_summary AS
SELECT 
    data_month,
    brand_name,
    store_name,
    category_group,
    SUM(stock_qty) as total_stock_qty,
    SUM(stock_amt) as total_stock_amt,
    SUM(sales_qty) as total_sales_qty,
    SUM(sales_amt) as total_sales_amt,
    CASE 
        WHEN SUM(sales_qty * normal_price) > 0 
        THEN 1 - (CAST(SUM(sales_amt) AS FLOAT) / SUM(sales_qty * normal_price))
        ELSE 0 
    END as avg_discount_rate
FROM records
GROUP BY data_month, brand_name, store_name, category_group;
