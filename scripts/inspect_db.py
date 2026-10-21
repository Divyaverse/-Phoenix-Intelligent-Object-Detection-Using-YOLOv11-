import sqlite3
import os

db_path = "phoenix.db"
print("DB Path:", os.path.abspath(db_path))
print("DB Exists:", os.path.exists(db_path))

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
    print("Tables:", tables)
    for t in tables:
        count = cur.execute(f"SELECT count(*) FROM {t};").fetchone()[0]
        print(f"  {t}: {count} rows")
        if count > 0:
            sample = cur.execute(f"SELECT * FROM {t} LIMIT 2;").fetchall()
            for s in sample:
                print(f"    sample: {dict(s)}")
    conn.close()
