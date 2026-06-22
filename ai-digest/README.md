# AI Daily Digest

AI 関連の論文（arXiv）とニュース（RSS）を毎日自動で収集し、
**各論文を LLM API（OpenAI または Anthropic）で日本語要約・日本語訳・関連度スコア付け**
したうえで、日次の Markdown レポートを `reports/YYYY-MM-DD.md` に出力するツール。
GitHub Actions で毎朝自動実行される。

## 構成

```
ai-digest/
├── main.py                      # エントリポイント（収集→エンリッチ→整形→出力）
├── config.py                    # 関心トピック・モデル・しきい値の設定
├── collectors/
│   ├── arxiv_collector.py       # arXiv API から論文を収集
│   ├── news_collector.py        # RSS からニュースを収集
│   ├── enrich.py                # LLM API で要約・翻訳・スコアリング（OpenAI/Anthropic）
│   ├── dedupe.py                # URL ベースの重複排除
│   └── seen.json                # 収集済み履歴（自動生成）
├── reports/                     # 生成された日次レポート
├── requirements.txt
└── .github/workflows/daily.yml  # 毎日実行する CI 設定
```

## セットアップ

1. このディレクトリを新しい GitHub リポジトリにプッシュする。
2. リポジトリの **Settings → Actions → General → Workflow permissions** で
   「Read and write permissions」を有効にする（レポートの自動コミットに必要）。
3. **Settings → Secrets and variables → Actions → New repository secret** で
   API キーを登録する。使うプロバイダのものだけでよい:
   - OpenAI を使う場合（既定）: `OPENAI_API_KEY`
     （[platform.openai.com](https://platform.openai.com) で取得）
   - Anthropic を使う場合: `ANTHROPIC_API_KEY`
     （[platform.claude.com](https://platform.claude.com) で取得）
4. これで毎日 JST 09:00 に自動実行される。
   すぐ試すなら **Actions タブ → AI Daily Digest → Run workflow** で手動実行。

## プロバイダの切り替え

既定では OpenAI を使う。`config.py` の `PROVIDER` と `MODEL` を変えるだけで
切り替えられる。

```python
# OpenAI を使う場合（既定）
PROVIDER = "openai"
MODEL = "gpt-5.4-mini"   # 最安にするなら "gpt-4.1-nano"

# Anthropic を使う場合
PROVIDER = "anthropic"
MODEL = "claude-haiku-4-5"
```

切り替えたら、対応する API キー（`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`）を
Secrets に登録しておくこと。

## ローカルで試す

```bash
pip install -r requirements.txt
# 使うプロバイダに応じてどちらかを設定
export OPENAI_API_KEY="sk-..."        # OpenAI を使う場合（既定）
# export ANTHROPIC_API_KEY="sk-ant-..." # Anthropic を使う場合
python main.py
# reports/ に当日分の Markdown が生成される
```

## 関連度スコアの仕組み

`config.py` の `INTERESTS` に書いたあなたの興味・研究テーマに対し、
各論文がどれだけ近いかを Claude が 0〜100 で採点する。レポートでは
スコアの高い論文が上に並び、しきい値（既定 50）未満は折りたたまれる。
**具体的に書くほどスコアの精度が上がる**ので、自分のテーマに合わせて編集する。

## カスタマイズ

- **関心トピック**: `config.py` の `INTERESTS`（関連度スコアの基準）。
- **プロバイダ / モデル**: `config.py` の `PROVIDER` と `MODEL`。
  既定は OpenAI の `gpt-5.4-mini`。最安にするなら `gpt-4.1-nano`、
  Anthropic に変えるなら `PROVIDER="anthropic"` + `claude-haiku-4-5` など。
- **折りたたみのしきい値**: `config.py` の `RELEVANCE_THRESHOLD`。
- **論文カテゴリ**: `collectors/arxiv_collector.py` の `CATEGORIES`。
- **ニュースソース**: `collectors/news_collector.py` の `FEEDS`。
- **収集する時間幅**: `main.py` の `WINDOW_HOURS`（デフォルト 26 時間）。
- **実行時刻**: `.github/workflows/daily.yml` の `cron`（UTC 表記）。

## コストの目安

要約は安価なモデル（OpenAI の `gpt-5.4-mini` で $0.75/$4.50 per Mtok、
`gpt-4.1-nano` なら $0.10/$0.40。Anthropic の Haiku 4.5 は $1/$5）を使う。
論文 1 件あたりの入出力はおおよそ 1〜2 千トークン程度なので、1 日数十件でも
数円〜十数円程度に収まる。件数が多い日に備えるなら、`arxiv_collector.py` の
`max_results` で上限を絞るとよい。

## 発展のアイデア

- Slack / Discord の webhook で関連度の高い論文だけ通知する
- 履歴を SQLite に移して検索・集計できるようにする
- 関連度スコアの推移を記録して興味の変化を可視化する
