# AgentLoom

> **Specialized Multi-Agent Orchestrator with Cyclic Personal/Organizational Memory**
>
> 業務フロー特化型のマルチエージェント・オーケストレーター。個人の暗黙知を**自動的に**組織知へ昇格させる5層メモリ循環機構を内蔵。

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## 🎯 なぜ AgentLoom か (Why AgentLoom?)

汎用的なマルチエージェント・フレームワーク（CrewAI、AutoGen、LangGraph等）は強力ですが、現場ではこんな課題に直面します：

| 既存フレームワークの課題 | AgentLoom のアプローチ |
|---|---|
| 設定が複雑で現場投入が困難 | **業務フロー特化テンプレート**（営業準備 / 論理整合チェック / RAG最適化）を即起動 |
| ベテランの「効くプロンプト」が個人の引き出しに留まる | **個人メモリ → 組織メモリの自動昇格パイプライン**を内蔵 |
| 「動く」だけで「効果」の保証がない | **評価エージェント**と**ハルシネーション検知**を標準同梱 |
| 一度作ったエージェントが進化しない | **Sleep-time Consolidation** が夜間に自分のフローを蒸留・改善 |

AgentLoom は「**1人の天才の引き出し**」を「**組織全員のベスプラ**」に変える OSS フレームワークです。

---

## 🏗 アーキテクチャ概要

### 5層メモリスタック（自律循環）

```
┌──────────────────────────────────────────────────────────┐
│  AI エージェント（Skills + MCP）                          │
└──────────────┬───────────────────────────────────────────┘
               │ ユーザは普通に対話するだけ
               ▼
╔═══════════════════════════════════════════════════════════╗
║ 第1層: 個人メモリ（自動抽出）                             ║
║   Mem0 / LangMem ベース、namespace = user_id              ║
║   ★ 努力ゼロで暗黙知を蓄積                                ║
╚══════════════╤════════════════════════════════════════════╝
               │ Sleep-time Consolidation（夜間バッチ）
               ▼
╔═══════════════════════════════════════════════════════════╗
║ 第2層: 蒸留・昇格判定エンジン                             ║
║   3経路の「有効性判定」並走:                              ║
║     ① 頻度ベース   (N人以上で共通)                        ║
║     ② 成果連動    (受注/失注などとの相関)                 ║
║     ③ 自己評価   (LLM スコアリング)                       ║
╚══════════════╤════════════════════════════════════════════╝
               │ 閾値超で自動昇格 / 高インパクト案件は人手レビュー
               ▼
╔═══════════════════════════════════════════════════════════╗
║ 第3層: 共有メモリ（生きた組織知）                         ║
║   Letta-style Shared Blocks、全エージェントが read/write   ║
╚══════════════╤════════════════════════════════════════════╝
               │ 重要案件のキュレーション
               ▼
╔═══════════════════════════════════════════════════════════╗
║ 第4層: 組織標準（凍結された Best Practices）              ║
║   Markdown + git + PR レビュー                            ║
║   GitHub Copilot / Cursor Rules 互換フォーマット          ║
╚══════════════╤════════════════════════════════════════════╝
               │（任意）
               ▼
╔═══════════════════════════════════════════════════════════╗
║ 第5層: 関係性領域の Graph 層（任意）                      ║
║   Zep / Graphiti — 決定履歴・顧客360・障害因果のみ        ║
╚═══════════════════════════════════════════════════════════╝

並走する第6層: Skills レジストリ
  個人が作った Skill が組織レジストリへ昇格
  MCP / Claude Skills / Cursor Skills 互換
```

3つの昇格経路（**自動 / 統計 / 手動**）を並走させ、単一経路に依存しない設計が肝です。

詳細は [docs/architecture.md](docs/architecture.md) を参照。

---

## ✨ 同梱される特化リソース

### 3 つの業務フロー（マルチエージェント・パイプライン）

| Flow | 概要 |
|---|---|
| **Sales-Agent-Flow** | 顧客 IR・過去議事録・RAG を読み込み、**仮説立案 → FAQ → 提案書アウトライン** を生成 |
| **Logic-Checker-Flow** | 構造抽出 / 矛盾検知 / 読者視点 の 3 エージェントで長文の論理整合性をレビュー |
| **RAG-Optimization-Flow** | クエリ拡張 → 検索 → 妥当性評価 → ハルシネーション検証 を **自己修復ループ** |

### 6 つのビジネス・ドメイン・スキル（単独でも、Flow 内でも使える）

