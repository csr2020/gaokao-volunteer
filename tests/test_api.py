from fastapi.testclient import TestClient

from app.main import app
from app.rank_lookup import lookup_rank
from app.recommender import recommend_colleges


client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok", "data_mode": "mock"}


def test_recommendation_contract():
    response = client.post("/api/recommendations", json={
        "province": "广东", "college_region": "全国", "subjects": "物化生", "score": 552, "rank": 78904,
        "rush_gap": 3000, "stable_gap": 5000, "secure_gap": 12000,
    })
    assert response.status_code == 200
    body = response.json()
    assert set(body["recommendations"]) == {"rush", "stable", "secure"}
    assert all(3 <= body["summary"][tier] <= 5 for tier in ("rush", "stable", "secure"))
    assert "模拟数据" in body["disclaimer"]


def test_invalid_thresholds():
    response = client.post("/api/recommendations", json={
        "province": "广东", "subjects": "物化生", "score": 552, "rank": 68000,
        "stable_gap": 12000, "secure_gap": 5000,
    })
    assert response.status_code == 422


def test_official_reference_rank_lookup():
    response = client.get("/api/rank?score=552&primary=物&province=广东")
    assert response.status_code == 200
    body = response.json()
    assert body["rank"] == 78904
    assert body["year"] == 2025
    assert body["is_current"] is False


def test_every_score_receives_three_tiers_for_physics_and_history():
    for primary, subjects in (("物", "物化生"), ("史", "史政地")):
        for score in range(0, 751):
            rank = lookup_rank(score, primary)["rank"]
            body = recommend_colleges(score, rank, subjects, "广东", college_region="全国")
            assert all(body["summary"][tier] >= 3 for tier in ("rush", "stable", "secure")), (primary, score, body["summary"])
