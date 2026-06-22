import sqlite3
conn = sqlite3.connect('database/product_master.db')
c = conn.cursor()
c.execute("SELECT * FROM products WHERE style_code='P4H21WBL090'")
print('P4H21WBL090:', c.fetchall())
c.execute("SELECT * FROM products WHERE style_code='P1G21WBL020'")
print('P1G21WBL020:', c.fetchall())
