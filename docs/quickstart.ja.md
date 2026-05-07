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

**最低条件**: LLM プロバイダのキーを 1 つ設定。`auto_detect()` は以下の優先順位で見つけ次第採用:

```bash
ANTHROPIC_API_KEY=sk-ant-...      # → claude (ツール使用に最適、推奨)
OPENAI_API_KEY=sk-...             # → chatgpt (Whisper STT + OpenAI TTS も同じキー)
GEMINI_API_KEY=...                # → gemini (長文コンテキスト・マルチモーダル)
DEEPSEEK_API_KEY=...              # → deepseek (中国 SOTA、コスト約 1/10)
MISTRAL_API_KEY=...               # → mistral (EU 親和的、mistral-large-latest)
XAI_API_KEY=...                   # → grok
DASHSCOPE_API_KEY=...             # → qwen (Alibaba)
COHERE_API_KEY=...                # → command-r (エンタープライズ RAG)
PERPLEXITY_API_KEY=...            # → perplexity (Web 検索内蔵)
GROQ_API_KEY=...                  # → llama (3.3 70B、数百 tok/s)
TOGETHERAI_API_KEY=...            # → llama via Together
```

明示指定は `--model <alias>` で:
`claude` / `chatgpt` / `gemini` / `deepseek` / `mistral` / `grok` / `qwen` /
`command-r` / `perplexity` / `llama` / `gemma` / `phi` / `llama-local` /
`qwen-local` / `gemma-cloud` 他 10+ ([praxia/core/llm.py](../praxia/core/llm.py) 参照)。

**完全オフライン運用** (クラウド LLM 不使用):

```bash
ollama pull qwen2.5:14b      # デフォルトのローカル
ollama pull llama3.3:70b     # または Llama 3.3
ollama pull gemma2:9b        # または Gemma
ollama pull phi3.5:3.8b      # または Phi (小フットプリント)

praxia run sales --model qwen-local --customer-name "Acme" --product "BizFlow"
# 同様に: --model llama-local / gemma / phi
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

## 4½. LLM に判断させる — 自律エージェント

フロー設計を自分でしたくないとき、`praxia.agent.AutonomousAgent` を使うと
LLM 駆動のツール使用ループを Praxia の各レイヤ (個人/組織メモリ・
凍結層・スキル・コネクタ) 上で LLM に自律的に回させることができます。

```bash
# CLI — 1 行
praxia agent run "Acme について整理して提案書ドラフトを作成して" \
    --user-id alice --org-id acme --max-steps 10

# 組込みツール 11 種を一覧
praxia agent tools
```

```python
# SDK
from praxia.agent import AutonomousAgent
from praxia.core.llm import LLM

agent = AutonomousAgent(user_id="alice", org_id="acme", llm=LLM("claude"))
result = agent.run("Acme について整理して提案書ドラフトを作成して")
print(result.final_text)
for tc in result.tool_calls:
    print(f"- {tc.name}({tc.arguments_text[:60]}) ok={tc.ok}")
```

全ツール呼出は **監査ログ化**、`pull_from_connector` は **ACL チェック**
を通過。`record_fact` は `read_only` モード時には no-op。詳細は
[FEATURES § 38](FEATURES.md#38-autonomous-agent-llm-driven-tool-use-loop)。

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

### サインイン

UI はログイン画面から始まります:

- **単一ユーザ開発モード** (CLI でユーザ未作成): User ID 入力のみで Sign in。全機能アクセス可。ローカル / 信頼 LAN 用。
- **複数ユーザモード** (`praxia user create alice --role admin` 等で 1 人以上登録済): User ID + Password (= ユーザ作成時に発行された API key)。サインインでそのユーザのロールが反映。

インターネット公開のマルチユーザ環境では `praxia serve` (FastAPI + OIDC SSO) を併用してください。Streamlit UI は信頼環境向け設計です。

### レイアウト

画面上部に固定ナビ (Run / Knowledge / Prompts / Data / Stats / Preferences、admin role なら + Admin)、サイドバーは **Context picker** 専用 (どのフォルダ / メモリ層を実行に渡すか)、メインに各 view のワークスペース。

| View | 内容 |
|------|------|
| **🎬 Run** | 2 サブタブ。**🤖 Agent** = `AutonomousAgent` バックエンドの chat。ゴールを書くと LLM が tool (検索 / コネクタ / スキル) を選んで反復実行。**🛠 Skill** = ドメインスキル (投資 / 営業 / 設計 / 購買 / 特許 / 法務) を選んで 1 回呼出。サイドバーで選んだ Context フォルダが両モードに供給され、大きいフォルダは grep ベースで関連箇所だけ抽出。 |
| **🧠 Knowledge** | 個人 + 共有メモリのブラウズ + Skill registry (個人スキル + 組織昇格スキル) の表示。 |
| **📁 Data** | データフォルダの管理。ローカル = UI でアップしたファイル群。コネクタ = 外部の特定パス (Box / SharePoint / Notion 等) を登録。 |
| **📝 Prompts** | 3 サブタブ: Generate (PromptDesigner — 1 行依頼でテンプレ自動生成)、Browse & edit (プロンプト CRUD)、Distribute (管理者のみ — 特定ユーザ / ロールに配信)。 |
| **📊 Stats** | 3 KPI + 横棒グラフ。個人: 総実行回数 · 成功率 · メモリ件数。組織: アクティブユーザ · 組織実行 · 成功率。 |
| **👤 Preferences** | ユーザ毎の永続設定: 言語、カラーテーマ (auto / light / dark)。`.praxia/preferences/<user>.json` に保存。 |
| **⚙ Admin** | admin ロール限定。7 サブタブ: Settings (ランタイム LLM/バックエンド + 永続 KNOWN_KEYS)、Users、Connectors、Policies (ACL)、Consolidate (sleep-time 昇格)、Exports (CSV/JSON/JSONL)、About。 |

## 7. 複数 LTM の融合 + 動的ルーティング (任意・精度向上)

LTM はそれぞれ得意分野が異なります — エンティティ連結 (Mem0)、時系列 KG (Zep)、
監査ログ (JSON)、ベクトル検索 (HindSight)。複数を同時に走らせて結果を融合
したり、クエリ毎に最適なバックエンドへ切り替えたりすることで精度を上げます。

```python
from praxia.memory.composite import CompositeBackend, WeightedBackend
from praxia.memory.backends import load_backend
from praxia import PersonalMemory

