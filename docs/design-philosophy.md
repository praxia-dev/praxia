# 設計思想

## 1. 「努力ゼロ」で個人の暗黙知を捕捉する

GitHub Copilot Custom Instructions のような **明示記述** ではなく、
対話の副産物として **自動抽出** する。

| アプローチ | 評価 | 採用 |
|----------|------|------|
| 明示記述 (`CLAUDE.md` / Custom Instructions) | 整理された知識のみ。日常運用での蓄積は薄い | × |
| 自動抽出 (Mem0 / LangMem) | 努力ゼロ。日常対話から暗黙知が積み上がる | ✅ |

## 2. 「有効なものだけ」を「自動的に」組織知に昇格させる

判定の自動化が核心。AgentLoom は 3 つの判定軸を **並走** させる。
単一経路に依存しない。

| 経路 | 駆動 | 例 |
|------|------|-----|
| 自動 | Sleep-time agent + LLM 自己評価 | 「3 ユーザが同じ嗜好」→ 共有ブロックへ |
| 統計 | 成果データとの相関分析 | 「このプロンプトでタスク完了率 70%」→ 組織標準へ |
| 手動 | PR / Q&A 投票 / キュレータ | 「この決定の経緯は重要」→ Markdown 化 |

## 3. 「凍結」と「生きた知識」を分離する

| 層 | 性質 | 例 |
|---|------|-----|
| Shared Blocks (Layer 3) | 即時更新、流動的 | 直近の有効パターン |
| Markdown + git (Layer 4) | PR レビュー必須、安定的 | 確定したベスプラ |

両方を **区別** することで、組織知の「鮮度」と「信頼性」を両立する。

## 4. Graph は限定領域のみ

Mem0 OSS が graph_store を廃止 (2026-04) したシグナルを真摯に受け止める。

採用判断のチェックリスト:
- [ ] 関係性の **2ホップ以上** が日常的に必要か?
- [ ] 時系列での因果連鎖の追跡が必要か?
- [ ] エンティティの canonical 化に十分なリソースを割けるか?
- [ ] 検索レイテンシ p95 で 2〜3 秒許容できるか?

3 つ以上 Yes なら Zep/Graphiti、それ未満なら Markdown 階層と vector 検索で十分。

## 5. ベンダーロックインを避ける

- LiteLLM 経由で **任意の LLM プロバイダ** を使える (Claude / ChatGPT / Gemini / Qwen / OSS モデル)
- LTM バックエンドはプラガブル (Mem0 / LangMem / Letta / Zep / JSON)
- Markdown + git はベンダーフリーな永続化先
- Apache 2.0 ライセンス (将来的にオープンコア化予定)

## 6. 「動く」だけでなく「効果」を保証する

評価 (Eval) を標準同梱:

- `agentloom.eval.hallucination` — LLM-as-judge による文単位検証
- `agentloom.eval.metrics` — Recall@k / Precision

評価エビデンスをセットで OSS 公開することで、
「導入を決定づけるエビデンス」を提供する。

## 7. 業務フロー特化を中核に置く

汎用 (CrewAI / AutoGen / LangGraph) ではなく、
**特定の勝ちパターン** に絞り込んで OSS 化:

- Sales-Agent-Flow (営業準備)
- Logic-Checker-Flow (執筆・論理整合)
- RAG-Optimization-Flow (RAG 自己修復)

各フローは「インストールして 5 分で動く」を目標。
業界別レシピは `docs/recipes/` にコミュニティから受け入れる。
