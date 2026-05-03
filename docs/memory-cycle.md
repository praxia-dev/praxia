# メモリ循環設計の詳細

## 課題: ベテランの暗黙知が組織に届かない

ベテラン営業 / エンジニア / 法務担当者が磨いた「効くプロンプト」「効く分析手順」は
ほとんどの場合、本人の引き出しに留まる。組織にとって以下の問題が発生:

1. 部門で「効くアプローチ」を発見しても自然な伝播が起きない
2. 退職時に知見が漏出する
3. 同じ間違いを別の人が繰り返す
4. 業界別のテンプレートが整備されても継続的な進化メカニズムがない

## Praxia の解: 5 層 + 3 経路の昇格パイプライン

### 層

```
個人メモリ (Layer 1)         ← ユーザは普通に使うだけ。明示的な save 不要
      │
      │  Sleep-time Consolidation (Layer 2)
      │  3 経路並走 (頻度 / 成果 / 自己評価)
      ▼
共有メモリ (Layer 3)         ← 全エージェントが即時参照
      │
      │  PR レビュー (重要案件のキュレーション)
      ▼
Markdown 凍結層 (Layer 4)   ← git 履歴管理されたベスプラ
      │
      │  (任意)
      ▼
Graph 層 (Layer 5)           ← 関係性が業務価値の中核な領域のみ
```

### 3 経路の昇格判定

#### ① 頻度ベース
- 複数ユーザ・複数セッションで繰り返し現れる事項
- 実装: `SleepTimeConsolidator._cluster_candidates`
- 例: 「製造業向け課題抽出で N 人が共通して使うプロンプト」

#### ② 成果連動ベース
- 受注/失注、テスト合格/失敗、PR マージ/リジェクト等の outcome データとの相関
- 実装: `PromotionEngine.evaluate(outcome_correlation=...)`
- 例: 「このプロンプトを使った商談は受注率 +20pt」

#### ③ 自己評価ベース
- LLM が「組織知候補度」を 0..1 でスコアリング
- 実装: `PromotionEngine._self_eval`
- 評価軸: generalizable / non-PII / actionable

### 重み付けと閾値

```python
PromotionEngine(
    llm=llm,
    weights=(0.4, 0.3, 0.3),    # frequency / outcome / self-eval
    auto_threshold=0.75,         # >= → 自動昇格
    review_threshold=0.5,        # >= → 人手レビューキューに投入
)
```

## なぜ Graph 層を任意にしたか

研究 (Mem0 / LinkedIn CMA / GraphRAG) を統合した結論:

- **Mem0 OSS は 2026年4月に graph_store サポートを完全廃止**
- グラフ化は LLM トークン消費 2倍 / レイテンシ 3倍 / 効果 +2pt 程度
- LinkedIn は GraphRAG より tree 階層集約が効率的と公開実証

→ Vector + Entity Linking を主軸、Graph は **関係性が業務価値の中核** な
領域のみ追加採用 (決定履歴 / 顧客360 / 障害因果)。

## オプトアウト

ユーザが「個人メモリを組織還元の対象にしない」を選択可能。
PII (個人情報) は自動抽出時にフィルタ済み。機密区分のあるデータは自動除外。

## 効果測定

昇格された知識の利用率 / 受注率変化を `praxia.eval` モジュールでトラッキング:

```python
from praxia.skills.registry import SkillRegistry
registry = SkillRegistry()
stats = registry.usage_stats("sales_strategist")
# {"count": 42, "users": 8, "success_rate": 0.71}
```
