#!/usr/bin/env python3
"""
Import 2026 enrollment plan for 广东财经大学 from PDF data.
Run from project root: python server/scripts/import_2026_guangcai.py
"""
import json
import re
import sqlite3
from collections import defaultdict


# Known stray header characters that get prepended to major names in PDF extraction
STRAY_HEADER_CHARS = set('室办公招生学土金')

def clean_text(text):
    """Remove garbled prefix characters from text"""
    if not text:
        return ''
    text = re.sub(r'^[\sѧ��ѧ��]+', '', text)
    text = re.sub(r'[\sѧ��ѧ��]+$', '', text)
    return text


def clean_major_name(name):
    """
    Clean major name by removing stray prefix characters from PDF table headers.
    Pattern: stray Chinese char + space + actual_name
    """
    import unicodedata
    name = name.strip()
    # Check if starts with a single Chinese char + space
    if len(name) >= 3 and name[0] in STRAY_HEADER_CHARS and name[1] == ' ':
        return name[2:].strip()
    # Also handle '学 ' prefix (common in our data)
    if len(name) >= 3 and name[0] == '学' and name[1] == ' ':
        return name[2:].strip()
    # Handle just a single stray char without space
    if len(name) >= 2 and name[0] in STRAY_HEADER_CHARS:
        rest = name[1:].strip()
        # Only clean if the rest starts with a valid Chinese name
        if rest and ord(rest[0]) >= 0x4E00:
            return rest
    return name


def parse_inner_plan(json_data, subject_track="历史"):
    """Parse history/physics plan into structured records"""
    all_records = []
    for table in json_data:
        rows = table['rows']
        current_group_code = None

        for row in rows:
            if len(row) < 7:
                continue
            cells = []
            for c in row:
                cells.append((c or '').replace('\n', ' ').strip())

            col0, col1, col2, col3, col4, col5, col6 = cells[:7]

            # Skip header rows
            if 'רҵ' in col0 or 'רҵ' in col2:
                current_group_code = None
                continue

            if not col2 or not re.search(r'\d{2,}', col2):
                continue

            # Group code
            gc_match = re.search(r'(\d{3,})', col0)
            if gc_match:
                current_group_code = gc_match.group(1)

            if not current_group_code:
                continue

            # Major code
            mc_match = re.search(r'(\d{2,})', col2)
            if not mc_match:
                continue
            major_code = mc_match.group(1)

            # Major name (also clean stray PDF artifacts)
            major_name = clean_major_name(clean_text(col3))

            # Plan count
            plan_count = 0
            nums = re.findall(r'\d+', col4.replace(' ', ''))
            if nums:
                plan_count = int(nums[0])

            # Subject requirement
            subject_req = clean_text(col5) or '不限'

            all_records.append({
                'group_code': current_group_code,
                'major_code': major_code,
                'major_name': major_name,
                'plan_count': plan_count,
                'subject_requirement': subject_req,
                'subject_track': subject_track
            })

    return all_records


def parse_art_plan(json_data):
    """Parse art/sports plan"""
    all_records = []
    for table in json_data:
        rows = table['rows']
        current_group = None
        current_track = '艺体'

        for row in rows:
            if len(row) < 7:
                continue
            cells = []
            for c in row:
                cells.append((c or '').replace('\n', ' ').strip())

            col0, col1, col2, col3, col4, col5, col6 = cells[:7]

            if 'רҵ' in col0 or 'רҵ' in col2:
                current_group = None
                continue

            if not col2 or not re.search(r'\d{2,}', col2):
                continue

            # Detect track from the raw group text before extracting number
            if col0 and len(col0) >= 3:
                raw_group = col0
                num_match = re.search(r'(\d{3})', col0)
                if num_match:
                    current_group = num_match.group(1)
                # Determine track from group code or context
                if current_group == '227':
                    current_track = '美术'
                elif current_group == '228':
                    current_track = '体育'
                elif current_group == '229':
                    current_track = '编导'
                else:
                    current_track = '艺体'

            if not current_group:
                continue

            mc_match = re.search(r'(\d{2,})', col2)
            if not mc_match:
                continue
            major_code = mc_match.group(1)

            major_name = clean_major_name(clean_text(col3))

            plan_count = 0
            nums = re.findall(r'\d+', col4)
            if nums:
                plan_count = int(nums[0])

            subject_req = clean_text(col5) or '不限'

            all_records.append({
                'group_code': current_group,
                'major_code': major_code,
                'major_name': major_name,
                'plan_count': plan_count,
                'subject_requirement': subject_req,
                'subject_track': current_track
            })

    return all_records


