from pydantic import BaseModel, Field


class RankLookupRequest(BaseModel):
    subject_track: str = Field(..., description="物理 或 历史")
    score: int = Field(..., ge=0, le=750)


class RankLookupResponse(BaseModel):
    score: int
    rank: int
    year: int
    subject_track: str


class RecommendRequest(BaseModel):
    score: int = Field(..., ge=0, le=750)
    subject_track: str = Field(..., description="物理 或 历史")
    rechoices: list[str] = Field(..., min_length=2, max_length=2, description="再选科目，如 ['化学','生物']")
    rank: int | None = Field(None, description="可选，若已知位次则跳过换算")
    preferences: dict | None = Field(default_factory=dict, description="cities, majors, school_levels")
    tier_counts: dict | None = Field(default_factory=lambda: {"冲": 8, "稳": 22, "保": 15})
    city_filter: str = Field(default="prefer", description="城市过滤模式: prefer(优先) / strict(仅限)")


class VolunteerItem(BaseModel):
    order: int
    tier: str
    school_code: str
    school_name: str
    group_code: str
    group_name: str | None
    city: str | None
    school_level: str | None
    plan_count: int
    subject_requirement: str | None
    ref_min_rank: int | None
    adjusted_rank: int | None = None
    plan_shift: int = 0
    student_rank: int
    confidence: float = 0.5
    evidence: dict
    major_names: str | None = None  # 该专业组包含的所有专业名称


class RecommendResponse(BaseModel):
    student_rank: int
    volunteers: list[VolunteerItem]
    disclaimer: str = "仅供参考，以广东省教育考试院及院校招生章程为准。"


class PlanChangeItem(BaseModel):
    school_code: str
    school_name: str
    group_code: str
    plan_previous: int
    plan_current: int
    change: int
    historical_rank: int | None = None
    historical_year: int | None = None
    cumulative_shift: int = 0
    adjusted_rank: int | None = None


class PlanImpactSummary(BaseModel):
    year_current: int
    year_previous: int
    subject_track: str
    total_schools_changed: int
    total_groups_changed: int
    total_expansion: int
    total_contraction: int
    net_change: int
    has_current_year_data: bool


class PlanImpactResponse(BaseModel):
    summary: PlanImpactSummary
    details: list[PlanChangeItem]
    top_expansions: list[PlanChangeItem]
    top_contractions: list[PlanChangeItem]


class ExplainRequest(BaseModel):
    volunteer: dict
    question: str | None = None


class ExplainResponse(BaseModel):
    explanation: str
