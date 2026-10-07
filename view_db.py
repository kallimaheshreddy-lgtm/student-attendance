r"""
SQLite Database Viewer CLI Utility
Run: .\.venv\Scripts\python.exe view_db.py
"""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent / "database.db"

def main():
    if not DB_FILE.exists():
        print(f"Error: {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    print("=" * 65)
    print(f" SQLite Database: {DB_FILE.name}")
    print("=" * 65)

    for tbl in tables:
        tbl_name = tbl["name"]
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl_name}").fetchone()[0]
        print(f"\n[TABLE] {tbl_name} ({count} total records)")
        print("-" * 65)

        rows = cursor.execute(f"SELECT * FROM {tbl_name} LIMIT 10").fetchall()
        if not rows:
            print("   (Empty table)")
            continue

        columns = [d[0] for d in cursor.description]
        print(" | ".join(f"{col:15}" for col in columns))
        print("-" * 65)
        for r in rows:
            values = []
            for col in columns:
                val = str(r[col])
                if len(val) > 15:
                    val = val[:12] + "..."
                values.append(f"{val:15}")
            print(" | ".join(values))

    conn.close()
    print("\n" + "=" * 65)

if __name__ == "__main__":
    main()