# A. 並列実行 + Reciprocal Rank Fusion で結果を融合
composite = CompositeBackend(
    backends=[
        WeightedBackend("mem0",      load_backend("mem0"),      weight=1.5),
        WeightedBackend("zep",       load_backend("zep"),       weight=1.0),
        WeightedBackend("hindsight", load_backend("hindsight"), weight=1.0),
    ],
    fusion="rrf",       # rrf | union | intersection | weighted | llm_rerank
    write_to="mem0",    # 書き込みは1箇所だけ、検索は全 backend に fan-out
)
pm = PersonalMemory(user_id="alice", backend=composite)
```

```python
# B. 動的ルーティング — クエリ内容に応じて最適バックエンドを選択
from praxia.memory.router import RoutedBackend, RuleRouter

routed = RoutedBackend(
    backends={
        "mem0":      load_backend("mem0"),
        "zep":       load_backend("zep"),
        "hindsight": load_backend("hindsight"),
        "json":      load_backend("json"),
    },
    router=RuleRouter(),   # または LLMRouter(llm=praxia.llm) で LLM 判定
    write_to="mem0",
)
pm = PersonalMemory(user_id="alice", backend=routed)
```

ルールルータは英語と日本語の両方を判定:
時系列 (`last week` / `先月`) → Zep、監査 (`changelog` / `履歴`) → JSON、
エンティティ (`who is` / `について`) → Mem0、類似 (`類似`) → HindSight。

戦略一覧と性能トレードオフは [FEATURES.md § 5.1](FEATURES.md#51-multi-ltm-fusion--dynamic-routing-accuracy-boost) を参照。

## 8. 個人 → 組織メモリの蒸留

```bash
praxia consolidate --dry-run                 # 何が昇格されるかを事前確認
praxia consolidate --threshold 0.75          # 本番閾値
praxia freeze --block team_norms             # 安定したブロックを git 管理 Markdown に
```

## 8a. 本番運用 OAuth + KMS 暗号化

複数ワーカ / 複数ホスト構成では FastAPI サーバを稼動させ、KMS アダプタを構成:

```bash
# server + KMS extras を install
pip install "praxia[server,kms-aws]"   # kms-azure / kms-gcp / kms-vault も可

# redirect URI を安定化
export PRAXIA_PUBLIC_URL=https://praxia.example.com

# KMS 包絡暗号化を有効化
export PRAXIA_KMS_ADAPTER=aws
export PRAXIA_KMS_KEY_ID=arn:aws:kms:us-east-1:111122223333:key/...

praxia serve --host 0.0.0.0 --port 8000
```

`/api/v1/oauth/{provider}/` 配下で以下を提供:
- `POST /start` — 現在ユーザの authorize URL を構築
- `GET /callback` — IdP redirect 受信、code 交換、トークン保存
- `GET /status` — トークン保有状況 + 有効期限
- `DELETE` — ローカル失効

state は TTL 付き JSON でワーカ間共有されるため、redirect はどの replica に届いても OK。

## 8b. A/B 実験

```bash
# 実験定義 (DRAFT)
praxia experiment create proposal_v2 \
    --name "提案文プロンプト: 短/長 比較" \
    --variants '{"control":{"prompt":"<800字>"},"candidate":{"prompt":"<400字>"}}' \
    --traffic-split "control=0.5,candidate=0.5"

# 開始
praxia experiment start proposal_v2

# 一定数のアウトカム記録後に結果確認
praxia experiment results proposal_v2
# → 🏆 暫定 winner: candidate (confidence 0.41)
```

スキル / フロー内でユーザの variant を取得:

```python
from praxia.experiments import ExperimentRegistry

reg = ExperimentRegistry()
variant = reg.assign("proposal_v2", user_id="alice", role="member")
prompt = variant.payload["prompt"] if variant else default_prompt
```

同ユーザは実験期間中常に同 variant を見ます (SHA-256 バケット)。アウトカムは `record_outcome()` 経由で記録 → variant 別に集計。

## 8c. LLM 出力品質評価

```bash
# 既定スキップ (実 API キー + トークン消費)
pytest tests/llm_eval -m llm_eval -v

# 既知良好状態でベースライン更新
pytest tests/llm_eval --update-baselines

# 別モデルで比較
pytest tests/llm_eval --llm-eval-model gpt-4o
```

各 PR がベースラインと比較され、5pt 超のスコア低下で CI が落ちます。詳細: [docs/EVALUATION.ja.md](EVALUATION.ja.md)

## 9. ユーザ委譲 OAuth (エンタープライズ推奨)

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

## 10. 管理操作

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

## 11. リソース一覧

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

詳細は [docs/FEATURES.md](FEATURES.md) / [docs/PLUGINS.md](PLUGINS.md)、または <https://github.com/praxia-dev/praxia/issues> へ。
