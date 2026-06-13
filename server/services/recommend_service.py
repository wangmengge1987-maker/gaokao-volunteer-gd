import re

from db.connection import get_connection
from config import settings
from services.filter_service import parse_subjects, subject_requirement_met
from services.plan_analysis_service import compute_cumulative_shifts


# ── 冲/稳/保 阈值（基于学校层次微调） ──
# 分析发现: 985学校波动大(中位数89%)，211/普本波动小(15%)
# 因此对高分段的冲/稳区间适当放宽
TIER_THRESHOLDS = {
    "冲": (-0.30, -0.10),
    "稳": (-0.10, 0.15),
    "保": (0.15, 0.50),
}

# 学校层次对应的额外浮动因子（波动越大，区间越宽）
LEVEL_VOLATILITY = {
    "985": 1.4,       # 高波动，扩大区间
    "211": 1.0,       # 基准
    "双一流": 1.1,
    "普通本科": 0.85,  # 低波动，缩小区间
}


def _tier_for_rank(student_rank: int, ref_rank: int | None,
                    school_level: str | None = None) -> str | None:
    """
    判断冲/稳/保，根据学校层次调整阈值。

    原理: 985学校年际位次波动大，同样的差距需要更宽松的判断；
          普通本科波动小，判断更严格。
    """
    if not ref_rank or ref_rank <= 0:
        return None

    factor = LEVEL_VOLATILITY.get(school_level, 1.0)
    ratio = (ref_rank - student_rank) / ref_rank

    # 根据学校层次动态调整阈值
    for tier, (lo, hi) in TIER_THRESHOLDS.items():
        adj_lo = lo * factor
        adj_hi = hi * factor
        if adj_lo <= ratio <= adj_hi:
            return tier

    # 超出范围
    if ratio < TIER_THRESHOLDS["冲"][0] * factor:
        return "难"
    if ratio > TIER_THRESHOLDS["保"][1] * factor:
        return "垫"
    return None


def _compute_ref_rank(hist_rows: list) -> tuple[int | None, float]:
    """
    改进的参考位次计算策略（基于分析发现的结论）。

    策略:
      1. 优先使用最近一年的位次（因为专业组内容每年可能变）
      2. 如果有多年的数据，使用加权平均（最近年份权重高）
      3. 加权公式: w1*rank1 + w2*rank2 + w3*rank3
         权重: 最近一年0.6, 前年0.3, 再前年0.1
      4. 同时返回 confidence 值（0~1），用于表示该参考的可信度

    Returns:
        (ref_rank, confidence)
        confidence based on: 数据年份数, 年际一致性, 计划偏差
    """
    valid = [(r["year"], r["min_rank"]) for r in hist_rows
             if r["min_rank"] and r["min_rank"] > 0]

    if not valid:
        return (None, 0.0)

    if len(valid) == 1:
        return (valid[0][1], 0.5)

    # 按年份排序（最近的在前面）
    valid.sort(key=lambda x: x[0], reverse=True)

    # 加权平均: 最近0.6, 前年0.3, 再前年0.1
    weights = [0.6, 0.3, 0.1]
    weighted_sum = 0
    total_weight = 0
    for i, (year, rank) in enumerate(valid):
        if i < len(weights):
            weighted_sum += rank * weights[i]
            total_weight += weights[i]

    if total_weight == 0:
        return (valid[0][1], 0.5)

    ref_rank = round(weighted_sum / total_weight)

    # 计算置信度: 年际一致性越高，置信度越高
    if len(valid) >= 2:
        ranks_only = [r for _, r in valid]
        max_rank = max(ranks_only)
        min_rank = min(ranks_only)
        # 一致性 = 1 - (max-min)/mean
        mean_rank = sum(ranks_only) / len(ranks_only)
        consistency = max(0, 1 - (max_rank - min_rank) / mean_rank)
        confidence = min(1.0, 0.3 + 0.3 * (len(valid) / 3) + 0.4 * consistency)
    else:
        confidence = 0.5

    return (ref_rank, confidence)


