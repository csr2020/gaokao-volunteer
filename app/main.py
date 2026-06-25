from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .recommender import Thresholds, recommend_colleges
from .rank_lookup import lookup_rank, lookup_rank_all_years


BASE_DIR = Path(__file__).parent
app = FastAPI(title="2026 高考志愿推荐模拟系统", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path in ("/",) or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class RecommendationRequest(BaseModel):
    province: str = "广东"
    college_region: str = "全国"
    subjects: str = Field(min_length=2, max_length=3, examples=["物化生"])
    score: int = Field(ge=0, le=750)
    rank: int = Field(gt=0, le=1_000_000)
    rush_gap: int = Field(default=3000, ge=500, le=30000)
    stable_gap: int = Field(default=5000, ge=1000, le=50000)
    secure_gap: int = Field(default=12000, ge=2000, le=100000)
    exclude_program_types: list[str] = Field(default_factory=list)

    @field_validator("subjects")
    @classmethod
    def validate_subjects(cls, value: str) -> str:
        if value[0] not in "物史" or len(set(value)) != len(value):
            raise ValueError("选科须以‘物’或‘史’开头，且科目不能重复")
        return value


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data_mode": "real", "years": "2023-2025", "records": 9173, "colleges": 1002, "rank_source": "2026官方一分一段"}


@app.get("/api/rank")
def rank(score: int, primary: str = "物", province: str = "广东") -> dict:
    if not 0 <= score <= 750 or primary not in {"物", "史"}:
        raise HTTPException(status_code=422, detail="分数或首选科目不正确")
    return lookup_rank(score, primary, province)


@app.get("/api/rank/all")
def rank_all(score: int, primary: str = "物", province: str = "广东") -> dict:
    """返回2023-2026四年的一分一段位次"""
    if not 0 <= score <= 750 or primary not in {"物", "史"}:
        raise HTTPException(status_code=422, detail="分数或首选科目不正确")
    return lookup_rank_all_years(score, primary, province)


@app.post("/api/recommendations")
def recommendations(payload: RecommendationRequest) -> dict:
    if payload.stable_gap >= payload.secure_gap:
        raise HTTPException(status_code=422, detail="保底范围必须大于稳妥范围")
    return recommend_colleges(
        payload.score,
        payload.rank,
        payload.subjects,
        payload.province,
        Thresholds(payload.rush_gap, payload.stable_gap, payload.secure_gap),
        payload.college_region,
        payload.exclude_program_types,
    )
