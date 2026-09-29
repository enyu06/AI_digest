"""config.TOPICS のキーワードで記事・論文にトピックを付ける。"""

from __future__ import annotations

import re

from config import TOPICS

# 単語の先頭一致（"trajectory optimi" は "optimization" にも当たる）。"rag" が "storage" に
# 当たらないよう、キーワードの直前は単語境界に限定する。
_PATTERNS = {
    key: re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in spec["keywords"]) + ")",
        re.IGNORECASE,
    )
    for key, spec in TOPICS.items()
}


def match_topics(text: str) -> list[str]:
    """text が該当するトピックのキーを TOPICS の優先順で返す。"""
    return [key for key, pattern in _PATTERNS.items() if pattern.search(text)]


def order(keys) -> list[str]:
    """トピックのキーを TOPICS の優先順に並べ替える。"""
    keys = set(keys)
    return [key for key in TOPICS if key in keys]


def label(key: str) -> str:
    return TOPICS[key]["label"]
