"""ローカル LLM で論文を日本語化・要約・関連度スコアリングする。

各論文について以下を 1 回の API 呼び出しで生成する:
  - title_ja      : タイトルの日本語訳
  - summary_ja    : 3〜4 文の日本語要約
  - relevance     : ユーザーの関心への関連度スコア（0〜100）
  - relevance_reason : スコアの理由（短く）

LLM は Ollama のローカル API を利用する。API キーは不要。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from config import INTERESTS, MODEL, OLLAMA_BASE_URL, OLLAMA_TIMEOUT

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

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title_ja": {"type": "string"},
        "summary_ja": {"type": "string"},
        "relevance": {"type": "integer", "minimum": 0, "maximum": 100},
        "relevance_reason": {"type": "string"},
    },
    "required": ["title_ja", "summary_ja", "relevance", "relevance_reason"],
}


class _OllamaBackend:
    """Ollama の /api/chat を呼び出すバックエンド。"""

    def __init__(self, base_url: str = OLLAMA_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.url = f"{self.base_url}/api/chat"

    def check_model(self) -> None:
        """Ollama サーバへの疎通とモデルの存在を確認する。"""
        tags_url = f"{self.base_url}/api/tags"
        try:
            with urllib.request.urlopen(tags_url, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Ollama サーバに接続できません ({tags_url})。"
                "研究室 LAN への接続と ASEL2 の稼働状態を確認してください。"
            ) from exc

        models = {
            item.get("name", "").lower()
            for item in result.get("models", [])
            if item.get("name")
        }
        if MODEL.lower() not in models:
            available = ", ".join(sorted(models)) or "なし"
            raise RuntimeError(
                f"モデル {MODEL!r} が ASEL2 にありません。利用可能: {available}"
            )

    def complete(self, system: str, user: str) -> str:
        payload = json.dumps(
            {
                "model": MODEL,
                "stream": False,
                "format": OUTPUT_SCHEMA,
                "think": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {"temperature": 0, "num_predict": 600},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Ollama に接続できません ({self.url})。"
                "Ollama が起動しているか確認してください。"
            ) from exc

        content = result.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError(f"Ollama から空の応答が返りました: {result}")
        return content


def check_ollama() -> None:
    """設定済みの Ollama サーバとモデルが利用可能ならその旨を表示する。"""
    backend = _OllamaBackend()
    backend.check_model()
    print(f"Ollama ready: {MODEL} at {OLLAMA_BASE_URL}")


# ---- エンリッチ本体 ------------------------------------------------------

def enrich_paper(backend: _OllamaBackend, paper: dict) -> dict:
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

    backend = _OllamaBackend()
    enriched = [enrich_paper(backend, p) for p in papers]
    enriched.sort(key=lambda p: p.get("relevance", 0), reverse=True)
    return enriched
