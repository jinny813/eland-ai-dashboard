import sqlite3
import os

def init_db():
    db_dir = "database"
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    db_path = os.path.join(db_dir, "product_master.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        style_code TEXT PRIMARY KEY,
        product_name TEXT,
        category TEXT,
        fit TEXT,
        material TEXT,
        detail TEXT,
        color TEXT,
        season_code TEXT,
        discount_rate REAL,
        brand TEXT,
        keywords TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 인덱스 생성 (검색 성능 최적화)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brand ON products(brand)")

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

if __name__ == "__main__":
    init_db()
