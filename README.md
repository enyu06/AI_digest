# AI Daily Digest

AI 関連の論文（arXiv）とニュース（RSS）を毎日自動で収集し、
**各論文を研究室 LAN 上のローカル LLM（ASEL2 の Ollama）で日本語要約・日本語訳・関連度スコア付け**
したうえで、日次の Markdown レポートを `reports/YYYY-MM-DD.md` に出力するツール。
研究室 LAN 内の GitHub Actions self-hosted runner で毎朝自動実行される。

## 構成

```
ai-digest/
├── main.py                      # エントリポイント（収集→エンリッチ→整形→出力）
├── config.py                    # 関心トピック・モデル・しきい値の設定
├── collectors/
│   ├── arxiv_collector.py       # arXiv API から論文を収集
│   ├── news_collector.py        # RSS からニュースを収集
│   ├── enrich.py                # Ollama で要約・翻訳・スコアリング
│   ├── dedupe.py                # URL ベースの重複排除
│   └── seen.json                # 収集済み履歴（自動生成）
├── reports/                     # 生成された日次レポート
├── requirements.txt
└── .github/workflows/daily.yml  # 毎日実行する CI 設定
```

## セットアップ

1. digest を実行する PC から ASEL2 への疎通を確認する。

   ```powershell
   Resolve-DnsName ASEL2
   Test-NetConnection ASEL2 -Port 11434
   curl.exe http://ASEL2:11434/api/tags
   ```

   `TcpTestSucceeded : True` となり、応答に `qwen3.8:27B` が含まれればよい。
   クライアント側に Ollama やモデルをインストールする必要はない。
2. GitHub リポジトリの **Settings → Actions → Runners → New self-hosted runner**
   を開き、表示される Windows 用の手順で研究室 LAN 内の PC を登録する。
   定期実行するには runner をサービスとして構成し、実行時刻に起動しておく。
   Actions Runner は `v2.327.1` 以降が必要。
3. リポジトリの **Settings → Actions → General → Workflow permissions** で
   「Read and write permissions」を有効にする（レポートの自動コミットに必要）。
4. これで毎日 JST 09:00 に自動実行される。
   すぐ試すなら **Actions タブ → AI Daily Digest → Run workflow** で手動実行。

API キーや GitHub Actions Secrets の登録は不要。LLM 本体と推論処理は
ASEL2（RTX 6000 Pro）側で実行される。

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
```

`Ollama サーバに接続できません` と表示された場合は、研究室 LAN への接続、
`ASEL2` の名前解決、TCP 11434、ASEL2 上の Ollama の順に確認する。

## 関連度スコアの仕組み

`config.py` の `INTERESTS` に書いたあなたの興味・研究テーマに対し、
各論文がどれだけ近いかをローカル LLM が 0〜100 で採点する。レポートでは
スコアの高い論文が上に並び、しきい値（既定 50）未満は折りたたまれる。
**具体的に書くほどスコアの精度が上がる**ので、自分のテーマに合わせて編集する。

## カスタマイズ

- **関心トピック**: `config.py` の `INTERESTS`（関連度スコアの基準）。
- **モデル**: `config.py` の `MODEL`（既定は `qwen3.8:27B`）。
- **Ollama の接続先**: `config.py` の `OLLAMA_BASE_URL`（既定は `http://ASEL2:11434`）。
- **推論タイムアウト**: `config.py` の `OLLAMA_TIMEOUT`（既定は 600 秒）。
- **折りたたみのしきい値**: `config.py` の `RELEVANCE_THRESHOLD`。
- **論文カテゴリ**: `collectors/arxiv_collector.py` の `CATEGORIES`。
- **ニュースソース**: `collectors/news_collector.py` の `FEEDS`。
- **収集する時間幅**: `main.py` の `WINDOW_HOURS`（デフォルト 26 時間）。
- **実行時刻**: `.github/workflows/daily.yml` の `cron`（UTC 表記）。

## 実行上の注意

研究室内のローカル推論なので API 利用料はかからない。論文 1 件ずつ
ASEL2 にリクエストするため、件数を減らす場合は
`collectors/arxiv_collector.py` の `max_results` を小さくする。

定期実行時に self-hosted runner がオフラインの場合、ジョブは runner が
オンラインになるまで待機する。ASEL2 に接続できない、またはモデルがない場合は
`Check remote LLM` ステップで停止する。TCP 11434 はインターネットへ公開せず、
研究室 LAN 内だけで利用する。

## 発展のアイデア

- Slack / Discord の webhook で関連度の高い論文だけ通知する
- 履歴を SQLite に移して検索・集計できるようにする
- 関連度スコアの推移を記録して興味の変化を可視化する
