---
title: "Praxia × 投資業務 — VC ジュニアが 1 週間に 30 件の DD を回す"
emoji: "💰"
type: "tech"
topics: ["AI", "LLM", "投資", "VC", "Python"]
published: false
---

> **このシリーズについて**: [Praxia](https://github.com/your-org/praxia) は業務特化型マルチエージェント・オーケストレーター + 個人→組織メモリ自動循環機構 を持つ OSS です。本記事は投資業務での具体的な活用例にフォーカスします。
> 全体紹介は [こちら](#)。

## 前提となる現場の課題

VC のジュニア・アソシエイトの業務:
- 毎週 5〜10 件のピッチデッキを読む
- 投資委員会向けに 1 ページ要約を作る
- 競合分析、財務試算、リスク洗い出しを行う

**ボトルネック**: 1 件あたり 4〜6 時間。週末まで続くこともしばしば。これでは経営者と密に対話する時間が取れない。

## ユースケース 3 つ

### UC-1: シード投資判断の高速化

**業務シーン**: VC ジュニア・アソシエイトが、毎週 5〜10 件のピッチデッキを読んで投資委員会向けの 1 ページ要約を作成する。

```bash
praxia skill run investment "
シード投資判断:
- 企業: SmartLog Inc (B2B SaaS / 製造業向け IoT 異常検知)
- ステージ: シード ($1M ラウンド、Pre-money $5M)
- ARR: $80k (12 ヶ月成長率 +320%)
- バーンマルチプル: 1.5
- 顧客: 国内製造業 5 社 (うち上場 2 社)
- 競合: PredictNow, FactoryOps, MachineMon

以下を出力:
1. Profile / Quant / Qual / Risk / Decision の 5 セクション
2. Bull / Bear ケース両論
3. 投資判断と想定 IRR
"
```

**出力内容** (抜粋):
- **Profile**: B2B SaaS / 製造業 / シード / 5社実績
- **Quant**: ARR $80k, 成長率 +320%, バーンマルチプル 1.5 (健全)
- **Qual**: 競合に対する優位性、経営陣の業界経験
- **Risk**: 業界 (製造業 IT 投資の景気感応性), 流動性 (Series A 調達想定)
- **Decision**: ✅ 投資検討推奨。ターム: $1M @ $5M Pre-money で 16.7% 取得

| 観点 | Before (従来) | After (Praxia) | 効果 |
|------|--------------|---------------|------|
| 1 件あたり所要時間 | 4〜6 時間 | **45〜60 分** | **約 80% 削減** |
| 競合調査の網羅性 | 主要 3〜5 社 | 主要 + 周辺領域 10〜15 社 | **網羅性 3 倍** |
| Bull/Bear 両論併記 | 担当者によって偏る | 必ず両論 + 反証可能性を提示 | **判断品質の標準化** |
| 案件処理本数 | 週 5〜10 件 | **週 20〜30 件** | **3 倍のディール検討** |

### UC-2: 上場株式の四半期リバランス

**業務シーン**: 個人投資家・ファミリーオフィスの IFA が、保有銘柄 30 銘柄について四半期ごとにリバランス判断資料を作る。

```python
from praxia.skills import InvestmentSkill

skill = InvestmentSkill()
holdings = [
    {"ticker": "7203.T", "name": "Toyota", "weight": 8.5},
    {"ticker": "9984.T", "name": "SoftBank", "weight": 6.2},
    # ... 30 銘柄
]

for h in holdings:
    analysis = skill.run(f"""
    {h['name']} ({h['ticker']}) のQ3 リバランス判断:
    - 現保有比率: {h['weight']}%
    - 直近四半期決算 + ガイダンス
    - 為替・金利・原油の感応度
    - 同業他社比較 (PER/PBR/ROE)
    最終: 増 / 維持 / 減 + 推奨ウェイト
    """)
    print(analysis)
```

| 観点 | Before | After |
|------|--------|-------|
| 1 銘柄あたり分析時間 | 30〜60 分 | **5〜10 分** |
| 30 銘柄の総時間 | 15〜30 時間 (3〜4 営業日) | **2.5〜5 時間 (半日)** |
| 為替・マクロ要因の織り込み | 主要 1〜2 要因 | 5〜7 要因を一貫して評価 |
| 顧客への説明資料の質 | 担当者依存 | 全顧客同じ品質 + 個別最適化 |

### UC-3: M&A デューデリの財務クイックスクリーニング

**業務シーン**: 事業会社の経営企画部が、M&A 候補 20 社のロングリストから 5 社にショート化する初期スクリーニング。

```bash
praxia skill run investment "
M&A 候補 20 社のスクリーニング (添付ファイル: 20社の財務 3 期分)

各社について以下を判定:
1. 粉飾の兆候 (異常検知ルール 30 項目)
2. シナジー期待度 (当社事業との接続点)
3. 簡易バリュエーション (DCF + 類似企業比較)
4. ショートリスト残し (Yes/No + 理由)
"
```

| 観点 | Before | After |
|------|--------|-------|
| 20 社の初期分析 | 2 週間 (財務 3 期分 × 20 社) | **2〜3 営業日** |
| 見逃しリスク (粉飾の兆候等) | 担当者の経験次第 | 異常検知ルール 30 項目を一律適用 |
| 投資委員会への説明資料 | 翌週月曜まで | **当日中** |

## 個人 → 組織知の循環例

ベテラン GP が 5 年かけて磨いた **「SaaS 系の Burn Multiple 評価ロジック」** が個人メモリに蓄積されているとします。

```python
from praxia import Praxia

p = Praxia(user_id="senior_gp_alice")
result = p.run(InvestmentSkill, inputs={"query": "..."})
# → 個人メモリに自動蓄積

# 受注に紐付け (Phase 2 outcome tracking)
p.personal_memory.record_outcome(
    episode_id=result.metadata["episode_id"],
    success=True,  # 投資した結果リターンが出た
    score=2.5,      # 2.5x exit
    notes="2-year exit at 2.5x — Burn multiple framework worked"
)
```

夜間バッチで蒸留:

```bash
praxia consolidate
# → 3 名以上のアソシエイトが同じ評価軸を使うようになると検出
# → 自己評価スコア 0.85, 成果相関 0.9
# → 自動昇格 (auto_threshold=0.75 を超過)
# → 組織共有ブロックへ
```

その後、新人アソシエイトがアクセス:

```python
new_p = Praxia(user_id="junior_bob")
result = new_p.run(InvestmentSkill, inputs={"query": "..."})
# → 組織共有ブロックが自動的にコンテキストに含まれる
# → 新人がベテランと同じ評価軸で動ける
```

**結果**: 新人独り立ち期間が 6〜12 ヶ月 → **2〜3 ヶ月** に短縮。

## ガードレールに注意

InvestmentSkill には以下のガードレールが組み込まれています:

- **「最終判断は投資家自身」** を必ず添える (投資助言業ライセンスを持たないため)
- 不確実性は隠さず明示 (信頼区間・前提条件)
- 利益相反 (ポジショントーク) の可能性も提示
- 日本国内投資の場合は税制 (NISA / 譲渡益課税 20.315%) も考慮

```python
class InvestmentSkill(Skill):
    system_prompt = """
    ...
    【ガードレール】
    - 投資助言業のライセンスを持たないため、「最終判断は投資家自身」を必ず添える
    - 不確実性は隠さず明示する (信頼区間・前提条件)
    - 利益相反 (ポジショントーク) の可能性も提示する
    - 日本国内投資の場合は税制 (NISA / 譲渡益課税 20.315%) も考慮
    ...
    """
```

これにより、無資格者による「投資助言の提供」と誤解されるリスクを下げています。

## 自社カスタマイズ — 30 行で投資特化フロー

例: ESG スコアリングを組み込んだ投資判断フローを作る。

```python
from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM

class ESGInvestmentFlow(Flow):
    name = "esg_investment_flow"
    description = "ESG 観点を統合した投資判断フロー"

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()
        self.steps = [
            FlowStep(
                name="financial",
                agent=Agent("financial", llm=llm, system_prompt="財務 3 表分析..."),
                inputs={"company": "${company}"},
            ),
            FlowStep(
                name="esg_score",
                agent=Agent("esg", llm=llm, system_prompt="ESG スコアリング..."),
                inputs={"company": "${company}"},
            ),
            FlowStep(
                name="integrated",
                agent=Agent("integrate", llm=llm, system_prompt="財務 + ESG 統合判断..."),
                inputs={"financial": "${financial}", "esg": "${esg_score}"},
            ),
        ]

# 利用
from praxia import Praxia
p = Praxia(user_id="esg_analyst")
result = p.run(ESGInvestmentFlow, inputs={"company": "Toyota Motor"})
```

## まとめ

Praxia の投資業務での価値:

1. **時間圧縮**: 1 件 4〜6h → 45〜60 分 (80% 削減)
2. **網羅性**: 競合 3〜5 社 → 10〜15 社 (3 倍)
3. **判断品質の標準化**: Bull/Bear 両論 + ガードレール
4. **組織知の自動形成**: ベテランの目利きが新人に自動継承
5. **完全な拡張性**: 30 行でカスタムフロー、20 行でカスタムスキル

⭐ [GitHub](https://github.com/your-org/praxia) | 📦 `pip install praxia`

---

> **シリーズ次回**: 営業業務での Praxia 活用 — 提案合意率 +15〜20pt の事前準備自動化
