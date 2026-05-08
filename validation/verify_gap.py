import sqlite3
import pandas as pd

conn = sqlite3.connect('database/product_master.db')
print("--- BP BEST 10 List ---")
df_best = pd.read_sql("SELECT * FROM products_best WHERE brand='JJ지고트' AND store_name='BP매장' ORDER BY sales_qty DESC LIMIT 10", conn)
print(df_best[['style_code', 'sales_qty']])

print("\n--- Current Store BEST 10 List (Sample: 신구로점) ---")
df_store = pd.read_sql("SELECT * FROM products_best WHERE brand='JJ지고트' AND store_name='신구로점' ORDER BY sales_qty DESC LIMIT 10", conn)
print(df_store[['style_code', 'sales_qty']])

target_sc = 'GR3M0TC921'
print(f"\nSearching for {target_sc}...")
bp_codes = [str(c).strip() for c in df_best['style_code'].tolist()]
store_codes = [str(c).strip() for c in df_store['style_code'].tolist()]

print(f"In BP BEST: {target_sc in bp_codes}")
print(f"In Store BEST: {target_sc in store_codes}")
print(f"In Gap List: {(target_sc in bp_codes) and (target_sc not in store_codes)}")

conn.close()
