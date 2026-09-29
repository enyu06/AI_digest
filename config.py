"""ユーザーの関心設定。

関連度スコアは、ここに書いた興味・関心にどれだけ近いかで採点される。
自分の研究テーマや追いたい分野を自由な日本語で書けばよい。
"""

import os

# あなたが追いたいトピック・研究テーマを自由に記述する。
# 具体的に書くほど関連度スコアの精度が上がる。
INTERESTS = """- 大規模言語モデル（LLM）の効率化・推論高速化・量子化、RAG とエージェント設計
- 機械学習の手法全般（深層学習、強化学習、ベイズ最適化、ガウス過程など）
- 軌道力学・宇宙機の軌道設計・軌道決定・軌道最適化（低推力、シスルナ、三体問題など）
- サロゲートモデル（代理モデル）、縮約モデル、ニューラルオペレータ、物理情報ニューラルネット
- 上記の組み合わせ（機械学習による軌道計算・軌道設計の高速化、サロゲート支援最適化）
- 評価手法・ベンチマーク・ハルシネーション対策、実務に応用できる手法
"""

# 収集するトピック。上にあるものほど優先度が高く、複数トピックに該当する論文は
# 最も上のトピックの節に載る（ニッチな分野を先に書くと埋もれにくい）。
#   categories : このトピックとみなす arXiv カテゴリ（そのカテゴリの論文はすべて該当）
#   keywords   : タイトル・アブストラクト中の単語の先頭一致で判定するキーワード
#                （大文字小文字は区別しない。"spacecraft" は "spacecrafts" にも当たる）
#   max_results: 1 日あたりレポートに載せる論文の上限
TOPICS = {
    "orbit": {
        "label": "🛰️ 軌道・宇宙力学",
        "categories": [],
        "keywords": [
            # 単独の "orbit" は系外惑星や分子軌道（orbital）の論文にも当たるため、
            # 宇宙機・軌道工学の語に絞っている。
            "orbit determination", "orbit propagat", "orbit design", "orbit control",
            "orbit transfer", "orbital transfer", "orbital mechanic", "orbital dynamic",
            "orbital maneuver", "orbital debris", "periodic orbit", "halo orbit",
            "earth orbit", "lunar orbit", "satellite orbit", "orbit insertion",
            "astrodynamic", "celestial mechanic", "spacecraft", "low-thrust",
            "cislunar", "three-body", "space debris", "space mission",
            "launch vehicle", "satellite constellation", "rendezvous",
            "trajectory optimi", "trajectory design",
        ],
        "max_results": 30,
    },
    "surrogate": {
        "label": "🧩 サロゲートモデル",
        "categories": [],
        "keywords": [
            "surrogate", "reduced-order model", "reduced order model", "metamodel",
            "neural operator", "physics-informed", "emulator",
        ],
        "max_results": 30,
    },
    "llm": {
        "label": "💬 LLM・生成 AI",
        "categories": ["cs.CL"],
        "keywords": [
            "llm", "large language model", "language model", "gpt", "chatgpt",
            "claude", "gemini", "rag", "retrieval-augmented", "ai agent",
            "chatbot", "generative ai",
        ],
        "max_results": 20,
    },
    "ml": {
        "label": "🤖 機械学習",
        "categories": ["cs.LG", "stat.ML"],
        "keywords": [
            "machine learning", "deep learning", "neural network",
            "reinforcement learning", "diffusion model", "gaussian process",
            "bayesian optimization", "graph neural", "foundation model",
        ],
        "max_results": 20,
    },
}

# arXiv の新着 RSS を取得するカテゴリ。ここに含まれる分野の論文から
# 上の TOPICS に該当するものを選ぶ（cross-list された論文も含む）。
ARXIV_CATEGORIES = [
    "cs.LG", "stat.ML", "cs.CL", "cs.AI",          # 機械学習・LLM
    "physics.space-ph", "astro-ph.EP", "astro-ph.IM",  # 宇宙・天体力学
    "math.OC", "math.DS", "eess.SY", "cs.RO",      # 最適化・力学系・制御
    "physics.comp-ph", "physics.flu-dyn", "cs.CE", "math.NA",  # 数値計算・サロゲート
]

# ASEL2 上で稼働しているモデル。
MODEL = os.environ.get("OLLAMA_MODEL") or "qwen3.8:27B"

# 研究室 LAN 上の Ollama API。IP は変わり得るためホスト名で接続する。
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL") or "http://ASEL2:11434"

# 27B モデルの初回ロードを考慮したタイムアウト（秒）。
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT") or "600")

# 関連度スコアがこの値未満の論文はレポートで「低関連」に折りたたむ
# （0〜100 のうち、表示の足切りではなく並べ替え・グルーピングに使う）
RELEVANCE_THRESHOLD = 50
