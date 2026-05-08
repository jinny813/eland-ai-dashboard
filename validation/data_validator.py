import sqlite3
import pandas as pd
import sys
import argparse

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r'd:\AI Assortment Agent\database\product_master.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def check_db_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    print("=== Database Tables ===")
    for t in tables:
        print(f"Table Name: {t[0]}")
    conn.close()

def check_schema(table_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = cur.fetchall()
    print(f"=== Schema for {table_name} ===")
    for col in columns:
        print(col)
    conn.close()

def check_first_row(table_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
    row = cur.fetchone()
    print(f"=== First Row of {table_name} ===")
    print(row)
    conn.close()

def check_brand_data(brand_name, limit=10):
    conn = get_connection()
    query = f"SELECT * FROM products WHERE brand_name LIKE '%{brand_name}%' LIMIT {limit}"
    df = pd.read_sql(query, conn)
    print(f"=== Data for Brand: {brand_name} ===")
    if df.empty:
        print("No data found.")
    else:
        print(df.to_string())
        
    query_cat = f"SELECT DISTINCT item_cat FROM products WHERE brand_name LIKE '%{brand_name}%'"
    items = pd.read_sql(query_cat, conn)
    print(f"\n--- {brand_name} Item Categories ---")
    print(items)
    conn.close()

def check_style_item(style_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM products WHERE style_code='{style_code}'")
    row = cur.fetchone()
    print(f"=== Data for Style Code: {style_code} ===")
    print(row)
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Validation Tool for AI Assortment Agent")
    parser.add_argument("--tables", action="store_true", help="List all tables in the database")
    parser.add_argument("--schema", type=str, help="Show schema for a specific table")
    parser.add_argument("--first-row", type=str, help="Show the first row of a specific table")
    parser.add_argument("--brand", type=str, help="Show sample data and categories for a specific brand")
    parser.add_argument("--style", type=str, help="Show data for a specific style code")
    
    args = parser.parse_args()
    
    if args.tables:
        check_db_tables()
    elif args.schema:
        check_schema(args.schema)
    elif args.first_row:
        check_first_row(args.first_row)
    elif args.brand:
        check_brand_data(args.brand)
    elif args.style:
        check_style_item(args.style)
    else:
        parser.print_help()
