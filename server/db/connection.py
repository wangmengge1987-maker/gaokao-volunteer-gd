import sqlite3
from pathlib import Path

from config import settings


def get_connection() -> sqlite3.Connection:
    db_path = Path(__file__).resolve().parent.parent / settings.database_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
