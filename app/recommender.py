from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


DATA_FILE = Path(__file__).parent / "data" / "colleges.csv"
YEAR_WEIGHTS = {2025: 0.5, 2024: 0.3, 2023: 0.2}

# 2026年广东省普通类（物理）录取最低分数线（省控线）
# 来源：广东省教育考试院 2026年6月24日
SCORE_LINE_2026 = {
    "本科批": 425,
    "特殊类型招生控制线": 539,
    "专科批": 200,
}

# 2026年一分一段表关键节点（物理类）
# 来源：广东省教育考试院 2026年6月25日
RANK_BRACKETS_2026 = {
    425: 275000,
    539: 110000,
    600: 60000,
    650: 20000,
    680: 5000,
}


@dataclass(frozen=True)
class Thresholds:
    rush: int = 3000
    stable: int = 5000
    secure: int = 12000


def _weighted(values: list[tuple[int, int]]) -> float:
    available = [(value, YEAR_WEIGHTS.get(year, 0.1)) for year, value in values]
    total = sum(weight for _, weight in available)
    return sum(value * weight for value, weight in available) / total


def _stddev(values: list[int]) -> float:
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _subject_matches(user_subjects: str, requirement: str) -> bool:
    # Handle "首选物理，再选不限" and "物理+不限" formats
    if "不限" in requirement:
        primary = "物理" if user_subjects.startswith("物") else "历史"
        return primary in requirement
    # Normalize both formats to short subject codes
    normalized = requirement
    for full, short in {"物理": "物", "历史": "史", "化学": "化", "生物": "生", "政治": "政", "地理": "地"}.items():
        normalized = normalized.replace(full, short)
    # Handle "首选物，再选化/生2选1" → extract subjects after "再选"
    if "再选" in normalized:
        normalized = normalized.split("再选", 1)[1]
    # Handle "化/生2选1" → split by "/" and take first part
    if "/" in normalized:
        parts = normalized.split("/")
        normalized = parts[0]
    # Handle remaining separators
    normalized = normalized.replace("、", "+").replace("，", "+")
    required = set(normalized.split("+"))
    selected = set(user_subjects)
    return required.issubset(selected)


