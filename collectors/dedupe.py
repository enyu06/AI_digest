"""収集済みアイテムを記録し、重複を排除する。

URL をキーに JSON ファイルへ履歴を保存する。小規模ならこれで十分。
規模が大きくなったら SQLite への置き換えを検討する。
"""

from __future__ import annotations

import json
import os

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "seen.json")


def load_seen() -> set[str]:
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return set(json.load(f))


def save_seen(seen: set[str]) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=0)


def filter_new(items: list[dict], seen: set[str]) -> list[dict]:
    """未収集のアイテムだけを返し、seen を更新する。"""
    fresh = []
    for item in items:
        key = item.get("url", "")
        if key and key not in seen:
            seen.add(key)
            fresh.append(item)
    return fresh
