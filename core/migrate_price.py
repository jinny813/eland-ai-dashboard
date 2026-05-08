import sqlite3
import pandas as pd

def migrate_db():
    conn = sqlite3.connect('database/product_master.db')
    cursor = conn.cursor()
    
    # 1. normal_price 컬럼 추가 (이미 있으면 무시)
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN normal_price REAL")
        print("normal_price 컬럼이 추가되었습니다.")
    except sqlite3.OperationalError:
        print("normal_price 컬럼이 이미 존재합니다.")
    
    # 2. 특정 품번(GS4M0BL901) 단가 업데이트 (259,000원)
    cursor.execute("UPDATE products SET normal_price = 259000 WHERE style_code = 'GS4M0BL901'")
    
    # 3. 다른 품번들도 샘플 데이터로 업데이트 (옵션)
    # 실제 운영 시에는 크롤링 또는 엑셀 업로드 시 반영되도록 파이서 수정 필요
    
    conn.commit()
    conn.close()
    print("DB 마이그레이션 및 단가 보정이 완료되었습니다.")

if __name__ == "__main__":
    migrate_db()
