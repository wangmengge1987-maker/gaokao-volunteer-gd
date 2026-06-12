from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from db.connection import get_connection
from models import (
    ExplainRequest,
    ExplainResponse,
    PlanImpactResponse,
    RankLookupRequest,
    RankLookupResponse,
    RecommendRequest,
    RecommendResponse,
    VolunteerItem,
)
from services.agent_service import explain_volunteer
from services.plan_analysis_service import get_impact_summary
from services.rank_service import score_to_rank
from services.recommend_service import recommend

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.joinpath("assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")


@app.get("/health")
def health():
    return {"status": "ok", "province": settings.province, "batch": settings.batch}


@app.post("/api/v1/rank/lookup", response_model=RankLookupResponse)
def rank_lookup(body: RankLookupRequest):
    if body.subject_track not in ("物理", "历史"):
        raise HTTPException(400, "subject_track 须为 物理 或 历史")
    result = score_to_rank(body.subject_track, body.score)
    if not result:
        raise HTTPException(404, "未找到对应位次，请确认分数与数据年份")
    return RankLookupResponse(
        score=body.score,
        rank=result["rank"],
        year=result["year"],
        subject_track=body.subject_track,
    )


@app.post("/api/v1/recommend", response_model=RecommendResponse)
def recommend_volunteers(body: RecommendRequest):
    if body.subject_track not in ("物理", "历史"):
        raise HTTPException(400, "subject_track 须为 物理 或 历史")

    student_rank = body.rank
    if student_rank is None:
        rank_result = score_to_rank(body.subject_track, body.score)
        if not rank_result:
            raise HTTPException(404, "无法换算位次")
        student_rank = rank_result["rank"]

    items = recommend(
        student_rank=student_rank,
        first_choice=body.subject_track,
        rechoices=body.rechoices,
        preferences=body.preferences,
        tier_counts=body.tier_counts,
        city_filter=body.city_filter,
    )

    return RecommendResponse(
        student_rank=student_rank,
        volunteers=[VolunteerItem(**{k: v for k, v in i.items() if k != "history" and k != "preference_score"}) for i in items],
    )


@app.post("/api/v1/explain", response_model=ExplainResponse)
async def explain(body: ExplainRequest):
    try:
        text = await explain_volunteer(body.volunteer, body.question)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    return ExplainResponse(explanation=text)


@app.get("/api/v1/plan/impact", response_model=PlanImpactResponse)
def plan_impact(subject_track: str = "物理", year_current: int = 2026, year_previous: int = 2025):
    if subject_track not in ("物理", "历史"):
        raise HTTPException(400, "subject_track 须为 物理 或 历史")

    impact = get_impact_summary(
        subject_track=subject_track,
        current_year=year_current,
        previous_year=year_previous,
    )

    from models import PlanChangeItem, PlanImpactSummary

    return PlanImpactResponse(
        summary=PlanImpactSummary(**impact["summary"]),
        details=[PlanChangeItem(**d) for d in impact["details"]],
        top_expansions=[PlanChangeItem(**d) for d in impact["top_expansions"]],
        top_contractions=[PlanChangeItem(**d) for d in impact["top_contractions"]],
    )


@app.post("/api/v1/plan/import")
def import_plan_csv(file_path: str):
    """
    Import 2026 enrollment plan data from CSV file.

    CSV must have columns:
    year,school_code,school_name,group_code,group_name,major_code,major_name,
    subject_requirement,subject_track,plan_count,school_level,city
    """
    import csv
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(404, f"File not found: {file_path}")

    conn = get_connection()
    try:
        count = 0
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
            if not cols:
                raise HTTPException(400, "Empty CSV")
            placeholders = ",".join("?" * len(cols))
            sql = f"INSERT OR REPLACE INTO enrollment_plan ({','.join(cols)}) VALUES ({placeholders})"
            for row in reader:
                values = tuple(row[c] for c in cols)
                conn.execute(sql, values)
                count += 1
        conn.commit()
        return {"status": "ok", "imported": count}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()


@app.get("/api/v1/plan/summary")
def plan_summary(subject_track: str = "物理"):
    """Quick summary: whether 2026 plans exist and what's the net change."""
    if subject_track not in ("物理", "历史"):
        raise HTTPException(400, "subject_track 须为 物理 或 历史")

    impact = get_impact_summary(subject_track=subject_track)
    return impact["summary"]


if __name__ == "__main__":
    import uvicorn
    from config import SERVER_PORT

    uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT)
