import sqlite3
import json

db_path = 'd:/AI Assortment Agent/database/product_master.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM products_best LIMIT 5")
rows = cur.fetchall()

result = [dict(row) for row in rows]
with open('d:/AI Assortment Agent/scratch/db_sample.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

cur.execute("SELECT COUNT(*) FROM products_best")
print("Total rows:", cur.fetchone()[0])
conn.close()
