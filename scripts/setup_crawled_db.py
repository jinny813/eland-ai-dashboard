import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "product_master.db")

def init_crawled_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Create the new table for crawled data
    cur.execute('''
        CREATE TABLE IF NOT EXISTS crawled_product_names (
            style_code TEXT PRIMARY KEY,
            product_name TEXT,
            brand TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Optionally, migrate existing data if products has it but crawled_product_names doesn't?
    # But usually product_name in products was already polluted by crawling, so let's just create it.
    conn.commit()
    conn.close()
    print("crawled_product_names table created successfully.")

if __name__ == "__main__":
    init_crawled_table()
