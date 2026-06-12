"""Initialize SQLite database with schema and sample data."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "gaokao.db"
SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
SAMPLES = Path(__file__).resolve().parent.parent.parent / "data" / "samples"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    for csv_name, table in [
        ("score_rank_sample.csv", "score_rank"),
        ("enrollment_plan_sample.csv", "enrollment_plan"),
        ("admission_history_sample.csv", "admission_history"),
    ]:
        csv_path = SAMPLES / csv_name
        if not csv_path.exists():
            continue
        import csv

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                continue
            cols = reader.fieldnames
            placeholders = ",".join("?" * len(cols))
            sql = f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
            conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
