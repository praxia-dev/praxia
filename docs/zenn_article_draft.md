---
title: "AgentLoom — 個人の暗黙知を組織知に自動昇格させるマルチエージェントOSSを作った"
emoji: "🪡"
type: "tech"
topics: ["AI", "LLM", "RAG", "agent", "Python"]
published: false
---

> **TL;DR**
> ベテランの「効くプロンプト」が個人の引き出しに留まる問題を解消するため、**業務フロー特化型のマルチエージェント・オーケストレーター + 個人→組織メモリ自動循環機構** をもつ OSS「AgentLoom」を作りました。Apache 2.0 で公開しています。

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

## AgentLoom の差別化 — 4 つの設計思想

### 1. 「努力ゼロ」で個人の暗黙知を捕捉

GitHub Copilot Custom Instructions のような **明示記述** ではなく、Mem0 / LangMem を使って **対話の副産物として自動抽出** します。ユーザは普段通り使うだけ。

### 2. 「有効なものだけ」を「自動的に」組織知に昇格

判定の自動化が核心です。AgentLoom は **3 つの判定軸を並走** させます：

| 経路 | 駆動 |
|------|------|
| 自動 | Sleep-time agent + LLM 自己評価 |
| 統計 | 成果データとの相関分析（受注/失敗 etc.） |
| 手動 | PR レビュー / Q&A 投票 |

単一経路に依存しないことで、誤昇格を抑えつつ取りこぼしも防ぎます。

### 3. 「凍結」と「生きた知識」を分離

| 層 | 性質 | 例 |
|---|------|-----|
| Shared Blocks (Layer 3) | 即時更新、流動的 | 直近の有効パターン |
| Markdown + git (Layer 4) | PR レビュー必須、安定的 | 確定したベスプラ |

両者を区別することで、組織知の **鮮度と信頼性** を両立させます。

### 4. Graph 層は限定領域のみ

Mem0 OSS は 2026年4月に graph_store サポートを廃止しました。理由は **コスト 2倍 / レイテンシ 3倍 / 効果 +2pt 程度** で割に合わないから。AgentLoom もこのシグナルを真摯に受け止め、Vector + Entity Linking を主軸に置き、Graph は **関係性が業務価値の中核** な領域（決定履歴 / 顧客360 / 障害因果）のみ任意採用としています。

## アーキテクチャ — 5 層スタック + Skills レジストリ

```
┌──────────────────────────────────────────────┐
│  AI エージェント (Skills + MCP)              │
└─────────────────┬────────────────────────────┘
                  │ ユーザは普通に対話するだけ
                  ▼
╔══════════════════════════════════════════════╗
║ 第1層: 個人メモリ (自動抽出)                  ║
║   Mem0 / LangMem ベース                       ║
╚═════════════════╤════════════════════════════╝
                  │ Sleep-time Consolidation
                  ▼
╔══════════════════════════════════════════════╗
║ 第2層: 蒸留・昇格判定エンジン                 ║
║   3 経路並走 (頻度 / 成果 / 自己評価)         ║
╚═════════════════╤════════════════════════════╝
                  │ 閾値超で自動昇格
                  ▼
╔══════════════════════════════════════════════╗
║ 第3層: 共有メモリ (生きた組織知)              ║
║   Letta-style Shared Blocks                  ║
╚═════════════════╤════════════════════════════╝
                  │ PR レビュー
                  ▼
╔══════════════════════════════════════════════╗
║ 第4層: 組織標準 (凍結された Best Practices)   ║
║   Markdown + git                             ║
╚══════════════════════════════════════════════╝
```

## 使い方 — 3 分で動く

```bash
pip install "agentloom[ui]"

# API キー設定 (どれか一つでOK)
export ANTHROPIC_API_KEY=sk-ant-...   # または OPENAI / GEMINI / DASHSCOPE

# 初期化
agentloom init

# 業務フロー実行
agentloom run sales --customer-name "Acme" --product "BizFlow"

# 単一スキル実行 (6 業務領域)
agentloom skill investment "ソニーグループ株の中期投資判断"
agentloom skill legal "業務委託契約書のリスクをレビュー"

# UI 起動
agentloom ui --port 8501
```

## 同梱リソース — 即戦力で使える組み合わせ

### 3 つの業務フロー

| Flow | 概要 |
|---|---|
| **Sales-Agent-Flow** | 顧客 IR・議事録から仮説立案 → FAQ → 提案書アウトラインを生成 |
| **Logic-Checker-Flow** | 構造抽出 / 矛盾検知 / 読者視点 の 3 エージェントで論理整合性をレビュー |
| **RAG-Optimization-Flow** | クエリ拡張 → 検索 → 妥当性評価 → ハルシネーション検証 のループ |

### 6 つのビジネス・ドメイン・スキル

**投資 / 営業 / 設計 / 購買 / 特許 / 法務** — 各ドメインの専門プロンプト + ガードレール込みで、単独でも Flow 内でも使えます。

### 主要 LLM すべてサポート

LiteLLM 経由で **Claude / ChatGPT / Gemini / Qwen-API / Qwen-local (Ollama)** を 1 行で切り替え。

```python
LLM("claude")        # Anthropic Claude
LLM("qwen-local")    # ローカル Qwen (Ollama 経由)
LLM("openai/gpt-4o") # 任意の LiteLLM 形式
```

### 5 つの LTM バックエンド

**json (default) / mem0 / langmem / letta / zep** から選択可能。プラガブル設計で、組織の既存スタックに合わせて切替できます。

## ビジネスへの繋げ方 — オープンコア・モデル

OSS で広く普及させる **コア** と、企業導入時に必要になる **拡張機能** を分離する戦略です。

| 層 | ライセンス | 提供形態 |
|---|---|---|
| コアフレームワーク | Apache 2.0 | OSS |
| GUI 管理画面 / 監査ログ / SSO | 有償 | エンタープライズ版 (将来) |
| 業界別の高精度プロンプト・データ | 有償 | コンサル / Vertical SaaS |

このアプローチにより、技術力（OSS による信頼）とビジネス（差別化機能の収益化）を両輪で回せます。

## 設計の参考にした文献・プロジェクト

理論面：
- [Mem0 論文 (arXiv:2504.19413)](https://arxiv.org/abs/2504.19413)
- [LinkedIn Cognitive Memory Agent](https://linkedin.com/blog/engineering/ai)
- [Letta Sleep-time Agents](https://docs.letta.com/guides/agents/architectures/sleeptime)

実装面：
- [Mem0](https://github.com/mem0ai/mem0) — 個人メモリ層に採用
- [Letta](https://github.com/letta-ai/letta) — Shared Blocks の思想
- [LiteLLM](https://github.com/BerriAI/litellm) — マルチプロバイダ抽象化

## おわりに — Reasoning Engineer の時代へ

2026年現在、AI 市場では **「誰でも作れるもの」には価値がつかない** 状況になっています。

これからの差別化要因は、技術そのものよりも **「Reasoning（推論）の質を評価・設計する」スキル** — つまり Reasoning Engineer の領域です。AgentLoom はこの領域での実践を OSS としてオープンに育てていきたいと思っています。

「個人の天才性 × 組織の継続性」を AI で結びつける — それが AgentLoom のミッションです。

⭐ Star / 🍴 Fork / Issue / PR をお待ちしています。
**[github.com/your-org/agentloom](https://github.com/your-org/agentloom)**
