"""
招生计划变化影响分析服务

核心逻辑（平行志愿下的位次漂移模型）:
  在广东平行志愿模式下，考生按位次排队投档。
  当某校扩招 ΔP 人时，该校录取位次下移（更容易进），
  同时下游所有学校的录取位次也同步下移 ΔP（竞争池缩小）。
  反之，缩招使录取位次上移。

  公式: adjusted_min_rank = historical_min_rank + cumulative_shift
  其中 cumulative_shift = Σ(ΔP_i) 对所有排位更高的学校/专业组
"""

from collections import defaultdict
from typing import Any

from db.connection import get_connection


def get_plan_changes(current_year: int = 2026, previous_year: int = 2025,
                     batch: str = "本科普通批") -> list[dict]:
    """
    计算各学校/专业组当年与往年的招生计划变化 ΔP。

    Returns:
        [{
            "school_code", "school_name", "group_code", "subject_track",
            "plan_previous", "plan_current", "change"
        }, ...]
    """
    conn = get_connection()
    try:
        # 获取当年的计划（如果已导入）
        current_plans = conn.execute(
            """
            SELECT school_code, school_name, group_code, subject_track,
                   SUM(plan_count) AS total_plan
            FROM enrollment_plan
            WHERE year = ? AND batch = ?
            GROUP BY school_code, group_code, subject_track
            """,
            (current_year, batch),
        ).fetchall()
        current_map = {
            (r["school_code"], r["group_code"], r["subject_track"]): r["total_plan"]
            for r in current_plans
        }

        # 获取往年的计划
        previous_plans = conn.execute(
            """
            SELECT school_code, school_name, group_code, subject_track,
                   SUM(plan_count) AS total_plan
            FROM enrollment_plan
            WHERE year = ? AND batch = ?
            GROUP BY school_code, group_code, subject_track
            """,
            (previous_year, batch),
        ).fetchall()
        previous_map = {
            (r["school_code"], r["group_code"], r["subject_track"]): {
                "school_name": r["school_name"],
                "total_plan": r["total_plan"],
            }
            for r in previous_plans
        }

        results = []
        # 遍历所有往年有的以及当年新增的
        all_keys = set(current_map.keys()) | set(previous_map.keys())

        for key in sorted(all_keys):
            school_code, group_code, subject_track = key
            cur = current_map.get(key, 0)
            prev_entry = previous_map.get(key, {})
            prev = prev_entry.get("total_plan", 0) if prev_entry else 0
            school_name = prev_entry.get("school_name", "") if prev_entry else ""

            # 如果当年有且往年没有，找当年的学校名
            if not school_name and key in current_map:
                for r in current_plans:
                    if (r["school_code"], r["group_code"], r["subject_track"]) == key:
                        school_name = r["school_name"]
                        break

            change = (cur or 0) - (prev or 0)
            results.append({
                "school_code": school_code,
                "school_name": school_name,
                "group_code": group_code,
                "subject_track": subject_track,
                "plan_previous": prev or 0,
                "plan_current": cur or 0,
                "change": change,
            })

        return results
    finally:
        conn.close()


def compute_cumulative_shifts(
    subject_track: str,
    plan_changes: list[dict] | None = None,
    current_year: int = 2026,
    previous_year: int = 2025,
    batch: str = "本科普通批",
) -> dict[tuple[str, str], int]:
    """
    按历史录取位次排序，计算每个（学校, 专业组）的累积计划变动偏移量。

    安全保护：如果当前年份的数据量远少于往年（例如专业组编码完全不同），
    则返回空结果，避免年际数据不匹配导致错误偏移。

    Returns:
        {(school_code, group_code): cumulative_shift, ...}
    """
    conn = get_connection()
    try:
        if plan_changes is None:
            plan_changes = get_plan_changes(current_year, previous_year, batch)

        # 只取当年有计划或有变化的记录
        active_changes = [
            pc for pc in plan_changes
            if pc["subject_track"] == subject_track
        ]

        # ── 安全检查：两年数据结构是否可比 ──
        # 如果当前年份有数据的组数量远少于往年，说明数据可能不完全
        # 或专业组编码体系已变更，此时不应应用计划偏移
        prev_groups = set()
        curr_groups = set()
        for pc in active_changes:
            key = (pc["school_code"], pc["group_code"])
            if pc["plan_previous"] > 0:
                prev_groups.add(key)
            if pc["plan_current"] > 0:
                curr_groups.add(key)

        # 计算「匹配率」：同时存在于两年中的组数量
        matched = prev_groups & curr_groups
        total_prev = len(prev_groups)
        total_curr = len(curr_groups)

        # 如果往年的组超过 30% 在当年找不到对应，说明数据结构不可比
        if total_prev > 0 and len(matched) / total_prev < 0.7:
            return {}
        # 如果当年的组超过 30% 在往年找不到对应，说明数据结构不可比
        if total_curr > 0 and len(matched) / total_curr < 0.7:
            return {}

        # 获取每个专业组的历史参考位次（取最近3年最低位次中的最小值）
        ref_ranks: dict[tuple[str, str], int] = {}
        for pc in active_changes:
            key = (pc["school_code"], pc["group_code"])
            rows = conn.execute(
                """
                SELECT min_rank FROM admission_history
                WHERE school_code = ? AND group_code = ?
                  AND subject_track = ? AND batch = ?
                  AND min_rank IS NOT NULL AND min_rank > 0
                ORDER BY year DESC LIMIT 3
                """,
                (pc["school_code"], pc["group_code"], subject_track, batch),
            ).fetchall()
            ranks = [r["min_rank"] for r in rows if r["min_rank"]]
            if ranks:
                ref_ranks[key] = min(ranks)  # 取最优（最小）位次

        # 按历史位次排序（位次越小越靠前）
        # 没有历史位次的放到最后
        sorted_items = sorted(
            active_changes,
            key=lambda x: ref_ranks.get((x["school_code"], x["group_code"]), 99999999),
        )

        # 计算累积偏移
        cumulative = 0
        shifts: dict[tuple[str, str], int] = {}

        for item in sorted_items:
            key = (item["school_code"], item["group_code"])
            shifts[key] = cumulative
            cumulative += item["change"]

        return shifts
    finally:
        conn.close()