def _preference_score(row: dict, prefs: dict) -> float:
    score = 0.0
    cities = prefs.get("cities") or []
    majors = prefs.get("majors") or []
    levels = prefs.get("school_levels") or []

    if cities and row.get("city") in cities:
        score += 3
    if levels and row.get("school_level") in levels:
        score += 2
    if majors:
        # 同时匹配专业组名称和专业名称
        group_name = row.get("group_name") or ""
        major_names = row.get("major_names") or ""
        all_names = group_name + "|" + major_names
        matched = [m for m in majors if m in all_names]
        if matched:
            # 匹配的专业越多，分数越高
            score += 4 * len(matched)
    return score


def recommend(
    student_rank: int,
    first_choice: str,
    rechoices: list[str],
    preferences: dict | None = None,
    tier_counts: dict | None = None,
    city_filter: str = "prefer",
) -> list[dict]:
    """
    Generate 冲/稳/保 volunteer suggestions for 广东本科普通批.
    city_filter: "prefer"（优先显示）, "strict"（仅限偏好城市）
    Returns list of dicts with school/group info and tier label.
    """
    preferences = preferences or {}
    tier_counts = tier_counts or {"冲": 8, "稳": 22, "保": 15}
    subjects = parse_subjects(first_choice, rechoices)

    conn = get_connection()
    try:
        # 计算招生计划变动引起的位次偏移
        plan_shifts = compute_cumulative_shifts(first_choice)
        has_plan_shift = any(v != 0 for v in plan_shifts.values())

        # Filter by subject_track (物理/历史) — 3+1+2 separates competition pools
        plans = conn.execute(
            """
            SELECT p.school_code, p.school_name, p.group_code,
                   MIN(p.group_name) as group_name,
                   MIN(p.subject_requirement) as subject_requirement,
                   SUM(p.plan_count) as plan_count,
                   p.school_level, p.city,
                   GROUP_CONCAT(p.major_name, '|') as major_names
            FROM enrollment_plan p
            WHERE p.year = ? AND p.batch = ?
              AND p.plan_count > 0
              AND p.subject_track = ?
            GROUP BY p.school_code, p.group_code
            """,
            (settings.data_year, settings.batch, first_choice),
        ).fetchall()

        candidates: list[dict] = []
        for plan in plans:
            if not subject_requirement_met(plan["subject_requirement"], subjects):
                continue

            hist_rows = conn.execute(
                """
                SELECT year, min_score, min_rank, plan_count
                FROM admission_history
                WHERE school_code = ? AND group_code = ? AND subject_track = ?
                ORDER BY year DESC LIMIT 3
                """,
                (plan["school_code"], plan["group_code"], first_choice),
            ).fetchall()

            # ── 改进1: 加权多年代替单一年份 ──
            ref_rank, ref_confidence = _compute_ref_rank([dict(r) for r in hist_rows])

            # ── 改进2: 如果专业组无历史数据，尝试学校层面估计 ──
            if ref_rank is None:
                # 用该学校其他组的平均位次作为参考
                school_rows = conn.execute(
                    """
                    SELECT year, min_rank FROM admission_history
                    WHERE school_code = ? AND subject_track = ? AND batch = ?
                      AND min_rank IS NOT NULL AND min_rank > 0
                    ORDER BY year DESC LIMIT 5
                    """,
                    (plan["school_code"], first_choice, settings.batch),
                ).fetchall()
                if school_rows:
                    school_ranks = [r["min_rank"] for r in school_rows]
                    ref_rank = sum(school_ranks) // len(school_ranks)
                    ref_confidence = 0.3  # 学校层面估计，置信度较低
                    hist_rows = [dict(r) for r in school_rows]

            # 如果招生计划有变动，调整参考位次
            adjusted_ref_rank = ref_rank
            shift = 0
            if ref_rank and has_plan_shift:
                shift = plan_shifts.get((plan["school_code"], plan["group_code"]), 0)
                if shift != 0:
                    adjusted_ref_rank = ref_rank + shift

            # ── 改进3: 根据学校层次动态调整冲/稳/保阈值 ──
            tier = _tier_for_rank(student_rank, adjusted_ref_rank,
                                  school_level=plan["school_level"])
            has_major_pref = bool(preferences.get("majors"))
            if not has_major_pref and (not tier or tier in ("难", "垫")):
                # 无专业偏好时，太难或太保底的跳过
                continue
            tier = tier or (  # 补全 tier 标签
                "难" if adjusted_ref_rank and adjusted_ref_rank < student_rank else "垫"
            )

            # Clean group name: shorten verbose Excel descriptions
            group_name = plan["group_name"] or ""
            short_name = group_name.split("\n")[0].strip() if "\n" in group_name else group_name
            short_name = short_name.split("【")[0].strip() if "【" in short_name else short_name
            # Remove trailing parenthetical enrollment notes
            short_name = re.sub(r'\([^)]*(不招|只招|含：|培养模式|中外合作).*$', '', short_name).strip()
            short_name = re.sub(r'\s*\([^)]{0,5}\)\s*$', '', short_name).strip()  # trailing short parens

            item = {
                "school_code": plan["school_code"],
                "school_name": plan["school_name"],
                "group_code": plan["group_code"],
                "group_name": short_name,
                "city": plan["city"],
                "school_level": plan["school_level"],
                "plan_count": plan["plan_count"],
                "subject_requirement": plan["subject_requirement"],
                "major_names": plan["major_names"],
                "tier": tier,
                "ref_min_rank": ref_rank,
                "adjusted_rank": adjusted_ref_rank,
                "plan_shift": shift,
                "student_rank": student_rank,
                "confidence": round(ref_confidence, 2),
                "history": [dict(r) for r in hist_rows],
                "preference_score": _preference_score(
                    {"city": plan["city"], "school_level": plan["school_level"],
                     "group_name": short_name, "major_names": plan["major_names"]},
                    preferences,
                ),
                "evidence": {
                    "data_year": settings.data_year,
                    "ref_min_rank": ref_rank,
                    "adjusted_rank": adjusted_ref_rank,
                    "plan_shift_applied": shift != 0 if ref_rank else False,
                    "confidence": round(ref_confidence, 2),
                    "history_years": [r["year"] for r in hist_rows],
                },
            }
            candidates.append(item)

        # ── 城市过滤 ──
        preferred_cities = preferences.get("cities") or []
        if city_filter == "strict" and preferred_cities:
            filtered = [c for c in candidates if c.get("city") in preferred_cities]
            if filtered:  # 有结果才过滤，避免空结果
                candidates = filtered

        if has_major_pref:
            # ── 专业偏好模式：优先展示匹配专业，按位次差距排序 ──
            for c in candidates:
                # 给每个候选计算"位次差距比率"，用于排序
                ref = c.get("ref_min_rank") or 0
                c["_rank_gap_ratio"] = (c["student_rank"] - ref) / max(ref, 1) if ref > 0 else 999

            # 排序：匹配专业且冲/稳的最优先 → 匹配专业的其他 → 不匹配的按原逻辑
            tier_priority = {"冲": 0, "稳": 1, "难": 2, "保": 3, "垫": 4}
            candidates.sort(key=lambda x: (
                0 if x["preference_score"] > 0 and x.get("tier") in ("冲", "稳") else
                1 if x["preference_score"] > 0 else 2,
                tier_priority.get(x.get("tier", ""), 5),
                abs(x.get("_rank_gap_ratio", 999)),
            ))

            result = candidates[: settings.max_volunteers]
            for i, item in enumerate(result):
                item["order"] = i + 1
        else:
            # ── 无专业偏好：按原逻辑分冲/稳/保 ──
            by_tier: dict[str, list] = {"冲": [], "稳": [], "保": []}
            for c in candidates:
                by_tier[c["tier"]].append(c)

            for tier in by_tier:
                by_tier[tier].sort(key=lambda x: (-x["preference_score"], x["ref_min_rank"] or 999999))

            result: list[dict] = []
            order = 1
            for tier in ("冲", "稳", "保"):
                for item in by_tier[tier][: tier_counts.get(tier, 0)]:
                    item["order"] = order
                    order += 1
                    result.append(item)

        return result[: settings.max_volunteers]
    finally:
        conn.close()
