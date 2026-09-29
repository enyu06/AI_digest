"""AI Daily Digest のエントリポイント。

config.TOPICS（LLM・機械学習・軌道・サロゲートモデルなど）の
論文(arXiv)とニュース(RSS)を収集し、重複を除いたうえで
日次の Markdown レポートを reports/ に出力する。

GitHub Actions から毎日実行されることを想定。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os

from collectors import arxiv_collector, dedupe, enrich, news_collector, topics
from config import RELEVANCE_THRESHOLD, TOPICS

REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
# ニュースを直近何時間ぶん集めるか。収集済みの URL は seen.json で除外されるため、
# 実行の遅延を吸収できるよう広めに取る。論文は arXiv の最新公開分を使う。
WINDOW_HOURS = 48


def _topic_tags(item: dict) -> str:
    return " ".join(f"`{topics.label(k)}`" for k in item.get("topics", []))


def _render_paper(p: dict, *, show_relevance: bool = True) -> list[str]:
    """1 件の論文を Markdown 行リストに整形する。"""
    authors = ", ".join(p["authors"][:3])
    if len(p["authors"]) > 3:
        authors += " ほか"

    score = p.get("relevance", 0)
    title_ja = p.get("title_ja") or p["title"]

    lines = [f"#### [{title_ja}]({p['url']})"]
    # 原題と著者
    lines.append(f"*{p['title']}*")
    lines.append(f"*{authors}*")
    lines.append("")
    lines.append(_topic_tags(p))
    lines.append("")
    if show_relevance:
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


def _render_topic_papers(papers: list[dict], *, papers_enriched: bool) -> list[str]:
    """1 トピック分の論文を整形する。採点済みなら低関連を折りたたむ。"""
    if not papers_enriched:
        lines = []
        for p in papers:
            lines.extend(_render_paper(p, show_relevance=False))
        return lines

    high = [p for p in papers if p.get("relevance", 0) >= RELEVANCE_THRESHOLD]
    low = [p for p in papers if p.get("relevance", 0) < RELEVANCE_THRESHOLD]
    lines = []
    for p in high:
        lines.extend(_render_paper(p))
    # 関連度の低い論文は折りたたんで邪魔にならないようにする
    if low:
        lines.append("<details>")
        lines.append(
            f"<summary>関連度 {RELEVANCE_THRESHOLD} 未満の論文（{len(low)} 件）</summary>"
        )
        lines.append("")
        for p in low:
            lines.extend(_render_paper(p))
        lines.append("</details>")
        lines.append("")
    return lines


def build_markdown(
    papers: list[dict],
    news: list[dict],
    today: str,
    *,
    papers_enriched: bool = True,
) -> str:
    lines = [f"# AI Daily Digest — {today}", ""]
    lines.append(f"論文 {len(papers)} 件 / ニュース {len(news)} 件")
    lines.append("")

    counts = [
        f"{spec['label']} {sum(p.get('topic') == key for p in papers)}"
        for key, spec in TOPICS.items()
    ]
    lines.append("論文の内訳: " + " / ".join(counts))
    lines.append("")

    lines.append("## 📰 ニュース・ブログ")
    lines.append("")
    if news:
        for n in news:
            lines.append(f"### [{n['title']}]({n['url']})")
            tags = _topic_tags(n)
            lines.append(f"*{n['source']}*" + (f" {tags}" if tags else ""))
            lines.append("")
            if n["summary"]:
                lines.append(f"> {n['summary']}")
                lines.append("")
    else:
        lines.append("_本日の新着はありませんでした。_")
        lines.append("")

    lines.append("## 📄 論文 (arXiv)")
    lines.append("")
    if papers and not papers_enriched:
        lines.append(
            "_定期実行では ASEL2 に接続しないため、論文は原題とアブストラクトを掲載しています。_"
        )
        lines.append("")
    if not papers:
        lines.append("_本日の新着はありませんでした。_")
        lines.append("")

    # トピックごとに節を分ける（papers は採点済みなら関連度の降順）
    for key, spec in TOPICS.items():
        group = [p for p in papers if p.get("topic") == key]
        if not group:
            continue
        lines.append(f"### {spec['label']}（{len(group)} 件）")
        lines.append("")
        lines.extend(_render_topic_papers(group, papers_enriched=papers_enriched))

    return "\n".join(lines)


def main(*, skip_enrichment: bool = False) -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)
    today = dt.date.today().isoformat()

    if not skip_enrichment:
        print("Checking remote Ollama on ASEL2...")
        enrich.check_ollama()

    seen = dedupe.load_seen()

    print("Collecting arXiv papers...")
    try:
        papers = dedupe.filter_new(arxiv_collector.fetch_recent(), seen)
    except Exception as exc:  # arXiv が落ちていてもニュースは配信する
        print(f"[warn] arXiv collection failed: {exc}")
        papers = []

    print("Collecting news...")
    news = dedupe.filter_new(news_collector.fetch_recent(hours=WINDOW_HOURS), seen)

    dedupe.save_seen(seen)

    if skip_enrichment:
        print("Skipping Ollama enrichment; keeping original paper abstracts.")
    else:
        print("Enriching papers via Ollama on ASEL2...")
        papers = enrich.enrich_all(papers)

    md = build_markdown(
        papers,
        news,
        today,
        papers_enriched=not skip_enrichment,
    )
    out_path = os.path.join(REPORT_DIR, f"{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Report written to {out_path}")
    print(f"  papers: {len(papers)}, news: {len(news)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="ASEL2/Ollama を使わず、論文は原文のままレポートに載せる",
    )
    args = parser.parse_args()
    main(skip_enrichment=args.skip_enrichment)
