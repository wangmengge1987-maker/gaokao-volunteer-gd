#!/usr/bin/env python3
"""Import 2026 enrollment plan for 广东第二师范学院.
Uses existing crawl totals (2613) and 2025 per-major distribution."""
import sqlite3
from collections import defaultdict

conn = sqlite3.connect('gaokao.db')
conn.text_factory = str
c = conn.cursor()

# Get 2025 per-major data
c.execute("SELECT * FROM enrollment_plan WHERE school_code=14278 AND year=2025")
rows_2025 = c.fetchall()
# Index: 0=id, 1=yr, 2=prov, 3=batch, 4=scode, 5=sname, 6=gcode, 7=gname,
# 8=mcode, 9=mname, 10=subj_r, 11=subj_t, 12=plan, 13=level, 14=city

# Get 2026 group totals from existing crawl
c.execute("SELECT group_code, SUM(plan_count) FROM enrollment_plan WHERE school_code=14278 AND year=2026 GROUP BY group_code")
groups_2026 = {r[0]: r[1] for r in c.fetchall()}

# Group 2025 records by group_code
groups_2025 = defaultdict(list)
for row in rows_2025:
    groups_2025[row[6]].append(row)

# Calculate scaling for each group
print('Group comparison (2025 -> 2026):')
for gc in sorted(set(list(groups_2025.keys()) + list(groups_2026.keys()))):
    total_25 = sum(int(r[12]) for r in groups_2025.get(gc, []))
    total_26 = groups_2026.get(gc, 0)
    status = 'SAME' if total_25 == total_26 else 'CHANGED'
    if total_25 > 0:
        ratio = total_26 / total_25
    else:
        ratio = 0
    print(f'  {gc}: {total_25} -> {total_26} ({ratio:.2f}x) [{status}]')
    if total_25 != total_26 and total_25 > 0:
        for row in groups_2025[gc]:
            print(f'    {row[8]} {row[9]}: {row[12]} -> {round(int(row[12])*ratio)}')

# Delete existing 2026 aggregate records
c.execute("DELETE FROM enrollment_plan WHERE school_code=14278 AND year=2026")
print(f'\nDeleted existing 2026 data')

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
            print(f'  WARN: {gc} has 0 in 2025, skipping')
    else:
        # New group in 2026 - create aggregate placeholder
        c.execute("""INSERT INTO enrollment_plan
        (year, province, batch, school_code, school_name, group_code, group_name,
         major_code, major_name, subject_requirement, subject_track, plan_count, school_level, city)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (2026, '广东', '本科普通批', '14278', '广东第二师范学院', gc, f'2026计划({gc})',
         '999999', f'2026计划({gc})', '不限', '物理', total_26, '普通本科', '广州'))
        inserted += 1
        print(f'  NOTE: New group {gc} with {total_26}人 (no 2025 data)')

conn.commit()

# Verify
c.execute("SELECT SUM(plan_count), COUNT(*) FROM enrollment_plan WHERE school_code=14278 AND year=2026")
total, cnt = c.fetchone()
print(f'\nInserted {inserted} records, total: {total}人, {cnt} rows')

c.execute("SELECT group_code, subject_track, SUM(plan_count) FROM enrollment_plan WHERE school_code=14278 AND year=2026 GROUP BY group_code ORDER BY group_code")
print('\n分组统计:')
for gc, track, count in c.fetchall():
    print(f'  {gc} ({track}): {count}人')

conn.close()
print('\nDone!')
