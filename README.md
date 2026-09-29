# AI Daily Digest

LLM・機械学習・軌道（宇宙力学）・サロゲートモデルに関する論文（arXiv）とニュース（RSS）を毎日自動で収集し、
日次の Markdown レポートを `reports/YYYY-MM-DD.md` に出力するツール。
配信は 2 段構えになっている。

- **GitHub Actions（未採点版）**: GitHub 管理ランナーで毎日実行され、論文は原題とアブストラクトのまま載せる。
  研究室の PC が停止していても配信が止まらない。
- **研究室 PC のタスク（採点版）**: 研究室 LAN 内の PC のタスク スケジューラで毎日 10:00 に実行され、
  各論文を ASEL2 の Ollama で日本語要約・日本語訳・関連度スコア付けしたレポートに差し替えて push する。

## 構成

```
ai-digest/
├── main.py                      # エントリポイント（収集→エンリッチ→整形→出力）
├── config.py                    # 収集トピック・関心・モデル・しきい値の設定
├── collectors/
│   ├── arxiv_collector.py       # arXiv の新着 RSS から論文を収集
│   ├── news_collector.py        # RSS からニュースを収集
│   ├── topics.py                # キーワードによるトピック判定
│   ├── enrich.py                # Ollama で要約・翻訳・スコアリング
│   ├── dedupe.py                # URL ベースの重複排除
│   └── seen.json                # 収集済み履歴（自動生成）
├── reports/                     # 生成された日次レポート
│   └── data/                    # 当日の収集結果（採点版への差し替えに使う）
├── scripts/
│   ├── run_enriched.ps1         # 研究室 PC で採点版を作って push する
│   └── register_task.ps1        # run_enriched.ps1 をタスク スケジューラに登録する
├── requirements.txt
└── .github/workflows/daily.yml  # 毎日実行する CI 設定
```

## セットアップ

1. リポジトリの **Settings → Actions → General → Workflow permissions** で
   「Read and write permissions」を有効にする（レポートの自動コミットに必要）。
2. これで毎日 JST 09:00 に自動実行される。
   すぐ試すなら **Actions タブ → AI Daily Digest → Run workflow** で手動実行。

定期版は API キーや self-hosted runner を必要としない。論文の日本語要約も付けて
ローカル実行する場合は、実行する PC から ASEL2 への疎通を確認する。

   ```powershell
   Resolve-DnsName ASEL2
   Test-NetConnection ASEL2 -Port 11434
   curl.exe http://ASEL2:11434/api/tags
   ```

   `TcpTestSucceeded : True` となり、応答に `qwen3.8:27B` が含まれればよい。
   クライアント側に Ollama やモデルをインストールする必要はない。

採点版を毎日自動で作るには、研究室 LAN 内の PC（このリポジトリを clone し、
`git push` できる状態にしておく）で次を 1 回実行してタスクを登録する。

```powershell
powershell -ExecutionPolicy Bypass -File scriptsegister_task.ps1
```

毎日 10:00 に `scripts/run_enriched.ps1` が実行される（PC が停止していた場合は次の起動時）。
初回は `.venv` を作って依存パッケージを入れる。実行ログは `logs/` に残る。
LLM 本体と推論処理は ASEL2（RTX 6000 Pro）側で実行される。

## モデルの切り替え

ガイドに合わせ、既定値は次のとおり。

```text
接続先: http://ASEL2:11434
モデル: qwen3.8:27B
```

一時的に切り替える場合は、コードを変更せず環境変数で上書きできる。

```powershell
$env:OLLAMA_BASE_URL = "http://別サーバー:11434"
$env:OLLAMA_MODEL = "別のモデル名"
```

## ローカルで試す

```powershell
pip install -r requirements.txt
python -c "from collectors.enrich import check_ollama; check_ollama()"
python main.py
# reports/ に当日分の Markdown が生成される

# ASEL2 が使えない環境でも、定期版と同じ内容を生成できる
python main.py --skip-enrichment
```

`Ollama サーバに接続できません` と表示された場合は、研究室 LAN への接続、
`ASEL2` の名前解決、TCP 11434、ASEL2 上の Ollama の順に確認する。

## 関連度スコアの仕組み

`config.py` の `INTERESTS` に書いたあなたの興味・研究テーマに対し、
各論文がどれだけ近いかをローカル LLM が 0〜100 で採点する。レポートでは
トピックごとにスコアの高い論文が上に並び、しきい値（既定 50）未満は折りたたまれる。
（ASEL2 を使わない定期版では採点せず、トピックごとに原文を掲載する。）
**具体的に書くほどスコアの精度が上がる**ので、自分のテーマに合わせて編集する。

## カスタマイズ

- **収集トピック**: `config.py` の `TOPICS`。トピックごとに、丸ごと対象にする arXiv カテゴリ
  （`categories`）、タイトル・アブストラクトで判定するキーワード（`keywords`）、
  1 日の掲載上限（`max_results`）を設定する。上に書いたトピックほど優先され、
  複数に該当する論文は最上位のトピックの節に載る。
- **関心**: `config.py` の `INTERESTS`（ASEL2 で採点するときの関連度スコアの基準）。
- **モデル**: `config.py` の `MODEL`（既定は `qwen3.8:27B`）。
- **Ollama の接続先**: `config.py` の `OLLAMA_BASE_URL`（既定は `http://ASEL2:11434`）。
- **推論タイムアウト**: `config.py` の `OLLAMA_TIMEOUT`（既定は 600 秒）。
- **折りたたみのしきい値**: `config.py` の `RELEVANCE_THRESHOLD`。
- **論文カテゴリ**: `config.py` の `ARXIV_CATEGORIES`（新着 RSS を取得する arXiv カテゴリ）。
- **ニュースソース**: `collectors/news_collector.py` の `FEEDS`（全記事）と
  `FILTERED_FEEDS`（宇宙系。軌道・サロゲートのキーワードに当たる記事だけ）。
- **ニュースを集める時間幅**: `main.py` の `WINDOW_HOURS`（デフォルト 48 時間）。
- **実行時刻**: `.github/workflows/daily.yml` の `cron`（UTC 表記）。

## 実行上の注意

研究室内のローカル推論なので API 利用料はかからない。論文 1 件ずつ
ASEL2 にリクエストするため、件数を減らす場合は
`config.py` の `TOPICS` の `max_results` を小さくする。

論文は arXiv の検索 API ではなく新着 RSS（`rss.arxiv.org`）から取得する。
検索 API は Python からのアクセスを HTTP 406 で拒否することがあるため。
arXiv は土日に新着を公開しないため、月曜・日曜のレポートは論文が少ないか 0 件になる。

GitHub Actions の定期版は ASEL2 に接続せず、RSS に含まれるニュース要約と
論文の原文アブストラクトを掲載する。`python main.py` を研究室 LAN 内で実行した場合だけ
Ollama による論文の日本語要約・採点を行う。収集結果は `reports/data/<日付>.json` に
保存され、同じ日に `python main.py` を実行すると再収集せずにそれを採点してレポートを
差し替える。採点済みの日に再実行しても何もしない（先に研究室 PC が採点版を作った日は、
GitHub Actions は何もせず終了する）。TCP 11434 はインターネットへ公開せず、
研究室 LAN 内だけで利用する。

## 発展のアイデア

- Slack / Discord の webhook で関連度の高い論文だけ通知する
- 履歴を SQLite に移して検索・集計できるようにする
- 関連度スコアの推移を記録して興味の変化を可視化する
