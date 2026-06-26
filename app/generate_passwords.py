"""生成一万个6位数字密码，每个初始可用10次。"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUTPUT = DATA_DIR / "passwords.json"


def main() -> None:
    if OUTPUT.exists():
        overwrite = input(f"{OUTPUT.name} 已存在，是否覆盖？(y/N): ")
        if overwrite.lower() != "y":
            print("已取消")
            return

    # 生成 10000 个不重复的 6 位数字
    pool = random.sample(range(1_000_000), 10000)
    passwords = {f"{n:06d}": {"remaining": 10} for n in pool}

    OUTPUT.write_text(
        json.dumps(passwords, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已生成 {len(passwords)} 个密码 → {OUTPUT}")


if __name__ == "__main__":
    main()
