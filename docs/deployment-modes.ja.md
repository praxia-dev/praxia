# デプロイモード

> 🇬🇧 English: [deployment-modes.md](deployment-modes.md)

Praxia は 2 つの構成要素から成り、組み合わせは自由です:

* **バックエンド** — オーケストレータ・メモリ層・スキル・フロー・LLM クライアント・認証認可・コネクタ・エクスポータ。Pure Python の SDK で組み込むか、FastAPI 経由で HTTP として叩けます。
* **フロントエンド** — `praxia ui` で起動する Streamlit UI。**任意**。独自のフロントに置き換えられます。

ユーザがよく選ぶ 2 つの構成:

| モード | 動かすもの | 向いているケース |
|---|---|---|
| **A. フルスタック** (Praxia フロント + バック) | `praxia ui` を同一ホストで起動 | 内製ツール / 単一チーム / 最短で動かす |
| **B. バックエンドのみ** (フロントは自前 / Praxia コアのみ) | Python SDK で埋め込む or `praxia serve` を立てて HTTP で呼ぶ | 既にポータル / モバイル / Slack ボットがあり Praxia を裏で使いたい |

両モードとも **設定・認証・メモリ・スキルは共通**。違いは **UI を誰が持つか** だけです。

---

## モード A. フルスタック (Streamlit UI 同梱)

最短で動かすなら一択。1 プロセスで全機能。

### A-1. インストール
```bash
pip install "praxia[ui,connectors,office]"
```

### A-2. 一度だけ設定
```bash
cp .env.example .env       # 最低 1 つの LLM キーを記入
praxia config init
```

### A-3. ストレージ + 管理者ユーザの初期化
```bash
praxia init --user-id admin --backend mem0
# 管理者の bootstrap API キーが 1 度だけ表示される — 必ず保管
```

### A-4. 起動
```bash
praxia ui --port 8501
# http://localhost:8501 を開く
```

11 タブ (Run Flow / Skill / Memory / Consolidate / Dashboard / Prompts / Users / Connectors / Policies / Admin / About) が利用可能。Streamlit は A-3 で発行された API キーで認証します。

### A-5. (任意) 公開 URL に乗せる
- **nginx / Caddy / Cloudflare Tunnel** の背後で TLS 終端 → `localhost:8501` へリバースプロキシ
- **Docker** — 上記手順をベースに自前 Dockerfile を用意 (公式 Dockerfile は今後追加予定)
- **Kubernetes** — Deployment 1 本 + `.praxia/` 用 PersistentVolumeClaim

Streamlit UI は SDK の薄いラッパなので、UI で見えるものは全て SDK でも操作できます。

---

## モード B. バックエンドのみ (フロントは自前)

統合方法は 2 通り:

### B-1. Python SDK で埋め込む (in-process)

フロントが既に Python (FastAPI / Django / Flask / Slack ボット / モバイル API) なら、`import praxia` するだけ:

```python
from praxia import Praxia, LLM
from praxia.skills.business import InvestmentSkill
from praxia.skills.output_format import OutputFormatSkill

loom = Praxia(user_id="alice", llm=LLM("claude"))

# 1. ドメインスキルを実行 → Markdown が返る
md = InvestmentSkill(llm=loom.llm).run("仮想中堅銘柄の Q3 レビュー")

# 2. ユーザの要求形式にレンダリング
result = OutputFormatSkill().deliver(md, user_request="パワポで")
return result.bytes  # ← application/vnd.openxmlformats-... で配信
```

これだけ。FastAPI のエンドポイントが本体、Praxia はライブラリ扱い。

### B-2. HTTP サービスとして動かす (out-of-process)

フロントが Python 以外 (Next.js / モバイル / Go 等) のときは HTTP の境界が必要。FastAPI ラッパが同梱されています:

```bash
pip install "praxia[server]"
praxia serve --host 0.0.0.0 --port 8000
```

エンドポイント (`/api/v1` 配下):