def build_group_name(records):
    """Build group_name from records in a group"""
    lines = []
    for r in records:
        lines.append(f"{r['major_code']} {r['major_name']} {r['plan_count']}人")
    return '\n'.join(lines)


def main():
    # Load parsed PDF data
    base = 'C:/Users/wangm/AppData/Local/Temp'
    with open(f'{base}/history_plan.json', 'r', encoding='utf-8') as f:
        history_data = json.load(f)
    with open(f'{base}/physics_plan.json', 'r', encoding='utf-8') as f:
        physics_data = json.load(f)
    with open(f'{base}/art_plan.json', 'r', encoding='utf-8') as f:
        art_data = json.load(f)

    # Parse
    print("Parsing 历史类...")
    history_records = parse_inner_plan(history_data, "历史")
    h_total = sum(r['plan_count'] for r in history_records)
    print(f"  {len(history_records)} records, total: {h_total}人")

    print("Parsing 物理类...")
    physics_records = parse_inner_plan(physics_data, "物理")
    p_total = sum(r['plan_count'] for r in physics_records)
    print(f"  {len(physics_records)} records, total: {p_total}人")

    print("Parsing 艺体类...")
    art_records = parse_art_plan(art_data)
    a_total = sum(r['plan_count'] for r in art_records)
    print(f"  {len(art_records)} records, total: {a_total}人")

    # Connect to DB
    conn = sqlite3.connect('server/gaokao.db')
    conn.text_factory = str
    cursor = conn.cursor()

    # Delete existing 2026 data for 广财
    cursor.execute("DELETE FROM enrollment_plan WHERE school_code='10592' AND year=2026")
    print(f"\nDeleted existing 2026 data for 广东财经大学")

    # Prepare batch insert
    batch = "本科普通批"
    province = "广东"
    school_code = "10592"
    school_name = "广东财经大学"
    school_level = "普通本科"
    city = "广州"

    all_records = history_records + physics_records + art_records
    group_details = defaultdict(list)

    # Collect all records by group
    for r in all_records:
        group_code = school_code + r['group_code']
        group_details[group_code].append(r)

    # Remove duplicates
    for gc in group_details:
        seen = set()
        unique = []
        for r in group_details[gc]:
            key = (r['major_code'], r['major_name'])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        group_details[gc] = unique

    # Insert records
    inserted = 0
    for r in all_records:
        group_code = school_code + r['group_code']
        group_name = build_group_name(group_details[group_code])

        sql = """
            INSERT INTO enrollment_plan 
            (year, province, batch, school_code, school_name, group_code, group_name, 
             major_code, major_name, subject_requirement, subject_track, plan_count, school_level, city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql, (
            2026, province, batch, school_code, school_name, group_code, group_name,
            r['major_code'], r['major_name'], r['subject_requirement'], r['subject_track'],
            r['plan_count'], school_level, city
        ))
        inserted += 1

    conn.commit()

    # Verify
    cursor.execute(
        "SELECT SUM(plan_count), COUNT(*) FROM enrollment_plan WHERE school_code='10592' AND year=2026"
    )
    total, cnt = cursor.fetchone()
    print(f"\nInserted {inserted} records, total: {total}人, {cnt} rows")

    cursor.execute(
        "SELECT group_code, subject_track, SUM(plan_count) FROM enrollment_plan WHERE school_code='10592' AND year=2026 GROUP BY group_code ORDER BY group_code"
    )
    print("\n分组统计:")
    for gc, track, count in cursor.fetchall():
        print(f"  {gc} ({track}): {count}人")

    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
