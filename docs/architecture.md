# AgentLoom アーキテクチャ

## 全体像 — 6 つの層

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      Application / UI (Streamlit / CLI / SDK)            │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │      Orchestrator        │  (agentloom.core.AgentLoom)
                    │   memory + flow + skill  │
                    └─┬──────────┬──────────┬──┘
                      │          │          │
                ┌─────▼───┐ ┌────▼────┐ ┌──▼───────┐
                │ Flows   │ │ Skills  │ │ Memory   │
                │ (Multi- │ │ (Domain │ │ (5-layer │
                │ Agent)  │ │ Bundles)│ │ Stack)   │
                └────┬────┘ └────┬────┘ └────┬─────┘
                     │           │           │
                ┌────▼───────────▼───────────▼────┐
                │            LLM Layer            │  (litellm — multi-provider)
                │  Claude / ChatGPT / Gemini /    │
                │  Qwen-API / Qwen-local (Ollama) │
                └─────────────────────────────────┘
```

## Memory: 5層スタック

### 第1層: 個人メモリ (PersonalMemory)
- 自動抽出 (Mem0 / LangMem) で会話の副産物として暗黙知を蓄積
- バックエンド: `json` (default) / `mem0` / `langmem` / `letta` / `zep`
- Namespace: `user_id`

### 第2層: 蒸留・昇格判定エンジン (SleepTimeConsolidator + PromotionEngine)
3つの判定軸を並走:
1. **頻度** — 複数ユーザ・セッションで繰返し現れるか
2. **成果** — 受注/失敗等の outcome データとの相関
3. **自己評価** — LLM が「組織知候補度」をスコアリング (0..1)

### 第3層: 共有メモリ (SharedMemory)
- Letta-style **shared blocks**
- 全エージェント read/write、`read_only` でポリシー保護

### 第4層: 凍結層 (MarkdownStore)
- Markdown + git + PR レビュー
- GitHub Copilot Custom Instructions / Cursor Rules 互換フォーマット

### 第5層 (任意): Graph 層
- 関係性が業務価値の中核な領域 (決定履歴 / 顧客360 / 障害因果) のみ
- Zep / Graphiti を採用、それ以外は Vector + Entity Linking で十分

### 並走第6層: Skills レジストリ
- 個人 → 組織 へ Skills 自体も昇格
- Claude Skills / MCP / Cursor Skills 互換

## Flow 実行モデル

```python
flow = SalesAgentFlow()
result = flow.run({"customer_name": "...", "product": "..."})
# result.final_output     ← 最終出力
# result.step_outputs     ← 各エージェントの中間出力
# result.total_usage      ← トークン消費合計
```

各 `FlowStep` は前段の出力を `${step_name}` で参照可能。

## LLM プロバイダ抽象化

LiteLLM をラップした薄い `LLM` クラス。文字列エイリアスで切り替え:

```python
LLM("claude")        # → anthropic/claude-opus-4-7
LLM("chatgpt")       # → openai/gpt-4o
LLM("gemini")        # → gemini/gemini-2.0-pro
LLM("qwen")          # → dashscope/qwen-max
LLM("qwen-local")    # → ollama/qwen2.5:14b
LLM("openai/gpt-4o") # 任意の LiteLLM 形式
```

## Phase 別ロードマップ

| Phase | 内容 | 状態 |
|-------|------|------|
| 1 | 個人メモリ + 3 特化フロー + 6 業務スキル | 🚧 Alpha |
| 2 | Sleep-time Consolidator + 統計昇格 | 📋 Planned |
| 3 | Shared Blocks + Markdown 凍結層 | 📋 Planned |
| 4 | Skills レジストリの個人→組織昇格 | 📋 Planned |
| 5 | エンタープライズ拡張 (GUI / 監査 / SSO) | 💼 Commercial |

## 設計決定の根拠

| 決定 | 理由 |
|------|------|
| Mem0 OSS 推奨 | 自動抽出が成熟、entity linking 採用 (2026-04 graph 廃止) |
| Graph 層を任意に降格 | 全領域 Graph は ROI が悪い (LinkedIn CMA / Mem0 自身が示唆) |
| 3経路並走の昇格 | 単一経路依存を避ける (頻度+成果+自己評価) |
| Markdown + git を凍結層に | PR レビュー・blame・履歴管理を既存ワークフローで利用 |
| LiteLLM 採用 | 100+ プロバイダの統一抽象化を再発明しない |
