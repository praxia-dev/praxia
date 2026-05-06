# 設計思想

## 1. 「努力ゼロ」で個人の暗黙知を捕捉する

GitHub Copilot Custom Instructions のような **明示記述** ではなく、
対話の副産物として **自動抽出** する。

| アプローチ | 評価 | 採用 |
|----------|------|------|
| 明示記述 (`CLAUDE.md` / Custom Instructions) | 整理された知識のみ。日常運用での蓄積は薄い | × |
| 自動抽出 (Mem0 / LangMem) | 努力ゼロ。日常対話から暗黙知が積み上がる | ✅ |

## 2. 「有効なものだけ」を「自動的に」組織知に昇格させる

判定の自動化が核心。Praxia は 3 つの判定軸を **並走** させる。
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

- LiteLLM 経由で **任意の LLM プロバイダ** を使える — 27 のフレンドリエイリアス (Claude / ChatGPT / Gemini / Gemma / Qwen / DeepSeek / Mistral · Codestral / xAI Grok / Cohere Command R+ / Perplexity Sonar / Llama 3.3 (Groq・Ollama) / Phi) + LiteLLM 経由 100+。`LLM("provider/model")` で直渡しも可
- LTM バックエンドはプラガブル (Mem0 / LangMem / Letta / Zep / HindSight / JSON)
- Markdown + git はベンダーフリーな永続化先
- Apache 2.0 ライセンス (将来的にオープンコア化予定)

## 6. 「動く」だけでなく「効果」を保証する

評価 (Eval) を標準同梱:

- `praxia.eval.hallucination` — LLM-as-judge による文単位検証
- `praxia.eval.metrics` — Recall@k / Precision

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

## 8. 自律エージェントは「業務スキルの 1 段上」に置く

**LLM 駆動のツール使用ループ** (`praxia.agent.AutonomousAgent`) を、業務フロー / スキルとは **別レイヤ** で同梱する:

- フローは「人間が決めたシーケンス」 — `${var}` で繋がれた `FlowStep` をそのまま実行
- 自律エージェントは「LLM が決めるシーケンス」 — メモリ検索 / スキル実行 / コネクタ pull の順序を判断

両者を共存させる理由は、業務によって最適解が異なるため。コンプラ的に審査済みのプロセスは決定論的フローで、探索的タスクは自律エージェントで、と使い分ける。

ガバナンスの観点では、自律エージェントはより多くの不確実性を抱えるため:
- 全ツール呼出を監査ログ化 (`auth.audit`)
- コネクタアクセスを ACL ゲート (`auth.policies`)
- read_only モードで書込ツールを no-op 化
- `enable_tools=` でツール露出を絞れる

この 4 つで「制御不能」リスクを構造的に抑える。
