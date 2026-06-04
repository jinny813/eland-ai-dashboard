import sqlite3
import os

def migrate_db():
    db_path = os.path.join("database", "product_master.db")
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 현재 컬럼 목록 조회
    cursor.execute("PRAGMA table_info(products)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    new_columns = {
        "tag_price": "INTEGER DEFAULT 0",
        "predicted_online_price": "INTEGER",
        "predicted_discount_rate": "REAL"
    }

    modified = False
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            try:
                print(f"Adding column '{col_name}' to 'products' table...")
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
                modified = True
            except sqlite3.OperationalError as e:
                print(f"Failed to add column '{col_name}': {e}")
        else:
            print(f"Column '{col_name}' already exists in 'products' table.")

    if modified:
        conn.commit()
        print("Database migration completed successfully.")
    else:
        print("No migration needed. All columns are already up to date.")

    conn.close()

if __name__ == "__main__":
    migrate_db()