| エンドポイント | メソッド | 用途 |
|---|---|---|
| `/api/v1/auth/login` | POST | API キー → JWT 交換 |
| `/api/v1/flows/{name}` | POST | フロー実行 |
| `/api/v1/skills/{name}` | POST | スキル単発実行 |
| `/api/v1/memory/search` | POST | 個人メモリのセマンティック検索 |
| `/api/v1/memory/mode` | PUT | accumulate / read_only 切替 |
| `/api/v1/export` | POST | html/pptx/docx/json レンダリング |
| `/api/v1/oauth/{provider}/start` | POST | ユーザ委譲 OAuth 開始 |
| `/api/v1/oauth/{provider}/callback` | GET | OAuth コールバック |

認証: `Authorization: Bearer <jwt>` (`/auth/login` で発行) または `X-API-Key: <raw>`。RBAC・監査ログは SDK / UI と完全共通。

> **注**: FastAPI ラッパは `praxia.server.app` モジュール。未配線エンドポイントが必要な場合は (a) SDK を直接使った独自 FastAPI で拡張、(b) GitHub Issue で要望ください。

---

## バックエンド (LTM) の選択

どのモードでも LTM は設定可能:

| 設定 | 場所 | 効果 |
|---|---|---|
| `PRAXIA_MEMORY_BACKEND` 環境変数 | `.env` / shell | 全員のデフォルトバックエンド |
| `praxia admin memory-policy-set --enforced-backend mem0` | CLI | 全ユーザを 1 つのバックエンドに固定 |
| `praxia memory backend --user-id alice mem0` | CLI | ユーザ毎の個人設定 (admin 制約に従う) |
| `PersonalMemory(..., backend=CompositeBackend(...))` | SDK | 呼び出し毎の複数 LTM 合成 (詳細: [FEATURES.md § 5.1](FEATURES.md#51-multi-ltm-fusion--dynamic-routing-accuracy-boost)) |

優先順位: admin enforced > 呼び出し時の引数 > user pref > admin default > `"json"`

---

## ユーザ毎の accumulate / read-only モード

両モード共通でユーザ毎の切替が可能:

```bash
praxia memory mode --user-id alice accumulate   # 書き込み有効 (既定)
praxia memory mode --user-id alice read_only    # 書き込みは無効化 (検索は可)
praxia memory show --user-id alice              # 現在の解決済み設定を表示
```

**read_only** では `record_episode / record_fact / record_outcome / record_preference` が no-op に。記憶を残さずに使いたい場合 (法務文書レビュー / 機微データ探索) に有効。

管理者はテナント全体や特定ロールに対してロック可能:
```bash
praxia admin memory-policy-set --default-mode read_only --mode-locked
praxia admin memory-policy-set --accumulate-locked-roles operator,admin
```

---

## 本番チェックリスト

| 項目 | モード A (フルスタック) | モード B (バックエンドのみ) |
|---|---|---|
| TLS 終端 | nginx / Caddy / Cloudflare Tunnel → `:8501` | 同左、`:8000` 向け |
| 永続ストレージ | PersistentVolume / EBS で `.praxia/` を保護 | 同左 |
| 管理者キーの初期発行 | `praxia init` 出力を保管、`praxia user rotate-key` でローテート | 同左 |
| LLM プロバイダキー | `.env` / `praxia config set` / クラウドのシークレットマネージャ | 同左 |
| OAuth コールバック | `https://host/oauth/callback` (Streamlit が処理) | `/api/v1/oauth/{provider}/callback` |
| 監査ログ保管 | `.praxia/audit/` の append-only JSONL を日次バックアップ | 同左 |
| レート制限 | Streamlit に組込みなし → WAF / nginx で制御 | FastAPI に slowapi 等のミドルウェアを追加 |
| マルチテナント分離 | 1 プロセス = 1 テナント (`.praxia/` をテナント毎に分離) | 同左 — プロセス分離 or `org_id` でシャーディング |

---

## A → B への移行タイミング

最初は A で。以下のいずれかが起きたら B へ移行:

1. 既存ポータルへの **シングルサインオン** が必要で Streamlit の認証では足りない
2. **モバイル / Python 以外のクライアント** (Slack / Teams 等) が必要
3. **UI の A/B テスト** をブレインの再デプロイなしでやりたい
4. **CDN キャッシュ済みフロントエンド資産** が欲しいが Streamlit では難しい

移行は機械的: Streamlit の各タブは SDK の関数呼び出し 1:1、SDK は HTTP エンドポイント 1:1 に対応します。
