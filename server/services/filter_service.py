def parse_subjects(first_choice: str, rechoices: list[str]) -> set[str]:
    """first_choice: 物理|历史; rechoices: 再选科目列表."""
    return {first_choice, *rechoices}


import re


def subject_requirement_met(requirement: str | None, student_subjects: set[str]) -> bool:
    """Check if student meets major group subject requirement."""
    if not requirement or requirement.strip() in ("不限", "无"):
        return True
    # 支持逗号、斜杠、顿号、"和" 作为分隔符
    required = {s.strip() for s in re.split(r"[,，、/和]+", requirement) if s.strip()}
    return required.issubset(student_subjects)
