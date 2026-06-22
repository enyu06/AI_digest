"""LLM API で論文を日本語化・要約・関連度スコアリングする。

各論文について以下を 1 回の API 呼び出しで生成する:
  - title_ja      : タイトルの日本語訳
  - summary_ja    : 3〜4 文の日本語要約
  - relevance     : ユーザーの関心への関連度スコア（0〜100）
  - relevance_reason : スコアの理由（短く）

プロバイダは config.py の PROVIDER で切り替える（"openai" / "anthropic"）。
API キーは環境変数から読む:
  - OpenAI    : OPENAI_API_KEY
  - Anthropic : ANTHROPIC_API_KEY
"""

from __future__ import annotations

import json
import os

from config import INTERESTS, MODEL, PROVIDER

# 要約の出力を JSON に固定するためのシステムプロンプト
SYSTEM_PROMPT = f"""\
あなたは AI 研究のキュレーターです。与えられた論文（英語）について、
日本語で要約し、ユーザーの関心への関連度を採点します。

ユーザーの関心:
{INTERESTS}

必ず以下の JSON 形式「のみ」で出力してください。前置き・コードブロック・
説明文は一切付けないこと。

{{
  "title_ja": "タイトルの自然な日本語訳",
  "summary_ja": "論文の要点を3〜4文で日本語要約。専門用語は残しつつ平易に。",
  "relevance": 0〜100の整数（ユーザーの関心への近さ）,
  "relevance_reason": "なぜそのスコアか、20〜40字程度で"
}}
"""


# ---- プロバイダごとの呼び出しを抽象化する -------------------------------

class _Backend:
    """LLM プロバイダの共通インターフェース。"""

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class _OpenAIBackend(_Backend):
    def __init__(self) -> None:
        from openai import OpenAI

        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY が設定されていません。"
                "GitHub Actions では Secrets に登録してください。"
            )
        self.client = OpenAI(api_key=key)

    def complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=MODEL,
            max_completion_tokens=600,
            # 出力を JSON に強制する（対応モデルで有効）
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


class _AnthropicBackend(_Backend):
    def __init__(self) -> None:
        from anthropic import Anthropic

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY が設定されていません。"
                "GitHub Actions では Secrets に登録してください。"
            )
        self.client = Anthropic(api_key=key)

    def complete(self, system: str, user: str) -> str:
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")


def _make_backend() -> _Backend:
    if PROVIDER == "openai":
        return _OpenAIBackend()
    if PROVIDER == "anthropic":
        return _AnthropicBackend()
    raise ValueError(f"未知のプロバイダ: {PROVIDER!r}（'openai' か 'anthropic'）")


# ---- エンリッチ本体 ------------------------------------------------------

def enrich_paper(backend: _Backend, paper: dict) -> dict:
    """1 件の論文にエンリッチ情報を付与して返す。失敗時は素通し。"""
    user_content = (
        f"タイトル: {paper['title']}\n\n"
        f"アブストラクト: {paper['summary'][:2000]}"
    )

    try:
        text = backend.complete(SYSTEM_PROMPT, user_content).strip()
        # 念のためコードフェンスを除去してからパース
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        paper["title_ja"] = data.get("title_ja", "")
        paper["summary_ja"] = data.get("summary_ja", "")
        paper["relevance"] = int(data.get("relevance", 0))
        paper["relevance_reason"] = data.get("relevance_reason", "")
    except Exception as exc:
        # API 失敗や JSON 崩れでもパイプライン全体は止めない
        print(f"[warn] enrich failed for '{paper['title'][:50]}': {exc}")
        paper.setdefault("title_ja", "")
        paper.setdefault("summary_ja", "")
        paper.setdefault("relevance", 0)
        paper.setdefault("relevance_reason", "（解析に失敗）")

    return paper


def enrich_all(papers: list[dict]) -> list[dict]:
    """全論文をエンリッチし、関連度の降順で並べ替えて返す。"""
    if not papers:
        return papers

    backend = _make_backend()
    enriched = [enrich_paper(backend, p) for p in papers]
    enriched.sort(key=lambda p: p.get("relevance", 0), reverse=True)
    return enriched
