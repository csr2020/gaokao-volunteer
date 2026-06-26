from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .recommender import Thresholds, recommend_colleges
from .rank_lookup import lookup_rank, lookup_rank_all_years
from .password_auth import (validate_password, check_password as check_password_auth,
                            admin_stats, admin_list_passwords, admin_set_owner,
                            admin_reset_password, admin_generate_additional)


BASE_DIR = Path(__file__).parent
app = FastAPI(title="2026 高考志愿推荐模拟系统", version="2.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path in ("/",) or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class RecommendationRequest(BaseModel):
    password: str = Field(min_length=6, max_length=6, examples=["123456"])
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
    # 验证密码并扣减次数
    auth = validate_password(payload.password)
    if not auth["valid"]:
        raise HTTPException(status_code=403, detail=auth["message"])
    result = recommend_colleges(
        payload.score,
        payload.rank,
        payload.subjects,
        payload.province,
        Thresholds(payload.rush_gap, payload.stable_gap, payload.secure_gap),
        payload.college_region,
        payload.exclude_program_types,
    )
    result["password_remaining"] = auth["remaining"]
    result["password_message"] = auth["message"]
    return result


@app.post("/api/password/check")
def check_password_ep(password: str) -> dict:
    """检查密码状态（不扣减次数）。"""
    return check_password_auth(password)


# ── 管理后台 API ─────────────────────────────────


@app.get("/api/admin/stats")
def admin_stats_ep(access: str = "") -> dict:
    if access != "admin2026":
        raise HTTPException(status_code=403, detail="无权限")
    return admin_stats()


@app.get("/api/admin/passwords")
def admin_passwords_ep(page: int = 1, page_size: int = 50, filter_mode: str = "all", access: str = "") -> dict:
    if access != "admin2026":
        raise HTTPException(status_code=403, detail="无权限")
    return admin_list_passwords(page, page_size, filter_mode)


@app.post("/api/admin/set-owner")
def admin_set_owner_ep(password: str, owner: str, notes: str = "", access: str = "") -> dict:
    if access != "admin2026":
        raise HTTPException(status_code=403, detail="无权限")
    return admin_set_owner(password, owner, notes)


@app.post("/api/admin/reset-password")
def admin_reset_password_ep(password: str, remaining: int = 10, access: str = "") -> dict:
    if access != "admin2026":
        raise HTTPException(status_code=403, detail="无权限")
    return admin_reset_password(password, remaining)


@app.post("/api/admin/generate")
def admin_generate_ep(count: int = 1000, access: str = "") -> dict:
    if access != "admin2026":
        raise HTTPException(status_code=403, detail="无权限")
    return admin_generate_additional(count)


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "admin.html")