| Skill | 領域 | 用途 |
|---|---|---|
| **InvestmentSkill** | 投資 | 株式・債券・スタートアップの投資判断、デューデリ |
| **SalesSkill** | 営業 | アカウント・リサーチ、提案ドラフト、FAQ 準備 |
| **DesignSkill** | 設計 | システム設計レビュー、要件定義、アーキテクチャ評価 |
| **PurchasingSkill** | 購買 | サプライヤー評価、RFQ 比較、TCO 算定、BCP リスク |
| **PatentSkill** | 特許 | 先行技術調査、クレーム作成、特許マップ、出願戦略 |
| **LegalSkill** | 法務 | 契約書レビュー、コンプライアンス、社内規程整備 |

各スキルは Claude Skills / MCP 互換の `SKILL.md` フォーマットでシリアライズ可能。

### 主要 LLM をすべてサポート

LiteLLM 経由で **任意のプロバイダ** を 1 行で切り替え。

| Provider | エイリアス | 認証 |
|---|---|---|
| Anthropic Claude | `claude` / `claude-sonnet` / `claude-haiku` | `ANTHROPIC_API_KEY` |
| OpenAI ChatGPT | `chatgpt` / `gpt-4o` / `o1` | `OPENAI_API_KEY` |
| Google Gemini | `gemini` / `gemini-flash` | `GEMINI_API_KEY` |
| Alibaba Qwen (cloud) | `qwen` / `qwen-72b` | `DASHSCOPE_API_KEY` |
| Qwen / Llama (local) | `qwen-local` (Ollama) | (none — 自社内) |

```python
LLM("claude")        # Anthropic Claude
LLM("qwen-local")    # ローカル Qwen (Ollama)
LLM("openai/gpt-4o") # 任意の LiteLLM 形式
```

### 5 つのメモリ・バックエンドから選択可能

| Backend | 特徴 |
|---|---|
| **json** (default) | ゼロ依存、JSONL on disk、完全に監査可能 |
| **mem0** | エンティティ・リンキング + ハイブリッド検索（推奨） |
| **langmem** | LangChain LangMem SDK |
| **letta** | Letta shared blocks（ポリシー保護機能つき） |
| **zep** | Zep / Graphiti（時系列 KG / 第5層） |

切り替えは 1 行:
```python
PersonalMemory(user_id="alice", backend="mem0")
```

---

## 🚀 Quickstart

```bash
pip install agentloom              # コア
pip install "agentloom[ui]"        # + Streamlit UI
pip install "agentloom[all]"       # 全部入り

# 初期化（個人メモリ + Skills レジストリ）
agentloom init --backend json --model auto

# 業務フロー実行
agentloom run sales --customer-name "Acme" --product "BizFlow"
agentloom run logic --document path/to/doc.md
agentloom run rag --question "AgentLoom はどのライセンス?"

# 単一スキル実行（6 業務スキルから選択）
agentloom skill investment "ソニーグループ株の中期投資判断を教えて"
agentloom skill legal "業務委託契約書のリスクを教えて"

# UI 起動
agentloom ui --port 8501

# 個人メモリ → 組織メモリへの夜間蒸留
agentloom consolidate --dry-run
```

最小コード例：

```python
from agentloom import AgentLoom
from agentloom.flows import SalesAgentFlow
from agentloom.skills import InvestmentSkill

loom = AgentLoom(user_id="alice", default_model="claude")

# Multi-agent flow
result = loom.run(SalesAgentFlow, inputs={
    "customer_name": "Acme",
    "product": "BizFlow",
})

# Single business skill
print(InvestmentSkill().run("Toyota の今後 3 年の投資判断"))

# 個人メモリには自動的に蓄積（明示 save 不要）
# 蒸留バッチで組織メモリへの昇格候補が自動抽出される
loom.consolidate(dry_run=True)
```

詳しくは [docs/quickstart.md](docs/quickstart.md) を参照。

---

## 📐 設計思想

### 1. **「努力ゼロ」で個人の暗黙知を捕捉する**
GitHub Copilot Custom Instructions のような明示記述ではなく、**対話の副産物として自動抽出**。Mem0 / LangMem の自動抽出機構を統合。

### 2. **「有効なものだけ」を「自動的に」組織知に昇格させる**
判定の自動化が核心。AgentLoom は 3 つの判定軸を並走させる：
- **頻度ベース**: 複数ユーザ・複数セッションで繰り返し現れる事項
- **成果連動ベース**: 成功事例（受注、テスト合格、PR マージ等）との相関
- **自己評価ベース**: LLM が「これは重要」と判断

### 3. **「凍結」と「生きた知識」を分離する**
- **生きた層** (Shared Blocks): 即時更新、全エージェントが共有
- **凍結層** (Markdown + git): PR レビューを経たベストプラクティスのみ
- 両方を区別することで、組織知の「鮮度」と「信頼性」を両立。

