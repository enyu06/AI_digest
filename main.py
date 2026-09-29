"""AI Daily Digest のエントリポイント。

config.TOPICS（LLM・機械学習・軌道・サロゲートモデルなど）の
論文(arXiv)とニュース(RSS)を収集し、重複を除いたうえで
日次の Markdown レポートを reports/ に出力する。

GitHub Actions（未採点版）と研究室 PC のタスク（ASEL2 で採点）から
毎日実行されることを想定。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os

from collectors import arxiv_collector, dedupe, enrich, news_collector, topics
from config import RELEVANCE_THRESHOLD, TOPICS

REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
# 当日の収集結果（採点前後）を保存する場所
DATA_DIR = os.path.join(REPORT_DIR, "data")
JST = dt.timezone(dt.timedelta(hours=9))
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


def _today() -> str:
    """JST の日付。GitHub Actions（UTC）と研究室 PC で同じ日付のレポートを扱う。"""
    return dt.datetime.now(JST).date().isoformat()


def _load_data(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_data(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _collect() -> tuple[list[dict], list[dict]]:
    """論文とニュースを収集し、未収集のものだけを返す（seen.json を更新する）。"""
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
    return papers, news


def main(*, skip_enrichment: bool = False) -> None:
    """当日のレポートを作る。

    収集結果は reports/data/<日付>.json に保存し、同じ日に再実行したときは
    収集をやり直さずに再利用する。これにより、GitHub Actions が作った未採点の
    レポートを、研究室 PC から `python main.py` で採点済みに差し替えられる。
    """
    today = _today()
    data_path = os.path.join(DATA_DIR, f"{today}.json")
    data = _load_data(data_path)

    out_path = os.path.join(REPORT_DIR, f"{today}.md")
    if data and (data["enriched"] or skip_enrichment):
        print(f"Report for {today} already exists; nothing to do.")
        return
    if not data and os.path.exists(out_path):
        # 収集結果が残っていないレポートを再収集すると、既読扱いで空になってしまう
        print(f"{out_path} exists but {data_path} does not; nothing to do.")
        return

    if not skip_enrichment:
        print("Checking remote Ollama on ASEL2...")
        enrich.check_ollama()

    if data:
        print(f"Reusing collected items from {data_path}")
        papers, news = data["papers"], data["news"]
    else:
        papers, news = _collect()
        # 採点前に保存しておき、採点が途中で失敗しても収集結果を失わないようにする
        _save_data(data_path, {"enriched": False, "papers": papers, "news": news})

    if skip_enrichment:
        print("Skipping Ollama enrichment; keeping original paper abstracts.")
    else:
        print(f"Enriching {len(papers)} papers via Ollama on ASEL2...")
        papers = enrich.enrich_all(papers)
        _save_data(data_path, {"enriched": True, "papers": papers, "news": news})

    md = build_markdown(
        papers,
        news,
        today,
        papers_enriched=not skip_enrichment,
    )
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
