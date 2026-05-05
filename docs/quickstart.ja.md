# Quickstart (日本語版)

`pip install` から実際のマルチエージェント・フロー実行まで 5 分で完結します。

> 🇬🇧 English version: [quickstart.md](quickstart.md)

---

## 1. インストール

必要なエクストラだけ追加できます (それ以外の依存関係は引き込まれません):

```bash
pip install praxia                 # コア (CLI + JSON memory + 6 skills + 3 flows)
pip install "praxia[ui]"           # + Streamlit UI
pip install "praxia[connectors]"   # + Box / SharePoint / Dropbox / Drive / kintone / Salesforce
pip install "praxia[office]"       # + PDF / Word / PowerPoint / Excel パース
pip install "praxia[audio]"        # + Whisper STT + OpenAI / ElevenLabs TTS
pip install "praxia[all]"          # 全部入り
```

## 2. 設定 — 鍵は一箇所で集中管理

Praxia は以下の優先順位で設定を解決します (上位優先):

1. **プロセス環境変数**
2. **`.env` ファイル** (作業ディレクトリ)
3. **`.praxia/config.toml`** (`praxia config` で管理)

最も簡単なのは `.env` 経由:

```bash
cp .env.example .env
# .env を編集して、利用したいキーだけ記入
```

または、対話ウィザード:

```bash
praxia config init     # 必要なキーをインタラクティブに入力
praxia config show     # 現在の設定を表示 (シークレットはマスク)
praxia config path     # 設定の解決順序を表示
praxia config set ANTHROPIC_API_KEY sk-ant-xxx
praxia config get OPENAI_API_KEY
```

**最低条件**: LLM プロバイダのキーを 1 つ設定:

```bash
ANTHROPIC_API_KEY=sk-ant-...      # 推奨
# または
OPENAI_API_KEY=sk-...             # Whisper STT + OpenAI TTS も同じキーで動く
# または
GEMINI_API_KEY=...                # Google Gemini
# または
DASHSCOPE_API_KEY=...             # Alibaba Qwen API
```

**完全オフライン運用**もOK:

```bash
ollama pull qwen2.5:14b
praxia run sales --model qwen-local --customer-name "Acme" --product "BizFlow"
```

## 3. 初期化

```bash
praxia init --user-id alice --backend json --model auto
```

`.praxia/` ディレクトリに個人メモリ・スキルレジストリ・admin ユーザが作成されます。

## 4. フロー実行

3 つの組み込みマルチエージェント・フロー:

```bash
# B2B 営業準備 — IR / 議事録 / RAG → 仮説 → FAQ → 提案書
praxia run sales --customer-name "株式会社サンプル" --product "BizFlow"

# 長文の論理整合性レビュー (3 エージェント)
praxia run logic --document 仕様書.pdf       # .pdf / .docx / .pptx / .xlsx / .csv 自動パース

# 自己修復型 RAG — クエリ拡張 → 評価 → ハルシネーション検証
praxia run rag --question "Praxia のライセンスは?"
```

## 5. 単一スキル実行

6 業務領域、ガードレール付き:

```bash
praxia skill run investment "中堅電機メーカー (架空) の中期投資判断"
praxia skill run sales      "Acme Corp (製造業) への提案戦略"
praxia skill run design     "spec.md のアーキテクチャをレビュー"
praxia skill run purchasing "suppliers.csv の 5 社 RFQ を比較"
praxia skill run patent     "全固体電池構造の先行技術調査"
praxia skill run legal      "services_agreement.pdf のリスクをレビュー"
```

## 6. UI 起動

```bash
praxia ui --port 8501
# http://localhost:8501 を開く
```

11 タブ:

- **🎬 Run Flow** — フロー選択、ファイル添付 (PDF / Office 等)、各エージェントの実行
- **🛠 Skill** — 6 ビジネススキル + ファイル添付 + 🎙 音声入力
- **🧠 Memory** — 個人メモリ + 共有ブロックのブラウズ
- **🌙 Consolidate** — 個人 → 組織への自動昇格
- **📊 Dashboard** — 個人 + 組織の利用状況
- **📝 Prompts** — カスタムプロンプト管理 (3 スコープ)
- **👥 Users** — 管理者: ユーザ CRUD
- **🔌 Connectors** — Box / SharePoint / Dropbox / Drive / kintone / Salesforce
- **🛡 Policies** — 管理者: アクセスポリシー (ACL)
- **💾 Admin** — 監査ログ・ユーザ・利用ログ・メモリ・ポリシー エクスポート
- **ℹ About**

## 7. 個人 → 組織メモリの蒸留

```bash
praxia consolidate --dry-run                 # 何が昇格されるかを事前確認
praxia consolidate --threshold 0.75          # 本番閾値
praxia freeze --block team_norms             # 安定したブロックを git 管理 Markdown に
```

## 8. ユーザ委譲 OAuth (エンタープライズ推奨)

各 Praxia ユーザが **自身の認証情報で** 外部システムを認可。連携先システムの ACL がユーザ単位で適用されます:

```bash
# 一度: OAuth アプリ登録 + クライアント認証情報を .env に
PRAXIA_OAUTH_BOX_CLIENT_ID=...
PRAXIA_OAUTH_BOX_CLIENT_SECRET=...

# ユーザ毎: 一度認可
praxia oauth start box --user-id alice
# URL を開く → Box にログイン → トークンが暗号化保存

# 以降、alice のコネクタ呼び出しは alice のトークンを使う
praxia connector pull box 0 --user-id alice
```

対応プロバイダ: Box / Microsoft / Dropbox / Google Drive / Salesforce。

## 9. 管理操作

```bash
# ユーザ管理 (全操作監査ログ)
praxia user create alice --role member
praxia user update alice --role operator --email alice@a.test
praxia user audit --limit 100

# アクセスポリシー (情報システム部向け)
praxia policy add deny connector "box:/Confidential/*" \
    --principals "role:member,role:viewer" \
    --description "機密フォルダはオペレーター以上のみ"
praxia policy test alice member connector box:/Confidential/q3.pdf read

# データダウンロード (export 操作自体も監査される)
praxia admin export-audit audit.csv --since-days 30
praxia admin export-users users.json --format json
praxia admin export-memory ./backup --all
```

## 10. リソース一覧

```bash
praxia list flows         # 利用可能なフロー
praxia list skills        # 6 業務スキル
praxia list models        # サポート LLM
praxia list backends      # メモリバックエンド
praxia connector list     # 外部コネクタ
```

---

## トラブルシュート

**「No LLM provider key found」** → `praxia config init` で `ANTHROPIC_API_KEY` 等を設定するか、Ollama 経由で `qwen-local` を使用。

**ファイルパースに失敗** → office エクストラを追加: `pip install "praxia[office]"`

**音声入出力が動かない** → `praxia[audio]` を追加し、`OPENAI_API_KEY` を設定 (Whisper / OpenAI TTS で利用)。

**OAuth で 「Unknown state」** → 現在の state 管理はインメモリ。本番環境では Redis 等に置き換えてください ([FEATURES.md § 25](FEATURES.md#25-user-delegated-oauth-per-user-external-system-access))。

詳細は [docs/FEATURES.md](FEATURES.md) / [docs/PLUGINS.md](PLUGINS.md)、または <https://github.com/genarch/praxia/issues> へ。