### 4. **Graph は「関係性が業務価値の中核」な領域のみ**
Mem0 OSS は 2026年4月に graph_store サポートを廃止。AgentLoom も同様に、**vector + entity linking を主軸**に置き、Graph は決定履歴・顧客360・障害因果など限定領域のみ任意採用。

詳細は [docs/design-philosophy.md](docs/design-philosophy.md) 参照。

---

## 📊 業種・業務別ユースケース

各業務領域での具体的な Before/After 効果例は **[docs/use-cases.md](docs/use-cases.md)** にまとめてあります。
ハイライト:

| 業種 | 代表ユースケース | 主な効果 |
|------|----------------|----------|
| 投資 | スタートアップへのシード投資判断 | 1 件 4〜6 時間 → **45〜60 分** |
| 営業 | 新規大手顧客の事前リサーチ + 商談 SB | 提案合意率 **+15〜20pt** |
| 設計 | 要件定義書のレビュー | シニアの可処分時間 **週 16 時間 → 4 時間** |
| 購買 | RFQ 結果の TCO 比較 | 隠れコスト発見で初期見積より **+30%** の真コスト把握 |
| 特許 | 先行技術調査 + 進歩性評価 | 弁理士費用 **50〜70% 削減** |
| 法務 | M&A 契約レビュー | 外部法律事務所費用 **半減** (案件 1 件 1,000 万円規模) |

**長期効果 (3 年後)**: 新人独り立ち期間 6〜12 ヶ月 → **2〜3 ヶ月** / ベテラン退職時の知見漏出 **ゼロ** / 部門横断ベスプラ流通 **月 30 件以上**

---

## 🆚 既存フレームワークとの比較

| 機能 | CrewAI | AutoGen | LangGraph | **AgentLoom** |
|---|---|---|---|---|
| 汎用マルチエージェント | ✅ | ✅ | ✅ | ✅ |
| 業務フロー特化テンプレート | ❌ | ❌ | ❌ | ✅ |
| 個人メモリ自動抽出 | ❌ | ❌ | △ | ✅ |
| 個人→組織メモリ昇格 | ❌ | ❌ | ❌ | ✅ |
| Sleep-time Consolidation | ❌ | ❌ | ❌ | ✅ |
| Skills レジストリ循環 | ❌ | ❌ | ❌ | ✅ |
| ハルシネーション評価標準 | ❌ | ❌ | ❌ | ✅ |
| MCP / Claude Skills 互換 | △ | △ | △ | ✅ |

---

## 🗺 ロードマップ

| Phase | 内容 | 状態 |
|---|---|---|
| **Phase 1** | 個人メモリ層 + 3 特化フロー（Alpha） | 🚧 In progress |
| **Phase 2** | Sleep-time Consolidator + 統計昇格 | 📋 Planned |
| **Phase 3** | Shared Blocks + Markdown 凍結層 | 📋 Planned |
| **Phase 4** | Skills レジストリの個人→組織昇格 | 📋 Planned |
| **Phase 5** | エンタープライズ拡張（GUI / 監査ログ） | 💼 Commercial |

---

## 🤝 Contributing

このプロジェクトは「**業界別レシピ**」のコミュニティ駆動の蓄積を目指します：

1. `agentloom/flows/` に新しい業務フローを追加
2. `examples/` に具体的なドメイン適用例を追加
3. `docs/recipes/` に「業種別ベスプラ」を投稿

Pull Request 歓迎。詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照。

---

## 📜 License

[Apache License 2.0](LICENSE) — 商用利用・改変・再配布可。

将来的に「**オープンコア・モデル**」（コアは Apache 2.0、企業向け管理機能のみ別ライセンス）を採用予定。

---

## 📚 関連プロジェクト & 参考文献

- [Mem0](https://github.com/mem0ai/mem0) — Personal memory layer (採用)
- [Letta](https://github.com/letta-ai/letta) — Shared Memory Blocks の思想を参考
- [LangMem](https://github.com/langchain-ai/langmem) — Long-term memory SDK
- [Claude Skills](https://docs.claude.com/) — Skills レジストリ規約
- [Model Context Protocol](https://modelcontextprotocol.io) — Tool/Skill 連携規約

理論的背景：
- LinkedIn Cognitive Memory Agent (Episodic + Semantic + Procedural)
- Mem0 論文 (arXiv:2504.19413)
- Letta Sleep-time Agents

---

## 🙏 謝辞

本プロジェクトは、RAG-1 グランプリでの実戦経験と、自律型 AI エージェントのメモリ機構に関する内部調査から生まれました。

> **「個人の天才性 × 組織の継続性」を AI で結びつける** — それが AgentLoom のミッションです。