def get_adjusted_rank(
    school_code: str,
    group_code: str,
    historical_rank: int | None,
    subject_track: str,
) -> dict[str, Any]:
    """
    根据计划变动调整历史录取位次。

    Returns:
        {
            "historical_rank": original rank,
            "cumulative_shift": adjustment value,
            "adjusted_rank": adjusted rank (or None if no historical rank),
            "has_plan_change_data": whether 2026 plan data is available,
        }
    """
    if historical_rank is None:
        return {
            "historical_rank": None,
            "cumulative_shift": 0,
            "adjusted_rank": None,
            "has_plan_change_data": False,
        }

    shifts = compute_cumulative_shifts(subject_track)
    key = (school_code, group_code)
    cumulative_shift = shifts.get(key, 0)

    has_data = any(v != 0 for v in shifts.values())

    return {
        "historical_rank": historical_rank,
        "cumulative_shift": cumulative_shift,
        "adjusted_rank": historical_rank + cumulative_shift if cumulative_shift != 0 else historical_rank,
        "has_plan_change_data": has_data,
    }


def get_impact_summary(
    subject_track: str = "物理",
    current_year: int = 2026,
    previous_year: int = 2025,
) -> dict[str, Any]:
    """
    生成招生计划变动的总体影响报告。

    Returns:
        {
            "summary": {
                "total_schools_changed": N,
                "total_expansion": sum of positive changes,
                "total_contraction": sum of negative changes,
                "net_change": net change,
                "has_current_year_data": bool,
            },
            "details": [{school, group, plan_prev, plan_cur, change, rank_impact}, ...],
            "top_expansions": [...],
            "top_contractions": [...],
        }
    """
    conn = get_connection()
    try:
        changes = get_plan_changes(current_year, previous_year)
        filtered = [c for c in changes if c["subject_track"] == subject_track]

        shifts = compute_cumulative_shifts(subject_track, filtered, current_year, previous_year)

        # 获取历史位次
        details = []
        total_expansion = 0
        total_contraction = 0
        schools_changed = set()

        for c in filtered:
            key = (c["school_code"], c["group_code"])
            shift = shifts.get(key, 0)

            # 找到对应的历史位次
            rows = conn.execute(
                """
                SELECT min_rank, year FROM admission_history
                WHERE school_code = ? AND group_code = ?
                  AND subject_track = ? AND batch = ?
                  AND min_rank IS NOT NULL AND min_rank > 0
                ORDER BY year DESC LIMIT 1
                """,
                (c["school_code"], c["group_code"], subject_track, "本科普通批"),
            ).fetchall()
            hist_rank = rows[0]["min_rank"] if rows else None
            hist_year = rows[0]["year"] if rows else None

            if c["change"] > 0:
                total_expansion += c["change"]
                schools_changed.add(c["school_code"])
            elif c["change"] < 0:
                total_contraction += c["change"]
                schools_changed.add(c["school_code"])

            details.append({
                "school_code": c["school_code"],
                "school_name": c["school_name"],
                "group_code": c["group_code"],
                "plan_previous": c["plan_previous"],
                "plan_current": c["plan_current"],
                "change": c["change"],
                "historical_rank": hist_rank,
                "historical_year": hist_year,
                "cumulative_shift": shift,
                "adjusted_rank": (hist_rank + shift) if (hist_rank and shift) else hist_rank,
            })

        # 排序：按变动绝对值降序
        details.sort(key=lambda x: abs(x["change"]), reverse=True)

        # 最大扩招/缩招
        top_expansions = [d for d in details if d["change"] > 0][:10]
        top_contractions = [d for d in details if d["change"] < 0][:10]

        has_data = any(d["change"] != 0 for d in details)

        return {
            "summary": {
                "year_current": current_year,
                "year_previous": previous_year,
                "subject_track": subject_track,
                "total_schools_changed": len(schools_changed),
                "total_groups_changed": sum(1 for d in details if d["change"] != 0),
                "total_expansion": total_expansion,
                "total_contraction": total_contraction,
                "net_change": total_expansion + total_contraction,
                "has_current_year_data": has_data,
            },
            "details": details[:30],  # 只返回前30条
            "top_expansions": top_expansions,
            "top_contractions": top_contractions,
        }
    finally:
        conn.close()
