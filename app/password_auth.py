"""密码验证、次数管理与管理模块。"""
from __future__ import annotations

import json
import random
import threading
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PASSWORDS_PATH = DATA_DIR / "passwords.json"

_lock = threading.Lock()
_store: dict[str, dict] | None = None
_MAX_USES = 10
_WARN_THRESHOLD = 3


def _ensure_store() -> None:
    """确保密码文件存在，不存在则自动生成。"""
    if not PASSWORDS_PATH.exists():
        pool = random.sample(range(1_000_000), 10000)
        data = {f"{n:06d}": {"remaining": _MAX_USES} for n in pool}
        PASSWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PASSWORDS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _load() -> dict[str, dict]:
    global _store
    if _store is None:
        _ensure_store()
        raw = PASSWORDS_PATH.read_text(encoding="utf-8")
        _store = json.loads(raw)
    return _store


def _save() -> None:
    global _store
    if _store is not None:
        PASSWORDS_PATH.write_text(
            json.dumps(_store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ── 公共 API ──────────────────────────────────────


def validate_password(password: str) -> dict:
    """验证密码并扣减次数。返回 {'valid': bool, 'remaining': int, 'message': str}"""
    with _lock:
        store = _load()
        entry = store.get(password)

        if entry is None:
            return {
                "valid": False,
                "remaining": 0,
                "message": "密码无效，请检查后重试。如需购买请联系微信 micle_chen。",
            }

        remaining = entry["remaining"]

        if remaining <= 0:
            return {
                "valid": False,
                "remaining": 0,
                "message": "该密码已用完所有次数，请联系微信 micle_chen 购买新密码。",
            }

        entry["remaining"] = remaining - 1
        remaining -= 1
        _save()

        result = {"valid": True, "remaining": remaining}

        if remaining < _WARN_THRESHOLD:
            result["message"] = f"密码剩余 {remaining} 次，次数不足请及时联系微信 micle_chen 购买。"
        elif remaining == _WARN_THRESHOLD:
            result["message"] = f"密码剩余 {remaining} 次，请留意剩余次数。"
        else:
            result["message"] = ""

        return result


def check_password(password: str) -> dict:
    """检查密码状态（不扣减次数）。"""
    with _lock:
        store = _load()
        entry = store.get(password)
        if entry is None:
            return {"valid": False, "remaining": 0, "message": "密码无效"}
        remaining = entry["remaining"]
        if remaining <= 0:
            return {"valid": False, "remaining": 0, "message": "该密码已用完所有次数，请联系微信 micle_chen 购买新密码。"}
        msg = f"密码剩余 {remaining} 次"
        if remaining < _WARN_THRESHOLD:
            msg += "，次数不足请及时联系微信 micle_chen 购买。"
        return {"valid": True, "remaining": remaining, "message": msg}


# ── 管理 API ─────────────────────────────────────


def admin_stats() -> dict:
    """返回密码使用统计概览。"""
    with _lock:
        store = _load()
    total = len(store)
    active = sum(1 for e in store.values() if e["remaining"] > 0)
    exhausted = sum(1 for e in store.values() if e["remaining"] <= 0)
    sold = sum(1 for e in store.values() if e.get("owner"))
    remaining_all = sum(e["remaining"] for e in store.values())
    return {
        "total": total,
        "active": active,
        "exhausted": exhausted,
        "sold": sold,
        "remaining_all": remaining_all,
    }


def admin_list_passwords(page: int = 1, page_size: int = 50, filter_mode: str = "all") -> dict:
    """分页列出密码。filter_mode: all / active / exhausted / sold / unsold"""
    with _lock:
        store = _load()
    items = []
    for pwd, entry in store.items():
        items.append({
            "password": pwd,
            "remaining": entry["remaining"],
            "owner": entry.get("owner", ""),
            "sold_at": entry.get("sold_at", ""),
            "notes": entry.get("notes", ""),
        })

    if filter_mode == "active":
        items = [i for i in items if i["remaining"] > 0]
    elif filter_mode == "exhausted":
        items = [i for i in items if i["remaining"] <= 0]
    elif filter_mode == "sold":
        items = [i for i in items if i["owner"]]
    elif filter_mode == "unsold":
        items = [i for i in items if not i["owner"]]

    items.sort(key=lambda x: (0 if x["owner"] else 1, x["remaining"]))
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {"items": items[start:end], "total": total, "page": page, "page_size": page_size}


def admin_set_owner(password: str, owner: str, notes: str = "") -> dict:
    """标记密码为已售（设置购买者）。"""
    with _lock:
        store = _load()
        if password not in store:
            return {"success": False, "message": "密码不存在"}
        from datetime import datetime
        store[password]["owner"] = owner
        store[password]["sold_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if notes:
            store[password]["notes"] = notes
        _save()
    return {"success": True, "message": f"已标记密码 {password} → {owner}"}


def admin_reset_password(password: str, remaining: int = _MAX_USES) -> dict:
    """重置密码剩余次数（例如续费后充值）。"""
    with _lock:
        store = _load()
        if password not in store:
            return {"success": False, "message": "密码不存在"}
        store[password]["remaining"] = remaining
        _save()
    return {"success": True, "message": f"密码 {password} 已重置为 {remaining} 次"}


def admin_generate_additional(count: int = 1000) -> dict:
    """补充生成新密码（确保不重复）。"""
    with _lock:
        store = _load()
        existing = set(store.keys())
        needed = count
        new_pwds = []
        while needed > 0:
            pool = random.sample(range(1_000_000), min(needed * 2, 100000))
            for n in pool:
                pwd = f"{n:06d}"
                if pwd not in existing:
                    existing.add(pwd)
                    store[pwd] = {"remaining": _MAX_USES}
                    new_pwds.append(pwd)
                    needed -= 1
                    if needed == 0:
                        break
        _save()
    return {"success": True, "generated": len(new_pwds), "total": len(store)}


def reload_store() -> None:
    """重新从磁盘加载密码数据。"""
    global _store
    with _lock:
        _store = None
        _load()
