"""AI 関連ニュース/ブログを RSS フィードから収集する。

feedparser を使い、各メディア・企業ブログの RSS から
直近 N 時間以内の記事を取得する。フィードは FEEDS で管理する。
"""

from __future__ import annotations

import datetime as dt
import time

import feedparser

# 収集対象の RSS フィード。「名前: URL」で自由に追加・削除できる。
FEEDS = {
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "MIT Tech Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
}


def _entry_datetime(entry) -> dt.datetime | None:
    """エントリの公開日時を timezone-aware な datetime で返す。"""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return dt.datetime.fromtimestamp(time.mktime(parsed), tz=dt.timezone.utc)


def fetch_recent(hours: int = 24, per_feed: int = 10) -> list[dict]:
    """各フィードから直近 `hours` 時間以内の記事を返す。"""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    articles: list[dict] = []

    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as exc:  # フィード単位の失敗で全体を止めない
            print(f"[warn] failed to parse {name}: {exc}")
            continue

        for entry in feed.entries[:per_feed]:
            pub_dt = _entry_datetime(entry)
            if pub_dt is None or pub_dt < cutoff:
                continue

            summary = entry.get("summary", "").strip()
            # HTML タグを雑に除去（簡易処理）
            summary = _strip_html(summary)[:400]

            articles.append(
                {
                    "source": name,
                    "title": entry.get("title", "(no title)").strip(),
                    "url": entry.get("link", ""),
                    "summary": summary,
                    "published": pub_dt.isoformat(),
                }
            )

    return articles


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


if __name__ == "__main__":
    for a in fetch_recent():
        print(f"[{a['source']}] {a['title']}")
