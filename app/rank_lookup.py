from __future__ import annotations

import csv
import re
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"
OFFICIAL_SOURCE_2026 = "https://eea.gd.gov.cn/ptgk/content/post_4916165.html"


def _all_rank_files() -> list[tuple[int, Path]]:
    """返回所有年份的 (year, path)，按年份降序"""
    candidates: list[tuple[int, Path]] = []
    for path in DATA_DIR.glob("score_rank_*.csv"):
        match = re.search(r"(20\d{2})", path.stem)
        if match:
            candidates.append((int(match.group(1)), path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def _latest_rank_file() -> tuple[int, Path]:
    candidates = _all_rank_files()
    if not candidates:
        raise FileNotFoundError("未导入一分一段数据")
    return candidates[0]


def _read_rank_file(path: Path, column: str) -> dict[int, int]:
    """读取一个rank CSV文件，返回 {score: rank} 映射"""
    rows: dict[int, int] = {}
    with path.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get(column):
                rows[int(row["score"])] = int(row[column])
    return rows


def _lookup_in_rows(rows: dict[int, int], score: int) -> int | None:
    """在{score: rank}映射中查找给定分数的最佳匹配位次"""
    if not rows:
        return None
    if score in rows:
        return rows[score]
    if score > max(rows):
        return rows[max(rows)]
    if score < min(rows):
        return rows[min(rows)]
    nearest = min(rows, key=lambda value: abs(value - score))
    return rows[nearest]


def lookup_rank(score: int, primary: str, province: str = "广东") -> dict:
    """（单年）返回最近一年的位次（若最新年份无对应科目数据则向前查找）"""
    if province != "广东":
        return {"available": False, "message": f"暂未导入{province}的一分一段表"}

    column = "physics_rank" if primary == "物" else "history_rank"
    for year, path in _all_rank_files():
        rows = _read_rank_file(path, column)
        rank = _lookup_in_rows(rows, score)
        if rank is not None:
            is_current = year == 2026
            return {
                "available": True,
                "rank": rank,
                "score": score,
                "primary": "物理" if primary == "物" else "历史",
                "year": year,
                "is_current": is_current,
                "label": f"{year}年官方参考位次" if not is_current else "2026年官方位次",
                "message": "" if is_current else "2026年夏季高考一分一段表尚未发布，当前采用最近一期官方数据作参考。",
                "source": OFFICIAL_SOURCE_2026 if is_current else path.name,
            }

    return {"available": False, "message": "历史类一分一段数据暂未收录" if primary == "史" else f"暂未收录{primary}类一分一段数据"}


def lookup_rank_all_years(score: int, primary: str, province: str = "广东") -> dict:
    """返回2023-2026四年位次"""
    if province != "广东":
        return {"available": False, "message": f"暂未导入{province}的一分一段表"}

    column = "physics_rank" if primary == "物" else "history_rank"
    files = _all_rank_files()

    years_data = []
    for year, path in files:
        rows = _read_rank_file(path, column)
        if rows:
            rank = _lookup_in_rows(rows, score)
            if rank is not None:
                years_data.append({
                    "year": year,
                    "rank": rank,
                    "is_current": year == max(f[0] for f in files),
                })

    if not years_data:
        return {"available": False, "message": f"暂未收录{primary}类一分一段数据"}

    return {
        "available": True,
        "score": score,
        "primary": "物理" if primary == "物" else "历史",
        "province": province,
        "years": years_data,
        "source": OFFICIAL_SOURCE_2026,
    }