def load_records() -> list[dict]:
    with DATA_FILE.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def recommend_colleges(
    user_score: int,
    user_rank: int,
    user_subjects: str,
    province: str,
    thresholds: Thresholds | None = None,
    college_region: str = "全国",
    exclude_program_types: list[str] | None = None,
) -> dict:
    """按三年加权位次推荐；位次越小越好。结果仅供模拟。"""
    thresholds = thresholds or Thresholds()
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    primary = "物理" if user_subjects.startswith("物") else "历史"

    exclude_types = set(exclude_program_types or [])
    for row in load_records():
        if row["province"] != province or row["subject_group"] != primary:
            continue
        if college_region != "全国" and row.get("college_province") and row["college_province"] != college_region:
            continue
        if exclude_types:
            college_name = row.get("college_name", "")
            school_type = row.get("school_type", "")
            if any(kw in college_name for kw in exclude_types) or any(kw in school_type for kw in exclude_types):
                continue
        if _subject_matches(user_subjects, row["subject_requirement"]):
            grouped[(row["college_code"], row["program_group"])].append(row)

    result = {"rush": [], "stable": [], "secure": []}
    candidates: list[dict] = []
    for rows in grouped.values():
        ranks = [(int(r["year"]), int(r["min_rank"])) for r in rows]
        scores = [(int(r["year"]), int(r["min_score"])) for r in rows]
        predicted_rank = round(_weighted(ranks))
        predicted_score = round(_weighted(scores))
        volatility = round(_stddev([v for _, v in ranks]))
        rank_gap = predicted_rank - user_rank

        latest = max(rows, key=lambda r: int(r["year"]))
        raw_history = [{"year": int(r["year"]), "score": int(r["min_score"]), "rank": int(r["min_rank"])} for r in rows]
        item = {
            "college_code": latest["college_code"],
            "college_name": latest["college_name"],
            "school_type": latest["school_type"],
            "college_province": latest.get("college_province", province),
            "city": latest["city"],
            "program_group": latest["program_group"],
            "subject_requirement": latest["subject_requirement"],
            "predicted_score": predicted_score,
            "predicted_rank": predicted_rank,
            "rank_gap": rank_gap,
            "volatility": volatility,
            "probability": 0,
            "history": sorted(raw_history, key=lambda item: item["year"], reverse=True),
        }
        candidates.append(item)

        if -thresholds.rush <= rank_gap < 0:
            item["probability"] = max(30, round(50 + rank_gap / thresholds.rush * 20))
            result["rush"].append(item)
        elif 0 <= rank_gap <= thresholds.stable:
            item["probability"] = min(82, round(70 + rank_gap / thresholds.stable * 12))
            result["stable"].append(item)
        elif thresholds.stable < rank_gap <= thresholds.secure:
            item["probability"] = min(97, round(90 + (rank_gap - thresholds.stable) / (thresholds.secure - thresholds.stable) * 7))
            result["secure"].append(item)

    # 模拟数据覆盖有限时，按考生位次自适应补齐每档最接近的院校，避免换分数后空白。
    used = {item["college_code"] for items in result.values() for item in items}
    tier_rules = {
        "rush": (0.88, lambda item: item["predicted_rank"] < user_rank),
        "stable": (1.02, lambda item: True),
        "secure": (1.15, lambda item: item["predicted_rank"] > user_rank),
    }
    probability_ranges = {"rush": (30, 50), "stable": (70, 82), "secure": (90, 97)}
    for tier in ("rush", "stable", "secure"):
        if len(result[tier]) >= 3:
            continue
        target_ratio, direction = tier_rules[tier]
        pool = [item for item in candidates if item["college_code"] not in used and direction(item)]
        if len(pool) < 3 - len(result[tier]):
            pool = [item for item in candidates if item["college_code"] not in used]
        pool.sort(key=lambda item: abs(item["predicted_rank"] - user_rank * target_ratio))
        needed = 3 - len(result[tier])
        low, high = probability_ranges[tier]
        for index, original in enumerate(pool[:needed]):
            item = original.copy()
            item["probability"] = max(low, high - index * 4)
            item["adaptive"] = True
            result[tier].append(item)
            used.add(item["college_code"])

    result["rush"].sort(key=lambda x: x["rank_gap"], reverse=True)
    result["stable"].sort(key=lambda x: x["rank_gap"])
    result["secure"].sort(key=lambda x: x["rank_gap"])
    result = {key: value[:5] for key, value in result.items()}

    # Determine 2026 score line reference
    if user_score >= SCORE_LINE_2026["特殊类型招生控制线"]:
        score_line_label = f"特控线{SCORE_LINE_2026['特殊类型招生控制线']}分"
    elif user_score >= SCORE_LINE_2026["本科批"]:
        score_line_label = f"本科线{SCORE_LINE_2026['本科批']}分"
    else:
        score_line_label = f"本科线{SCORE_LINE_2026['本科批']}分"

    return {
        "profile": {
            "province": province,
            "college_region": college_region,
            "subjects": user_subjects,
            "score": user_score,
            "rank": user_rank,
            "score_line_2026": SCORE_LINE_2026,
            "rank_brackets_2026": RANK_BRACKETS_2026,
            "score_line_label": score_line_label,
        },
        "summary": {key: len(value) for key, value in result.items()},
        "recommendations": result,
        "methodology": "2023—2025 三年最低位次按 20%/30%/50% 加权，位次为主、分数为辅。2026年院校投档线预计7月中下旬公布，当前参考2025年位次。",
        "disclaimer": "本系统所有数据及推荐结果仅供参考。高考志愿填报关乎未来，请务必以各省教育考试院及高校官网发布的最新官方政策、招生计划为准。建议结合多方渠道理性决策，祝广大考生金榜题名。",
    }
