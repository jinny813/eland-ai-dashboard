import sqlite3

print("--- Cleaning product_master.db ---")
conn = sqlite3.connect('database/product_master.db')
cursor = conn.cursor()

# Get column names for products_best
cursor.execute("PRAGMA table_info(products_best)")
columns = [c[1] for c in cursor.fetchall()]
print(f"Columns in products_best: {columns}")

if 'old_name' in columns:
    cursor.execute("SELECT item_code, old_name, product_name FROM products_best")
    rows = cursor.fetchall()
    
    bad_codes = []
    for item_code, old_name, product_name in rows:
        sn = str(product_name).replace('발렌시아가', '')
        # How to check brand from old_name or item_code?
        # Typically the user's issue is: they see bad product names in the dashboard.
        # But wait! If the user says "발렌시아와 안지크 브랜드는 상품명 크롤링이 잘못되고 있어"
        # Are they crawling right NOW? Or is it cached data?
        
        # If it's cached data, we can just wipe all records in products_best where 
        # product_name does NOT contain '발렌시아' AND '안지크' BUT it was supposed to be them!
        pass
conn.close()
