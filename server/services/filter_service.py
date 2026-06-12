def parse_subjects(first_choice: str, rechoices: list[str]) -> set[str]:
    """first_choice: 物理|历史; rechoices: 再选科目列表."""
    return {first_choice, *rechoices}


def subject_requirement_met(requirement: str | None, student_subjects: set[str]) -> bool:
    """Check if student meets major group subject requirement."""
    if not requirement or requirement.strip() in ("不限", "无"):
        return True
    required = {s.strip() for s in requirement.replace("/", ",").split(",") if s.strip()}
    return required.issubset(student_subjects)
