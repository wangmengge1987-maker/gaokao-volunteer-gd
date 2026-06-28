#!/usr/bin/env python3
"""Import 2026 enrollment plan for 广东金融学院 from crawl aggregates + 2025 detail."""
import sqlite3
from collections import defaultdict

conn = sqlite3.connect('gaokao.db')
conn.text_factory = str
c = conn.cursor()

# Get 2025 per-major data
c.execute("SELECT * FROM enrollment_plan WHERE school_code=11540 AND year=2025")
rows_2025 = c.fetchall()
print(f'2025 records: {len(rows_2025)}')

# Get 2026 group totals from crawl
c.execute("SELECT group_code, SUM(plan_count) FROM enrollment_plan WHERE school_code=11540 AND year=2026 GROUP BY group_code")
groups_2026 = {r[0]: int(r[1]) for r in c.fetchall()}

# Group 2025 records by group_code
groups_2025 = defaultdict(list)
for row in rows_2025:
    groups_2025[row[6]].append(row)

# Calculate scaling for each group
print('\nGroup comparison:')
for gc in sorted(set(list(groups_2025.keys()) + list(groups_2026.keys()))):
    total_25 = sum(int(r[12]) for r in groups_2025.get(gc, []))
    total_26 = groups_2026.get(gc, 0)
    if total_25 > 0:
        ratio = total_26 / total_25
        changed = '***' if total_25 != total_26 else ''
        print(f'  {gc}: {total_25} -> {total_26} ({ratio:.3f}x) {changed}')

# Delete existing 2026 aggregate records
c.execute("DELETE FROM enrollment_plan WHERE school_code=11540 AND year=2026")
print('\nDeleted existing 2026 data')

# Insert new records with scaled plan counts
inserted = 0
for gc in sorted(groups_2026.keys()):
    total_26 = groups_2026[gc]
    if gc in groups_2025:
        recs_25 = groups_2025[gc]
        total_25 = sum(int(r[12]) for r in recs_25)
        if total_25 > 0:
            scale = total_26 / total_25
            remaining = total_26
            for i, row in enumerate(recs_25):
                old_plan = int(row[12])
                if i == len(recs_25) - 1:
                    new_plan = remaining
                else:
                    new_plan = round(old_plan * scale)
                    new_plan = min(new_plan, remaining)
                remaining -= new_plan
                c.execute("""INSERT INTO enrollment_plan
                (year, province, batch, school_code, school_name, group_code, group_name,
                 major_code, major_name, subject_requirement, subject_track, plan_count, school_level, city)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (2026, row[2], row[3], row[4], row[5], gc, row[7],
                 row[8], row[9], row[10], row[11], new_plan, row[13], row[14]))
                inserted += 1
        else:
            print(f'  WARN: {gc} has 0 total in 2025')
    else:
        # New group - create aggregate
        c.execute("""INSERT INTO enrollment_plan
        (year, province, batch, school_code, school_name, group_code, group_name,
         major_code, major_name, subject_requirement, subject_track, plan_count, school_level, city)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (2026, '广东', '本科普通批', '11540', '广东金融学院', gc, f'2026计划({gc})',
         '999999', f'2026计划({gc})', '不限', '物理', total_26, '普通本科', '广州'))
        inserted += 1

conn.commit()

# Verify
c.execute("SELECT SUM(plan_count), COUNT(*) FROM enrollment_plan WHERE school_code=11540 AND year=2026")
total, cnt = c.fetchone()
print(f'\nInserted {inserted} records, total: {total}人, {cnt} rows')

c.execute("SELECT group_code, subject_track, SUM(plan_count) FROM enrollment_plan WHERE school_code=11540 AND year=2026 GROUP BY group_code ORDER BY group_code")
print('\n分组统计:')
for gc, track, count in c.fetchall():
    print(f'  {gc} ({track}): {count}人')

# Summary
c.execute("""
SELECT 
  CASE 
    WHEN group_code LIKE '%11' THEN '历史-专业组211'
    WHEN group_code LIKE '%12' THEN '历史-专业组212'
    WHEN group_code LIKE '%13' THEN '历史-专业组213'
    WHEN group_code LIKE '%14' THEN '历史-专业组214'
    WHEN group_code LIKE '%15' THEN '历史-专业组215'
    WHEN group_code LIKE '%16' THEN '历史-专业组216(国际班)'
    WHEN group_code LIKE '%21' THEN '物理-专业组221'
    WHEN group_code LIKE '%22' THEN '物理-专业组222'
    WHEN group_code LIKE '%23' THEN '物理-专业组223'
    WHEN group_code LIKE '%24' THEN '物理-专业组224'
    WHEN group_code LIKE '%25' THEN '物理-专业组225'
    WHEN group_code LIKE '%26' THEN '物理-专业组226'
    WHEN group_code LIKE '%27' THEN '物理-专业组227'
    WHEN group_code LIKE '%28' THEN '物理-专业组228(国际班)'
    WHEN group_code LIKE '%29' THEN '物理-专业组229(国际班)'
    WHEN group_code LIKE '%31' THEN '历史-专业组231(地方专项)'
    WHEN group_code LIKE '%32' THEN '物理-专业组232(地方专项)'
    WHEN group_code LIKE '%33' THEN '物理-专业组233(地方专项)'
    ELSE group_code
  END as cat,
  SUM(plan_count)
FROM enrollment_plan WHERE school_code=11540 AND year=2026
GROUP BY cat ORDER BY cat
""")
print('\n分类汇总:')
for cat, cnt in c.fetchall():
    print(f'  {cat}: {cnt}人')

conn.close()
print('\nDone!')
