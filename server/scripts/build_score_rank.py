"""
Build score_rank mapping from admission_history data.

Since the database doesn't have a real 一分一段表 (score distribution),
this script generates approximate score-to-rank mappings using the
(min_score, min_rank) data points from admission_history.

Usage:
    cd server
    python scripts/build_score_rank.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "gaokao.db"


def build():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    groups = conn.execute("""
        SELECT DISTINCT year, subject_track FROM admission_history
        WHERE min_score IS NOT NULL AND min_rank IS NOT NULL
          AND min_score > 0 AND min_rank > 0
        ORDER BY year, subject_track
    """).fetchall()

    # Clear existing data
    conn.execute("DELETE FROM score_rank")
    total = 0
    for grp in groups:
        year = grp["year"]
        track = grp["subject_track"]

        rows = conn.execute("""
            SELECT min_score, MIN(min_rank) as best_rank
            FROM admission_history
            WHERE year = ? AND subject_track = ?
              AND min_score IS NOT NULL AND min_rank IS NOT NULL
              AND min_score > 0 AND min_rank > 0
            GROUP BY min_score
            ORDER BY min_score DESC
        """, (year, track)).fetchall()

        if len(rows) < 2:
            continue

        points = {r["min_score"]: r["best_rank"] for r in rows}
        scores = sorted(points.keys(), reverse=True)

        # Extrapolate down to score 200
        if scores:
            low_pts = sorted([(s, points[s]) for s in scores])[:5]
            x1, y1 = low_pts[0]
            x2, y2 = low_pts[-1]
            down_slope = (y2 - y1) / (x2 - x1) if x2 != x1 else 2000
            lowest = scores[-1]
            for s in range(lowest - 1, 199, -1):
                points[s] = max(y1 + int((s - x1) * down_slope), y1)

        # Extrapolate up to score 750
        if scores:
            high_pts = sorted([(s, points[s]) for s in scores], reverse=True)[:5]
            x1, y1 = high_pts[0]
            x2, y2 = high_pts[-1]
            up_slope = (y2 - y1) / (x2 - x1) if x2 != x1 else -10
            highest = scores[0]
            for s in range(highest + 1, 751):
                points[s] = max(1, y1 + int((s - x1) * up_slope))

        # Interpolate gaps
        all_scores = sorted(points.keys(), reverse=True)
        for i in range(len(all_scores) - 1):
            hi_s, hi_r = all_scores[i], points[all_scores[i]]
            lo_s, lo_r = all_scores[i + 1], points[all_scores[i + 1]]
            for mid in range(hi_s - 1, lo_s, -1):
                if mid not in points:
                    ratio = (mid - lo_s) / (hi_s - lo_s) if hi_s != lo_s else 0
                    points[mid] = int(lo_r + ratio * (hi_r - lo_r))

        # Insert
        count = 0
        for s in sorted(points.keys(), reverse=True):
            conn.execute("""
                INSERT OR REPLACE INTO score_rank
                (year, province, subject_track, score, rank)
                VALUES (?, '广东', ?, ?, ?)
            """, (year, track, s, points[s]))
            count += 1
        total += count
        print(f"  [{year} {track}] {count} scores ({min(points.keys())}-{max(points.keys())})")

    conn.commit()
    conn.close()
    print(f"\nTotal: {total} score_rank entries")


if __name__ == "__main__":
    build()
