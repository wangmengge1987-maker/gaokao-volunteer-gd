from db.connection import get_connection
from config import settings


def score_to_rank(subject_track: str, score: int, year: int | None = None) -> dict | None:
    """Convert score to rank using score_rank table (广东 物理/历史 方向)."""
    year = year or settings.data_year
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT score, rank, cumulative_count
            FROM score_rank
            WHERE year = ? AND province = ? AND subject_track = ? AND score <= ?
            ORDER BY score DESC
            LIMIT 1
            """,
            (year, settings.province, subject_track, score),
        ).fetchone()
        if row:
            return {"score": row["score"], "rank": row["rank"], "year": year}
        return None
    finally:
        conn.close()
