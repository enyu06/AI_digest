"""AI 関連ニュース/ブログを RSS フィードから収集する。

feedparser を使い、各メディア・企業ブログの RSS から
直近 N 時間以内の記事を取得する。フィードは FEEDS / FILTERED_FEEDS で管理する。
"""

from __future__ import annotations

import datetime as dt
import time

import feedparser

from collectors import topics

USER_AGENT = "ai-digest/1.0 (+https://github.com/enyu06/AI_digest)"

# 収集対象の RSS フィード。「名前: URL」で自由に追加・削除できる。
# AI・機械学習系は全記事を対象にする。
FEEDS = {
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Google Research": "https://research.google/blog/rss/",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "MarkTechPost": "https://www.marktechpost.com/feed/",
    "Phys.org ML/AI": "https://phys.org/rss-feed/technology-news/machine-learning-ai/",
    "MIT Tech Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
}

# 宇宙系フィード。記事数が多いため、FILTER_TOPICS のキーワードに
# 当たる記事（軌道・宇宙機・サロゲートなど）だけを残す。
FILTERED_FEEDS = {
    "SpaceNews": "https://spacenews.com/feed/",
    "NASA": "https://www.nasa.gov/feed/",
    "Phys.org Space": "https://phys.org/rss-feed/space-news/",
}
FILTER_TOPICS = {"orbit", "surrogate"}


def _entry_datetime(entry) -> dt.datetime | None:
    """エントリの公開日時を timezone-aware な datetime で返す。"""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc)


def _fetch_feed(name: str, url: str, cutoff: dt.datetime, per_feed: int) -> list[dict]:
    feed = feedparser.parse(url, agent=USER_AGENT)
    if not feed.entries:
        print(f"[warn] no entries from {name}: {feed.get('bozo_exception', '')}")

    articles = []
    for entry in feed.entries:
        pub_dt = _entry_datetime(entry)
        if pub_dt is None or pub_dt < cutoff:
            continue

        title = entry.get("title", "(no title)").strip()
        # HTML タグを雑に除去（簡易処理）
        summary = _strip_html(entry.get("summary", ""))[:400]
        articles.append(
            {
                "source": name,
                "title": title,
                "url": entry.get("link", ""),
                "summary": summary,
                "published": pub_dt.isoformat(),
                "topics": topics.match_topics(f"{title} {summary}"),
            }
        )

    # フィードによっては新しい順に並んでいないため、日時で並べ替えてから絞る
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:per_feed]


def fetch_recent(hours: int = 24, per_feed: int = 10) -> list[dict]:
    """各フィードから直近 `hours` 時間以内の記事を新しい順に返す。"""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    articles: list[dict] = []

    for name, url in FEEDS.items():
        try:
            articles.extend(_fetch_feed(name, url, cutoff, per_feed))
        except Exception as exc:  # フィード単位の失敗で全体を止めない
            print(f"[warn] failed to parse {name}: {exc}")

    for name, url in FILTERED_FEEDS.items():
        try:
            fetched = _fetch_feed(name, url, cutoff, per_feed=100)
        except Exception as exc:
            print(f"[warn] failed to parse {name}: {exc}")
            continue
        relevant = [a for a in fetched if FILTER_TOPICS & set(a["topics"])]
        articles.extend(relevant[:per_feed])

    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles


def _strip_html(text: str) -> str:
    import html
    import re

    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text)).split())


if __name__ == "__main__":
    for a in fetch_recent():
        print(f"[{a['source']}] {a['title']}")
