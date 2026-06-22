"""arXiv から AI 関連の最新論文を収集する。

arXiv API は無料・無認証で利用できる。直近 N 時間以内に
投稿/更新された論文を、指定カテゴリから取得する。
"""

from __future__ import annotations

import datetime as dt
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 収集対象カテゴリ（cs.AI=人工知能, cs.LG=機械学習, cs.CL=自然言語処理,
# cs.CV=コンピュータビジョン）。必要に応じて増減する。
CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV"]

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
API_URL = "http://export.arxiv.org/api/query"


def fetch_recent(hours: int = 24, max_results: int = 60) -> list[dict]:
    """直近 `hours` 時間以内に更新された論文を返す。"""
    cat_query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    params = {
        "search_query": cat_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results),
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"

    # arXiv はリクエスト間隔を空けることを推奨しているため少し待つ
    time.sleep(1)
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    papers: list[dict] = []

    for entry in root.findall("atom:entry", ATOM_NS):
        published = entry.find("atom:published", ATOM_NS).text
        pub_dt = dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
        if pub_dt < cutoff:
            continue

        title = entry.find("atom:title", ATOM_NS).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ATOM_NS).text.strip().replace("\n", " ")
        link = entry.find("atom:id", ATOM_NS).text.strip()
        authors = [
            a.find("atom:name", ATOM_NS).text
            for a in entry.findall("atom:author", ATOM_NS)
        ]

        papers.append(
            {
                "source": "arXiv",
                "title": title,
                "url": link,
                "summary": summary,
                "authors": authors,
                "published": pub_dt.isoformat(),
            }
        )

    return papers


if __name__ == "__main__":
    for p in fetch_recent():
        print(p["title"])
