---
title: "Praxia — 個人の暗黙知を組織知に自動昇格させるマルチエージェントOSSを作った"
emoji: "🪡"
type: "tech"
topics: ["AI", "LLM", "RAG", "agent", "Python"]
published: false
---

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

## Praxia の差別化 — 12 の独自優位性

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

## アーキテクチャ — 5 層スタック + Skills レジストリ

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

## 使い方 — 5 分で動く

```bash
pip install "praxia[ui]"

# API キー設定 (どれか一つでOK)
export ANTHROPIC_API_KEY=sk-ant-...   # または OPENAI / GEMINI / DASHSCOPE

# 初期化 (個人メモリ + スキルレジストリ + admin ユーザ作成)
praxia init

# 業務フロー実行
praxia run sales --customer-name "Acme" --product "BizFlow"

# 単一スキル実行 (6 業務領域)
praxia skill run investment "ソニーグループ株の中期投資判断"
praxia skill run legal "業務委託契約書のリスクをレビュー"

# UI 起動
praxia ui --port 8501

# 個人メモリ → 組織メモリの蒸留 (夜間バッチ)
praxia consolidate --dry-run

# スキル昇格 (個人 → 組織)
praxia skill promote --candidates
praxia skill promote --name my_skill --user-id alice

# ユーザ管理
praxia user create alice --role member
praxia user audit
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

OSS で技術力と信頼を獲得しつつ、企業導入時に必要となる **付帯機能** で収益化する戦略です。詳細は [docs/business-plan.ja.md](https://github.com/your-org/praxia/blob/main/docs/business-plan.ja.md) を参照。

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
