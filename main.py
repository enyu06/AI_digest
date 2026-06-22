"""AI Daily Digest のエントリポイント。

論文(arXiv)とニュース(RSS)を収集し、重複を除いたうえで
日次の Markdown レポートを reports/ に出力する。

GitHub Actions から毎日実行されることを想定。
"""

from __future__ import annotations

import datetime as dt
import os

from collectors import arxiv_collector, dedupe, enrich, news_collector
from config import RELEVANCE_THRESHOLD

REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
# 直近何時間ぶんを集めるか（日次実行なら 24〜26 程度に余裕を持たせる）
WINDOW_HOURS = 26


def _render_paper(p: dict) -> list[str]:
    """1 件の論文を Markdown 行リストに整形する。"""
    authors = ", ".join(p["authors"][:3])
    if len(p["authors"]) > 3:
        authors += " ほか"

    score = p.get("relevance", 0)
    title_ja = p.get("title_ja") or p["title"]

    lines = [f"### [{title_ja}]({p['url']})"]
    # 原題と著者
    lines.append(f"*{p['title']}*")
    lines.append(f"*{authors}*")
    lines.append("")
    # 関連度スコア（バッジ風）と理由
    reason = p.get("relevance_reason", "")
    lines.append(f"**関連度: {score}/100** — {reason}")
    lines.append("")
    # 日本語要約（無ければ英語アブストラクトにフォールバック）
    summary_ja = p.get("summary_ja")
    if summary_ja:
        lines.append(f"> {summary_ja}")
    else:
        lines.append(f"> {p['summary'][:400]}...")
    lines.append("")
    return lines


def build_markdown(papers: list[dict], news: list[dict], today: str) -> str:
    lines = [f"# AI Daily Digest — {today}", ""]
    lines.append(f"論文 {len(papers)} 件 / ニュース {len(news)} 件")
    lines.append("")

    lines.append("## 📰 ニュース・ブログ")
    lines.append("")
    if news:
        for n in news:
            lines.append(f"### [{n['title']}]({n['url']})")
            lines.append(f"*{n['source']}*")
            lines.append("")
            if n["summary"]:
                lines.append(f"> {n['summary']}")
                lines.append("")
    else:
        lines.append("_本日の新着はありませんでした。_")
        lines.append("")

    lines.append("## 📄 論文 (arXiv)")
    lines.append("")
    if papers:
        # 関連度でグルーピング（papers は事前に降順ソート済み）
        high = [p for p in papers if p.get("relevance", 0) >= RELEVANCE_THRESHOLD]
        low = [p for p in papers if p.get("relevance", 0) < RELEVANCE_THRESHOLD]

        lines.append(f"### ⭐ あなたの関心に近い論文（{len(high)} 件）")
        lines.append("")
        if high:
            for p in high:
                lines.extend(_render_paper(p))
        else:
            lines.append("_該当なし。_")
            lines.append("")

        # 関連度の低い論文は折りたたんで邪魔にならないようにする
        if low:
            lines.append("<details>")
            lines.append(
                f"<summary>その他の論文（{len(low)} 件・関連度 "
                f"{RELEVANCE_THRESHOLD} 未満）</summary>"
            )
            lines.append("")
            for p in low:
                lines.extend(_render_paper(p))
            lines.append("</details>")
            lines.append("")
    else:
        lines.append("_本日の新着はありませんでした。_")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)
    today = dt.date.today().isoformat()

    seen = dedupe.load_seen()

    print("Collecting arXiv papers...")
    papers = dedupe.filter_new(arxiv_collector.fetch_recent(hours=WINDOW_HOURS), seen)

    print("Collecting news...")
    news = dedupe.filter_new(news_collector.fetch_recent(hours=WINDOW_HOURS), seen)

    dedupe.save_seen(seen)

    print("Enriching papers via Claude API...")
    papers = enrich.enrich_all(papers)

    md = build_markdown(papers, news, today)
    out_path = os.path.join(REPORT_DIR, f"{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Report written to {out_path}")
    print(f"  papers: {len(papers)}, news: {len(news)}")


if __name__ == "__main__":
    main()
