"""arXiv の新着 RSS から関心トピックの論文を収集する。

rss.arxiv.org は無料・無認証で、各カテゴリの直近の公開分（アブストラクト付き）を
返す。config.ARXIV_CATEGORIES の新着をまとめて取得し、config.TOPICS の
カテゴリ・キーワードに該当する論文だけを残す。

（export.arxiv.org の検索 API は Python からのアクセスを 406 で拒否することが
あるため、RSS を使っている。）
"""

from __future__ import annotations

import datetime as dt
import re

import feedparser

from collectors import topics
from config import ARXIV_CATEGORIES, TOPICS

RSS_URL = "https://rss.arxiv.org/atom/" + "+".join(ARXIV_CATEGORIES)
USER_AGENT = "ai-digest/1.0 (+https://github.com/enyu06/AI_digest)"

# "new"=新規投稿, "cross"=他分野からのクロスリスト。改訂版（replace）は除く。
ANNOUNCE_TYPES = {"new", "cross"}

_ABSTRACT_RE = re.compile(r"^.*?Abstract:\s*", re.DOTALL)


def _classify(title: str, summary: str, categories: list[str]) -> list[str]:
    """論文が該当するトピックを TOPICS の優先順で返す。"""
    keys = topics.match_topics(f"{title} {summary}")
    keys += [k for k, spec in TOPICS.items() if set(spec["categories"]) & set(categories)]
    return topics.order(keys)


def fetch_recent() -> list[dict]:
    """直近の公開分から、各トピックに該当する論文を返す。

    各論文の "topic" は該当トピックのうち最優先のもの、"topics" は該当する全トピック。
    トピックごとに複数トピックにまたがる論文を優先して max_results 件まで残す。
    """
    feed = feedparser.parse(RSS_URL, agent=USER_AGENT)
    if not feed.entries:
        raise RuntimeError(
            f"arXiv RSS を取得できません ({RSS_URL}): {feed.get('bozo_exception', '')}"
        )

    by_topic: dict[str, list[dict]] = {key: [] for key in TOPICS}
    for entry in feed.entries:
        if entry.get("arxiv_announce_type") not in ANNOUNCE_TYPES:
            continue

        title = " ".join(entry.get("title", "").split())
        summary = " ".join(_ABSTRACT_RE.sub("", entry.get("summary", "")).split())
        categories = [t["term"] for t in entry.get("tags", [])]
        keys = _classify(title, summary, categories)
        if not keys:
            continue

        parsed = entry.get("published_parsed")
        published = dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc) if parsed else None
        by_topic[keys[0]].append(
            {
                "source": "arXiv",
                "title": title,
                "url": entry.get("link", ""),
                "summary": summary,
                "authors": [a.strip() for a in entry.get("author", "").split(",") if a.strip()],
                "published": published.isoformat() if published else "",
                "topic": keys[0],
                "topics": keys,
            }
        )

    papers: list[dict] = []
    for key, group in by_topic.items():
        # sort は安定なので、該当トピック数が同じ論文は RSS の順序を保つ
        group.sort(key=lambda p: len(p["topics"]), reverse=True)
        papers.extend(group[: TOPICS[key]["max_results"]])
    return papers


if __name__ == "__main__":
    for p in fetch_recent():
        print(f"[{','.join(p['topics'])}] {p['title']}")
