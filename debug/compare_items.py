import sqlite3
conn = sqlite3.connect('database/product_master.db')
cursor = conn.cursor()
styles = ['GS2A0SK111', 'GS3A0OP211', 'GS4M0BL901']
for s in styles:
    cursor.execute(f"SELECT * FROM products WHERE style_code='{s}'")
    print(s, cursor.fetchone())
conn.close()
