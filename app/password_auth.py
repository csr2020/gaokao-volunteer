"""密码验证、次数管理、备份与管理模块。"""
from __future__ import annotations

import json
import random
import sys
import threading
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PASSWORDS_PATH = DATA_DIR / "passwords.json"
SEED_PATH = DATA_DIR / "passwords_seed.json"
BACKUP_DIR = DATA_DIR / "backups"

_lock = threading.Lock()
_store: dict[str, dict] | None = None
_MAX_USES = 10
_WARN_THRESHOLD = 3
_MAX_BACKUPS = 200
_last_backup_ts: float = 0  # 防止同一秒写太多备份


def _log(msg: str) -> None:
    print(f"[password_auth] {msg}", file=sys.stderr)


def _ensure_store() -> None:
    """确保密码文件存在：优先从种子文件复制，否则自动生成。"""
    if PASSWORDS_PATH.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SEED_PATH.exists():
        _log("从 passwords_seed.json 初始化密码…")
        PASSWORDS_PATH.write_text(SEED_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        _log("已从种子文件复制")
    else:
        _log("passwords.json 不存在，正在自动生成 10000 个密码…")
        pool = random.sample(range(1_000_000), 10000)
        data = {f"{n:06d}": {"remaining": _MAX_USES} for n in pool}
        PASSWORDS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        _log("密码文件已生成")


def _load() -> dict[str, dict]:
    global _store
    if _store is not None:
        return _store
    _ensure_store()
    try:
        raw = PASSWORDS_PATH.read_text(encoding="utf-8")
        _store = json.loads(raw)
        _log(f"已加载 {len(_store)} 个密码")
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"读取密码文件失败 ({exc})，正在重新生成…")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SEED_PATH.exists():
            _store = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        else:
            pool = random.sample(range(1_000_000), 10000)
            _store = {f"{n:06d}": {"remaining": _MAX_USES} for n in pool}
        PASSWORDS_PATH.write_text(json.dumps(_store, ensure_ascii=False), encoding="utf-8")
        _log("已重新生成密码文件")
    return _store


def _save() -> None:
    global _store
    if _store is not None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            content = json.dumps(_store, ensure_ascii=False, indent=2)
            PASSWORDS_PATH.write_text(content, encoding="utf-8")
            # 自动创建时间戳备份（同1秒内只备份一次）
            global _last_backup_ts
            now = time.time()
            if now - _last_backup_ts >= 1.0:
                _last_backup_ts = now
                BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
                backup_path = BACKUP_DIR / f"passwords_{ts}.json"
                backup_path.write_text(content, encoding="utf-8")
                # 清理超过上限的旧备份
                _clean_old_backups()
        except OSError as exc:
            _log(f"保存密码文件失败: {exc}")


def _clean_old_backups(max_keep: int = _MAX_BACKUPS) -> None:
    """保留最近 max_keep 个备份，删除更旧的。"""
    try:
        files = sorted(BACKUP_DIR.glob("passwords_*.json"), reverse=True)
        for old in files[max_keep:]:
            old.unlink()
    except OSError:
        pass


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


# ── 备份管理 ──────────────────────────────────────


def backup_list() -> list[dict]:
    """列出所有可用备份（按时间倒序）。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob("passwords_*.json"), reverse=True)
    result = []
    for path in files:
        ts = path.stem.replace("passwords_", "")
        try:
            size = path.stat().st_size
            # 读取备份中的概要统计
            data = json.loads(path.read_text(encoding="utf-8"))
            total = len(data)
            active = sum(1 for e in data.values() if e["remaining"] > 0)
            sold = sum(1 for e in data.values() if e.get("owner"))
            result.append({
                "filename": path.name,
                "timestamp": ts,
                "size": size,
                "total": total,
                "active": active,
                "sold": sold,
            })
        except Exception as exc:
            result.append({"filename": path.name, "timestamp": ts, "size": 0, "error": str(exc)})
    return result


def backup_restore(filename: str) -> dict:
    """从指定备份文件恢复密码数据。"""
    global _store
    backup_path = BACKUP_DIR / filename
    if not backup_path.exists():
        return {"success": False, "message": f"备份文件 {filename} 不存在"}
    if not backup_path.name.startswith("passwords_") or not backup_path.name.endswith(".json"):
        return {"success": False, "message": "无效的备份文件名"}
    with _lock:
        try:
            data = json.loads(backup_path.read_text(encoding="utf-8"))
            # 先把当前状态存为备份（防误操作丢数据）
            if _store is not None:
                _save()
            _store = data
            PASSWORDS_PATH.write_text(
                json.dumps(_store, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _log(f"已从备份 {filename} 恢复，共 {len(data)} 个密码")
            return {"success": True, "message": f"已从 {filename} 恢复，共 {len(data)} 个密码"}
        except (json.JSONDecodeError, OSError) as exc:
            return {"success": False, "message": f"恢复失败: {exc}"}


def backup_export(filename: str) -> str | None:
    """获取备份文件的绝对路径（用于导出下载）。"""
    backup_path = BACKUP_DIR / filename
    if backup_path.exists() and backup_path.name.startswith("passwords_") and backup_path.name.endswith(".json"):
        return str(backup_path)
    return None
