"""Simple script to inspect and view SQLite database tables and records in clean table format."""
import sqlite3
import json

def view_database(db_path="run.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]

    print("=" * 80)
    print(f"DATABASE: {db_path} (Found {len(tables)} tables)")
    print("=" * 80)

    for table in tables:
        print(f"\n[TABLE]: {table}")
        print("-" * 80)

        # Get column schema
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [col[1] for col in cursor.fetchall()]
        print("Columns:", " | ".join(columns))
        print("-" * 80)

        # Get rows
        cursor.execute(f"SELECT * FROM {table} LIMIT 10;")
        rows = cursor.fetchall()
        if not rows:
            print("  (Table is empty)")
        else:
            for idx, r in enumerate(rows, start=1):
                row_dict = dict(r)
                print(f"[{idx}] {json.dumps(row_dict, indent=2, default=str)}")
        print("=" * 80)

    conn.close()

if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "run.db"
    view_database(db)
