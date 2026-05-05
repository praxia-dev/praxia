---
title: "Praxia — 個人の暗黙知を組織知に自動昇格させるマルチエージェントOSSを作った"
emoji: "🪡"
type: "tech"
topics: ["AI", "LLM", "RAG", "agent", "Python"]
published: false
---

![Praxia](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/hero-banner.svg)

> **TL;DR**
> ベテランの「効くプロンプト」が個人の引き出しに留まる問題を解消するため、**業務フロー特化型マルチエージェント・オーケストレーター + 個人→組織メモリ自動循環機構** を持つ OSS「Praxia」を作りました。Apache 2.0 で公開。**6 業務領域** (投資/営業/設計/購買/特許/法務) のスキルが標準同梱、**SSO + RBAC + 監査ログ** も組み込み済みです。

> **シリーズ記事**: 本記事は全体紹介。各業務での具体的な使い方は別記事に分けています。
> - **[本記事] 全体紹介** ← 今ここ
> - [💰 投資業務](#) (近日公開)
> - [📈 営業業務](#) (近日公開)
> - [🏗 設計業務](#) (近日公開)
> - [🛒 購買業務](#) (近日公開)
> - [📑 特許業務](#) (近日公開)
> - [⚖️ 法務業務](#) (近日公開)

## なぜ作ったか — 既存フレームワークでは届かない 4 つの壁

LLM アプリケーション開発の現場で、CrewAI / AutoGen / LangGraph のようなマルチエージェント・フレームワークを使ってきて、こんな課題を繰り返し見てきました。

| 課題 | 何が起きているか |
|------|-----------------|
| 設定が複雑 | 「とりあえず動く」までに2〜3日。本番投入の判断が下せない |
| ベテランの暗黙知が届かない | 「効くプロンプト」は本人の Cursor / VSCode に埋もれたまま |
| 評価のエビデンスがない | 「動く」が「効く」を保証しない。担当者の信頼を得られない |
| エージェントが進化しない | 一度作ったら停滞。改善のフィードバック・ループが回らない |

特に深刻なのは2番目です。RAG-1 グランプリで2位を取った経験から確信したのですが、**RAG の精度を本当に分ける要素は、ライブラリ選定でもモデル選定でもなく、「ドメイン特化の試行錯誤の蓄積」** です。そしてその蓄積はほぼ必ず特定の個人の頭の中に閉じ込められています。

これを **自動的に** 組織知へ昇格させる仕組みが、今のフレームワーク群には欠けていました。

## Praxia の差別化 — 22 の独自優位性

### 1〜12: コアフレームワーク
| # | 優位性 | 一言 |
|---|---|---|
| 1 | 個人 → 組織メモリ循環 | 業界唯一の「使うだけで組織知が育つ」機構 |
| 2 | 3 経路の昇格判定 | 頻度 / 成果連動 / LLM 自己評価 を並走 |
| 3 | 業務特化フロー 3 種 | 営業準備 / 論理整合 / RAG 自己修復 |
| 4 | 業務スキル 6 種 | 投資 / 営業 / 設計 / 購買 / 特許 / 法務 |
| 5 | エビデンス標準同梱 | ハルシネーション検知 + 検索メトリクス |
| 6 | LTM バックエンド 6 種 | json / mem0 / langmem / letta / zep / hindsight |
| 7 | 主要 LLM 全対応 | Claude / ChatGPT / Gemini / Qwen + 100+ |
| 8 | 認証認可 SSO 監査が OSS に | API Key + JWT + OIDC + 4 ロール + 監査ログ |
| 9 | スキル自体も昇格 | 個人で磨いたスキルが組織レジストリへ |
| 10 | MCP / Claude Skills 互換 | `SKILL.md` 形式でシリアライズ |
| 11 | 成果トラッキング標準 | `record_outcome()` で受注/失敗を学習 |
| 12 | Apache 2.0 + Open Core | 商用利用可、エンタープライズ拡張へのパス明確 |

### 13〜22: エンタープライズ運用 + 入出力機能 (NEW)
| # | 優位性 | 一言 |
|---|---|---|
| 13 | 管理者ユーザ CRUD | 作成/編集/削除/有効化/キーローテーション、全操作監査 |
| 14 | リソースアクセスポリシー (ACL) | 情報システム部向け Glob ベース allow/deny |
| 15 | 管理者データダウンロード | 監査ログ/ユーザ/メモリ/ポリシー を CSV/JSON でエクスポート |
| 16 | カスタムプロンプト管理 | 個人/組織/配信の 3 スコープ、管理者がロール単位で配信可能 |
| 17 | 6 つの外部コネクタ (Pull + Push) | Box / SharePoint / Dropbox / GDrive / kintone / Salesforce |
| 18 | 個人 / 組織ダッシュボード | フロー数・スキル使用量・成果率・トークン消費を可視化 |
| 19 | **ファイルパーサー 13 拡張子** | PDF / Word / PowerPoint / Excel / CSV / HTML / Markdown 等を自動解析 |
| 20 | **音声入出力 (STT + TTS)** | Whisper / OpenAI TTS / ElevenLabs / ローカル Whisper・Piper |
| 21 | **ユーザ委譲 OAuth** | Box/MS/Dropbox/Google/Salesforce — 連携先 ACL がユーザ単位で適用 |
| 22 | **統一設定システム** | 全鍵を 1 箇所で管理 (`.env` / `praxia config show/set/init`) |

## アーキテクチャ — 5 層スタック + Skills レジストリ

![Architecture](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/architecture.svg)

メモリ循環の流れ:

![Memory cycle](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/memory-cycle.svg)

ASCII 表示:

```
個人メモリ (Layer 1)         ← ユーザは普通に使うだけ。明示的な save 不要
      │  Sleep-time Consolidation (Layer 2)
      │  3 経路並走 (頻度 / 成果 / 自己評価)
      ▼
共有メモリ (Layer 3)         ← 全エージェントが即時参照
      │  PR レビュー
      ▼
Markdown 凍結層 (Layer 4)   ← git 履歴管理されたベスプラ
      │  (任意)
      ▼
Graph 層 (Layer 5)           ← 関係性が業務価値の中核な領域のみ

並走 Layer 6: Skills レジストリ
+ 横断 Layer: Auth / RBAC / Audit / SSO
```

### 個人メモリの自動抽出 (Layer 1)

```python
from praxia import Praxia
from praxia.flows import SalesAgentFlow

p = Praxia(user_id="alice", default_model="claude")
result = p.run(SalesAgentFlow, inputs={...})
# 個人メモリに自動蓄積。明示的な save() 不要。
```

### 3 経路昇格エンジン (Layer 2)

```python
from praxia.memory.promoter import PromotionEngine

engine = PromotionEngine(
    llm=llm,
    weights=(0.4, 0.3, 0.3),  # 頻度 / 成果 / 自己評価
    auto_threshold=0.75,        # この値以上で自動昇格
    review_threshold=0.5,       # この値以上で人手レビュー
)
```

3 つの判定軸を **並走** させ、単一経路に依存しない設計が肝です:
- **頻度ベース**: N人以上で繰り返される事項
- **成果連動**: `record_outcome()` で記録された結果との相関
- **自己評価**: LLM が「組織知候補度」を 0..1 でスコアリング

### Markdown 凍結層 (Layer 4)

```bash
praxia freeze --block manufacturing_pain_hypotheses
# → .praxia/frozen/instructions/manufacturing_pain_hypotheses.md (git-tracked)
```

## UI ツアー (Streamlit)

11 タブで全機能にアクセスできます:

| タブ | 画面イメージ |
|---|---|
| 🎬 Run Flow | ![Run Flow](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-run-flow.svg) |
| 📊 Dashboard | ![Dashboard](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-dashboard.svg) |
| 🛡 Policies (情報システム部向け ACL) | ![Policies](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-policies.svg) |
| 💾 Admin Downloads | ![Admin](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-admin-exports.svg) |

CLI も同じ機能を Rich 整形で:

![CLI](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/cli-terminal.svg)

## 使い方 — 5 分で動く

```bash
# インストール (必要なエクストラだけ追加)
pip install "praxia[ui,connectors,office,audio]"

# 設定は一箇所に集約 (.env / praxia config / 環境変数 のいずれか)
praxia config init      # インタラクティブに鍵を入力
# または: cp .env.example .env して編集

# 初期化 (個人メモリ + スキルレジストリ + admin ユーザ作成)
praxia init

# 業務フロー実行
praxia run sales --customer-name "Acme" --product "BizFlow"

# 単一スキル実行 (6 業務領域)
praxia skill run investment "中堅電機メーカー (架空) の中期投資判断"
praxia skill run legal "業務委託契約書のリスクをレビュー"

# UI 起動 (11 タブ: Run / Skill / Memory / Consolidate / Dashboard /
# Prompts / Users / Connectors / Policies / Admin / About)
praxia ui --port 8501

# 個人メモリ → 組織メモリの蒸留
praxia consolidate --dry-run
praxia freeze --block team_norms

# ダッシュボード
praxia dashboard --scope personal --user-id alice
praxia dashboard --scope org

# 管理者: ユーザ CRUD
praxia user create alice --role member
praxia user update alice --role operator --email alice@a.test
praxia user deactivate alice
praxia user delete alice --yes
praxia user audit --limit 100

# 管理者: アクセスポリシー (情報システム部向け)
praxia policy add deny connector "box:/Confidential/*" \
    --principals "role:member,role:viewer" \
    --description "機密フォルダはオペレーター以上のみ"
praxia policy list
praxia policy test alice member connector box:/Confidential/q3.pdf read

# 管理者: データダウンロード (CSV/JSON、自身も監査される)
praxia admin export-audit audit.csv --since-days 30
praxia admin export-users users.json --format json
praxia admin export-memory ./backup --all
praxia admin export-policies policies.json

# 外部システム連携 (Pull / Push、ACL 適用)
praxia connector list
praxia connector pull box 0 --limit 20 --save-to ./box_pulled
praxia connector pull salesforce "SELECT Id, Name FROM Account"
praxia connector push gdrive 0AbCdEf review.md

# カスタムプロンプト
praxia prompt create my_qualifier prompt.txt
praxia prompt distribute curated_pricing body.md --target-roles member

# スキル: 昇格 + 配信
praxia skill promote --candidates
praxia skill distribute investment_analyst --target-roles member,operator
```

## 同梱業務スキル 6 種

| Skill | 領域 | 主用途 |
|---|---|---|
| **InvestmentSkill** | 投資 | 株式・債券・スタートアップ投資判断、デューデリ |
| **SalesSkill** | 営業 | アカウント・リサーチ、提案ドラフト、FAQ 準備 |
| **DesignSkill** | 設計 | システム設計レビュー、要件定義、アーキ評価 |
| **PurchasingSkill** | 購買 | サプライヤー評価、RFQ 比較、TCO、BCP リスク |
| **PatentSkill** | 特許 | 先行技術調査、クレーム作成、特許マップ |
| **LegalSkill** | 法務 | 契約書レビュー、コンプライアンス、M&A デューデリ |

各スキルには **業界フレームワーク** (例: 法務の RACE、購買の QCD+S) と **ガードレール** (士業ライセンス遵守、個人情報保護等) が組み込まれています。

具体的な業務での使い方とビフォア/アフターは、各業務別記事を参照してください。

## サポート LLM (主要全対応)

LiteLLM 経由で 100+ プロバイダ対応:

```python
LLM("claude")        # Anthropic Claude (推奨)
LLM("chatgpt")       # OpenAI GPT-4o / o1
LLM("gemini")        # Google Gemini 2.0
LLM("qwen")          # Alibaba Qwen Max (DashScope API)
LLM("qwen-local")    # Qwen ローカル (Ollama 経由)
LLM("openai/gpt-4o") # 任意の LiteLLM 形式
```

**完全オフライン運用** も可能 (Qwen-local + JSON memory backend)。

## サポート LTM バックエンド 6 種

| Backend | 自動抽出 | ベクトル検索 | エンティティ・リンキング | 推奨用途 |
|---|---|---|---|---|
| **json** (default) | ❌ | BM25 風 | ❌ | 開発・小規模 |
| **mem0** | ✅ | ✅ ハイブリッド | ✅ | 本番・推奨 |
| **langmem** | ✅ | ✅ | ✅ | LangChain 既存ユーザ |
| **letta** | ✅ | ✅ | ❌ | Letta 共有ブロック使用 |
| **zep** | ✅ | ✅ | ✅ + 時系列 KG | Layer 5 関係性領域 |
| **hindsight** | ✅ | ✅ | ❌ | vectorize-io インテグ |

### 複数 LTM の同時利用 — 精度を上げるための合成プリミティブ

「どの LTM が一番優秀か」を選ぶゲームを終わらせるための合成機構を 2 つ用意:

```python
# A. CompositeBackend: 並列に問い合わせて Reciprocal Rank Fusion で融合
from praxia.memory.composite import CompositeBackend, WeightedBackend
from praxia.memory.backends import load_backend

composite = CompositeBackend(
    backends=[
        WeightedBackend("mem0",      load_backend("mem0"),      weight=1.5),
        WeightedBackend("zep",       load_backend("zep"),       weight=1.0),
        WeightedBackend("hindsight", load_backend("hindsight"), weight=1.0),
        WeightedBackend("json",      load_backend("json"),      weight=0.5),
    ],
    fusion="rrf",       # rrf | union | intersection | weighted | llm_rerank
    write_to="mem0",    # 書き込みは1つに、検索だけ fan-out
)
PersonalMemory(user_id="alice", backend=composite)
```

```python
# B. RoutedBackend: クエリ内容に応じて最適なバックエンドを動的選択
from praxia.memory.router import RoutedBackend, RuleRouter

routed = RoutedBackend(
    backends={"mem0": ..., "zep": ..., "hindsight": ..., "json": ...},
    router=RuleRouter(),   # または LLMRouter(llm=...) で LLM 判定
    write_to="mem0",
)
```

`RuleRouter` は英語と日本語の両方を判定:
- 時系列クエリ (`last week` / `先月`) → **Zep** 優先
- 監査クエリ (`changelog` / `履歴`) → **JSON** 優先
- エンティティ問い合わせ (`who is` / `について`) → **Mem0** 優先
- 類似検索 (`類似`) → **HindSight** 優先

ベンチマークなしで「とりあえず複数併用 → RRF で融合」が再現率の高い堅実な
ベースラインです。レイテンシが気になるユースケースには `RoutedBackend` で
クエリ毎にシングルバックエンドを当てる構成が向きます。

## 認証・認可・監査・SSO

```python
from praxia.auth import AuthManager, Role, google_provider

auth = AuthManager()
user, key = auth.create_user("alice", role=Role.MEMBER)

# SSO 連携
auth.attach_sso(google_provider(
    client_id="...", client_secret="...",
    redirect_uri="https://praxia.example.com/cb",
))

# RBAC
auth.require(user, "promote_skills")  # PermissionError if denied

# 監査ログ
events = auth.audit.tail(limit=50)
```

**4 ロール**: `admin` / `operator` / `member` / `viewer`
**SSO 対応**: Google / Microsoft Entra ID / Okta / GitHub / Keycloak / 汎用 OIDC + SAML スケルトン

これらが **OSS コアに含まれている** のが Praxia の特徴です。多くの競合フレームワークでは有償プラグインです。

## エンタープライズ運用機能 (情報システム部向け)

### リソースアクセスポリシー (ACL)

Glob パターンの allow/deny ルールで、外部コネクタや組織メモリへのアクセスを細かく制御:

```python
auth.policies.add(
    effect="deny",
    resource_type="connector",
    resource_pattern="box:/Confidential/*",
    actions=["read", "write"],
    principals=["role:member", "role:viewer"],
    description="機密フォルダはオペレーター以上のみ",
)

# 評価
decision = auth.policies.evaluate(
    user_id="alice", role="member",
    resource_type="connector",
    resource_id="box:/Confidential/q3.pdf",
    action="read",
)
print(decision.allowed, decision.reason)
# False, "matched policy abc... (deny: 機密フォルダは...)"
```

すべてのポリシー評価が監査ログに記録されます (`action="policy.eval.read"`)。

### 管理者データダウンロード

監査・コンプライアンス・SIEM 連携・バックアップ用途:

```python
auth.exports.export_audit(output_path="audit.csv", since=time.time() - 30*86400)
auth.exports.export_users(output_path="users.json", format="json")
# api_key_hash, password_hash は自動除去される
auth.exports.export_personal_memory(user_id="alice", output_path="alice.jsonl")
auth.exports.export_all_personal_memory(output_dir="./backup")
auth.exports.export_policies(output_path="policies.json")
```

**チェーン・オブ・カスタディ**: export 操作自体も `action="export.audit"` 等で監査ログに記録されます。

### 6 つの外部コネクタ (Pull + Push)

| Connector | Pull | Push | 認証 |
|---|---|---|---|
| **Box** | フォルダ ID → ファイル | フォルダへアップロード | OAuth2 / JWT |
| **SharePoint / M365** | ドライブフォルダ | アップロード | Microsoft Entra アプリ |
| **Dropbox** | フォルダ | アップロード | OAuth2 |
| **Google Drive** | 親フォルダ | アップロード | サービスアカウント / OAuth |
| **kintone** | アプリ + クエリ | レコード作成 | API トークン / 基本認証 |
| **Salesforce** | SOQL | sObject create | ユーザ名/トークン / OAuth |

```bash
# Pull (Praxia 内のフロー入力に使う)
praxia connector pull box 0 --limit 20
praxia connector pull salesforce "SELECT Id, Name, Industry FROM Account WHERE Industry='Manufacturing'"
praxia connector pull kintone "42?status='open'"

# Push (Praxia の出力を社内システムへ書き戻す)
praxia connector push gdrive 0AbCdEf review.md
praxia connector push salesforce Lead lead.json
```

**ACL 強制**: Pull/Push は内部で `PolicyManager.require()` を呼ぶため、外部システムへ通信する前に管理者ポリシーで弾けます。

### カスタムプロンプト管理

3 つのスコープ (個人 / 組織 / 配信):

```python
from praxia.skills.prompts import PromptStore
store = PromptStore()

# 個人で保存
store.save_personal("alice", name="my_qualifier", body="...", tags=["sales"])

# 管理者がロールに配信
store.distribute(
    name="curated_pricing",
    body="...",
    target_roles=["member", "operator"],
)

# 効果的なビュー (個人 > 配信 > 組織 の優先順位でマージ)
visible = store.list_for_user(user_id="bob", role="member")
```

### 個人 / 組織ダッシュボード

```python
from praxia.analytics import Dashboard
d = Dashboard()

# 個人ダッシュボード
ps = d.personal_summary("alice")
# ps.flow_runs, ps.skill_runs, ps.memory_entries,
# ps.outcomes_recorded, ps.success_rate,
# ps.total_input_tokens, ps.total_output_tokens,
# ps.top_skills, ps.recent_episodes

# 組織ダッシュボード
os_ = d.org_summary("default-org")
# os_.active_users, os_.total_flow_runs,
# os_.org_success_rate, os_.promoted_blocks,
# os_.frozen_files, os_.distributed_skills,
# os_.distributed_prompts, os_.top_users, os_.top_skills
```

UI の 📊 Dashboard タブで両ビューがメトリクス + ランキング表で表示されます。

## 拡張性 — 30 行でカスタムフロー、20 行でカスタムスキル

### カスタム Flow

```python
from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM

class IncidentResponseFlow(Flow):
    name = "incident_response"
    description = "On-call incident triage + root cause + mitigation"

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()
        self.steps = [
            FlowStep("triage", Agent(name="triage", llm=llm,
                     system_prompt="You triage SRE alerts..."), inputs={...}),
            FlowStep("hypothesis", Agent(name="hypothesis", llm=llm,
                     system_prompt="You hypothesize root causes..."), inputs={...}),
            FlowStep("mitigation", Agent(name="mitigation", llm=llm,
                     system_prompt="You suggest mitigations..."), inputs={...}),
        ]
```

### カスタム Skill

```python
from praxia.skills.skill import Skill, SkillManifest

class HRRecruitingSkill(Skill):
    manifest = SkillManifest(
        name="hr_recruiting",
        description="Resume screening + interview question generation",
        domain="hr",
        tags=["recruiting", "screening"],
    )
    system_prompt = """あなたは HR リクルーティング専門エージェントです。
    [Role] 履歴書スクリーニング、インタビュー質問生成、強み/懸念のエビデンス付き提示
    [Guardrails] 保護属性 (年齢/性別/人種) を判断材料にしない、必ず履歴書の該当箇所を引用
    """
```

### カスタム LTM バックエンド

```python
class PineconeBackend:
    def add(self, *, user_id, text, kind, metadata): ...
    def search(self, *, user_id, query, limit): ...
    def all(self, *, user_id=None): ...
    def clear(self, *, user_id=None): ...
```

## ビジネスへの繋げ方 — オープンコア・モデル

| 層 | ライセンス | 提供形態 |
|---|---|---|
| コアフレームワーク | Apache 2.0 | OSS |
| エンタープライズ GUI / マルチテナント / 専任サポート | 有償 | エンタープライズ版 (将来) |
| 業界別の高精度プロンプト・データ | 有償 | コンサル / Vertical SaaS |

OSS で技術力と信頼を獲得しつつ、企業導入時に必要となる **付帯機能** で収益化する戦略です。

## 想定 ROI (100 名規模の中堅企業の例)

| 変数 | Year 1 | Year 2 |
|------|--------|--------|
| 対象社員 (N) | 100 | 100 |
| FTE 単価 (C) | ¥14M | ¥14M |
| ルーチン業務シェア (t) | 40% | 40% |
| 時間削減率 (s) | 35% | 60% |
| 品質効果 (Q) | ¥10M | ¥30M |
| Praxia コスト (P) | ¥12M | ¥12M |
| **純効果** | **¥194M** | **¥354M** |

3 年累積純効果 ≈ **¥800M**。各パラメータを半分にしても **10 倍超の ROI**。

## おわりに — Reasoning Engineer の時代へ

2026 年現在、AI 市場では **「誰でも作れるもの」には価値がつかない** 状況になっています。

これからの差別化要因は、技術そのものよりも **「Reasoning (推論) の質を評価・設計するスキル」** — つまり Reasoning Engineer の領域です。Praxia はこの領域での実践を OSS としてオープンに育てていきたいと思っています。

**「個人の天才性 × 組織の継続性」を AI で結びつける** — それが Praxia のミッションです。

⭐ Star / 🍴 Fork / Issue / PR をお待ちしています。
**[github.com/your-org/praxia](https://github.com/your-org/praxia)**

---

## 次の記事

各業務での具体的な活用例と Before/After を業務別に分けて解説しています:

- 💰 [投資業務での Praxia 活用](#) — VC ジュニア・アソシエイトが 4–6h → 45 min に
- 📈 [営業業務での Praxia 活用](#) — 提案合意率 +15–20pt の事前準備自動化
- 🏗 [設計業務での Praxia 活用](#) — シニア・アーキトの可処分時間を週 16h → 4h に
- 🛒 [購買業務での Praxia 活用](#) — TCO で初期見積より +30% の真コスト発見
- 📑 [特許業務での Praxia 活用](#) — 弁理士費用 50–70% 削減
- ⚖️ [法務業務での Praxia 活用](#) — M&A 外部法律事務所費用を半減

ご興味のある業務領域から、ぜひお読みください。
