#!/usr/bin/env python3
"""Import 2026 enrollment plan for 广东医科大学 from news article."""

import sqlite3
from collections import defaultdict

CATEGORIES_2026 = {
    'pth_wl': 3654,
    'pth_ls': 465,
    'dfzx': 100,
    'lhxs': 120,
    'xtpy': 140,
    'ddyx': 222,
}

conn = sqlite3.connect('gaokao.db')
conn.text_factory = str
c = conn.cursor()

c.execute("SELECT * FROM enrollment_plan WHERE school_code=10571 AND year=2025")
rows_2025 = c.fetchall()
print(f'2025 records: {len(rows_2025)}')

# Col indices: 1=yr, 2=prov, 3=batch, 4=scode, 5=sname,
# 6=gcode, 7=gname, 8=mcode, 9=mname, 10=subj_req,
# 11=subj_trk, 12=plan, 13=level, 14=city

def get_cat(gc):
    """Categorize 2025 group_code to 2026 category plan group"""
    suffix = gc[5:]  # Remove '10571'
    if suffix.startswith('2'):
        g = suffix[1:]  # e.g. '201' -> '01'
        if g in ['01','02','03','04','05']:
            return 'pth_wl'
        elif g in ['06','07','08']:
            return 'xtpy'
        elif g == '09':
            return 'dfzx'
        elif g in ['10','11']:
            return 'lhxs'
        elif g == '12':
            return 'pth_ls'
    # All 10571 + 1XX (104-124) are 订单定向
    if suffix.startswith('1'):
        return 'ddyx'
    return 'other'

cat_records = defaultdict(list)
for row in rows_2025:
    cat = get_cat(row[6])
    cat_records[cat].append(row)

print('\nCategory breakdown (2025 -> 2026):')
for cat, recs in sorted(cat_records.items()):
    total = sum(int(r[12]) for r in recs)
    target = CATEGORIES_2026.get(cat, 0)
    print(f'  {cat}: {len(recs)} groups, {total}人 -> {target}人')

# Delete existing 2026 data
c.execute("DELETE FROM enrollment_plan WHERE school_code=10571 AND year=2026")
print('\nDeleted existing 2026 data')

# Insert scaled records
inserted = 0
for cat, recs in cat_records.items():
    old_total = sum(int(r[12]) for r in recs)
    new_total = CATEGORIES_2026.get(cat)
    if new_total is None or old_total == 0:
        print(f'Skipping {cat}')
        continue
    scale = new_total / old_total
    remaining = new_total
    for i, row in enumerate(recs):
        old_plan = int(row[12])
        if i == len(recs) - 1:
            new_plan = remaining
        else:
            new_plan = round(old_plan * scale)
            new_plan = min(new_plan, remaining)
        remaining -= new_plan
        c.execute("""INSERT INTO enrollment_plan
        (year, province, batch, school_code, school_name, group_code, group_name,
         major_code, major_name, subject_requirement, subject_track, plan_count, school_level, city)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (2026, row[2], row[3], row[4], row[5], row[6], row[7],
         row[8], row[9], row[10], row[11], new_plan, row[13], row[14]))
        inserted += 1

conn.commit()

# Verify
c.execute("SELECT SUM(plan_count), COUNT(*) FROM enrollment_plan WHERE school_code=10571 AND year=2026")
total, cnt = c.fetchone()
print(f'\nInserted {inserted} records, total: {total}人, {cnt} rows')

c.execute("SELECT substr(group_code,6), subject_track, SUM(plan_count) FROM enrollment_plan WHERE school_code=10571 AND year=2026 GROUP BY group_code ORDER BY group_code")
print('\n分组统计:')
for gc_suffix, track, count in c.fetchall():
    print(f'  {gc_suffix} ({track}): {count}人')

print('\n分类汇总:')
summaries = [
    ('pth_wl', '普通类物理', ['201','202','203','204','205']),
    ('pth_ls', '普通类历史', ['212']),
    ('dfzx', '地方专项', ['209']),
    ('lhxs', '联合学士学位', ['210','211']),
    ('xtpy', '协同培养', ['206','207','208']),
    ('ddyx', '订单定向医学生', ['104','105','106','107','108','109','110','111','112','113','114','115','116','117','118','119','120','121','122','123','124']),
]
for cat, cat_name, suffixes in summaries:
    total = 0
    for s in suffixes:
        c.execute("SELECT COALESCE(SUM(plan_count),0) FROM enrollment_plan WHERE school_code=10571 AND year=2026 AND group_code LIKE ?", ('10571' + s,))
        total += c.fetchone()[0]
    expected = CATEGORIES_2026.get(cat, 0)
    match = 'OK' if total == expected else f'MISMATCH (expected {expected})'
    print(f'  {cat_name}: {total}人 {match}')

conn.close()
