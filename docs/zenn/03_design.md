---
title: "Praxia × 設計業務 — シニア・アーキトの可処分時間を週 16h → 4h に"
emoji: "🏗"
type: "tech"
topics: ["AI", "LLM", "アーキテクチャ", "設計レビュー", "Python"]
published: false
---

> **このシリーズについて**: [Praxia](https://github.com/your-org/praxia) は業務特化型マルチエージェント・オーケストレーター + 個人→組織メモリ自動循環機構 を持つ OSS。本記事は設計業務 (システム設計・要件定義・アーキテクチャ評価) での具体的な活用例にフォーカスします。
> 全体紹介は [こちら](#)。

![Connectors UI](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-connectors.svg)

## 前提となる現場の課題

SIer のシニア・アーキトの典型的な 1 週間:
- 新人 PM が書いた要件定義書のレビュー: 3〜5 本 / 週
- 各レビューに 2〜4 時間かかる
- 結果: シニア時間の **週 12〜20 時間** がレビューに消費
- それでも非機能要件 (NFR) の抜け漏れが残る

> 「監視・障害対応・運用引き継ぎ」が抜けたまま設計フェーズに入ってしまい、リリース直前に 200 時間の追加工数が発生したことがある。

## ユースケース 3 つ

### UC-1: 要件定義書の早期レビュー

DesignSkill には **DRAGON フレームワーク** が組み込まれています:

- **D**ata flow: データ流れの矛盾・欠落
- **R**equirements traceability: 要件 ↔ 設計の対応
- **A**rchitectural fit: パターン選定の妥当性
- **G**aps: 抜け漏れ (例外系・運用系・移行)
- **O**peration: 監視・障害対応・運用引継ぎ
- **N**FRs: 性能・可用性・セキュリティ

```bash
praxia skill run design "$(cat requirements_v2.md)"
```

**出力例**:
```markdown
## レビューサマリ
🟡 **Request Changes** — 重大な抜け漏れ 3 件、改善推奨 5 件

## 重大な指摘 (Critical)
1. 監視・障害対応の記述が完全に抜けている (NFR)
   - 改善案: SRE プレイブックの章を追加 (P12 参照)
2. 移行戦略の記述がない (G)
   - 改善案: ブルー/グリーン または カナリア展開を選択
3. リクエスト数 1,000 RPS 想定に対し、データ層がボトルネック
   - 改善案: Read レプリカ + キャッシュ層を設計に組み込む

## 改善推奨 (Major)
4. データ流れに 1 箇所未対応のエラーパス (D)
5. PII 取扱いに関する記述がプライバシー要件と不整合 (NFR)
...
```

### Before / After

| 観点 | Before | After |
|------|--------|-------|
| レビュー 1 本あたりの所要時間 | 2〜4 時間 | **20〜40 分** |
| シニアの可処分時間 | 週 12〜20 時間レビューに消費 | **週 3〜4 時間 (本質的な指摘のみ集中)** |
| 抜け漏れ検出 (NFR) | 主要 5〜7 観点 | **DRAGON 全 6 軸で網羅的に検出** |
| PM の独り立ち期間 | 12〜18 ヶ月 | **6〜9 ヶ月** |
| リリース直前の手戻り工数 | 平均 150〜250 時間 / プロジェクト | **20〜50 時間** |

### UC-2: アーキテクチャ選定の意思決定支援

Monolith / Microservices / Modular Monolith のどれを選ぶか議論する場面。

```python
from praxia import Praxia
from praxia.skills import DesignSkill

p = Praxia(user_id="arch_kenta", default_model="claude")
skill = DesignSkill()

decision = skill.run("""
新規プロジェクト「Project Aurora」のアーキテクチャ選定:

要件:
- ローンチ時: 100 リクエスト/秒
- 1 年後想定: 1,000 リクエスト/秒
- チーム規模: 8 名 → 18 名 (1 年後)
- 既存システム: Rails モノリス + RDS
- 法務要件: PII を別 DB に分離
- 予算: 開発費 50M JPY、年間運用費 20M JPY

選択肢:
A. Modular Monolith (現状の Rails 拡張)
B. Strangler Fig (Modular Monolith → 段階的 Microservices)
C. 新規 Microservices (Go / Kubernetes)

各選択肢について Conway / NFR / 運用負荷 / 採用容易性を評価。
過去案件との比較もしてください。
""")
```

Praxia の特徴は **過去案件との比較** の自動引用です。組織メモリに「2025 年の A 社案件で Microservices に踏み込みすぎて運用負荷が破綻した」という事例が蓄積されていれば、それを引用して同じ失敗を回避します。

| 観点 | Before | After |
|------|--------|-------|
| 比較資料作成 | 3〜5 営業日 | **半日** |
| 評価観点の網羅 | 主要 5〜10 観点 | **15〜20 観点 (Conway / NFR / 運用負荷 / 採用容易性)** |
| 過去案件との比較 | 担当者の記憶 | **組織メモリから類似案件を自動抽出** |
| 意思決定の質 | 担当者依存 | **エビデンス・ベース** |

### UC-3: レガシーコードの非機能評価

20 年運用の基幹システムについて、リファクタ判断のための非機能棚卸し。

```python
# モジュール毎にスキャン
import os
from praxia.skills import DesignSkill

skill = DesignSkill()
for root, dirs, files in os.walk("legacy_system/"):
    for file in files:
        if file.endswith((".java", ".cob")):
            with open(os.path.join(root, file)) as f:
                code = f.read()
            assessment = skill.run(f"""
            レガシーコード非機能評価:

            ```{file.split('.')[-1]}
            {code[:5000]}
            ```

            以下を判定:
            1. 性能ボトルネック (推定)
            2. セキュリティ脆弱性 (OWASP Top 10)
            3. 保守性スコア (0-10)
            4. リファクタ推奨度 (Critical / Major / Minor / OK)
            5. ROI 試算 (リファクタ後の運用工数削減効果)
            """)
            # 結果を蓄積
```

| 観点 | Before | After |
|------|--------|-------|
| 評価所要時間 | 3〜6 ヶ月 (専任 2 名) | **3〜4 週間** |
| カバー範囲 | サンプリング 30% | **全モジュール網羅** |
| ROI 試算の精度 | ±50% | **±15%** |

## 個人 → 組織知の循環例 — 「失敗から学ぶ組織」

```python
# 痛い経験を個人メモリに記録
p = Praxia(user_id="arch_kenta")
result = p.run(DesignSkill, inputs={"query": "Microservices 分割案"})

# 1 年後、運用負荷が破綻したことを成果として記録
p.personal_memory.record_outcome(
    episode_id=result.metadata["episode_id"],
    success=False,
    score=-1.5,  # 想定の 1.5 倍の運用工数
    notes="Microservices 過分割。サービス間データ連携で運用負荷破綻。"
)
```

別チームが類似決定を検討する 1 年後:

```python
new_p = Praxia(user_id="arch_taro")
result = new_p.run(DesignSkill, inputs={"query": "新規プロジェクトのアーキテクチャ"})

# 組織メモリから類似失敗事例が自動的にコンテキストに含まれる
# → 「過去案件で Microservices に分割しすぎて運用破綻した事例あり」と警告
# → 同じ失敗を回避
```

これが Praxia の核心: **「失敗から学ぶ組織」が初めて実装できる**。

| Before | After |
|--------|-------|
| 失敗事例は担当者の記憶のみ | 組織メモリに永続化 |
| 退職時に消失 | 退職後も継承される |
| 同じ失敗を繰り返す | パターン検出して回避 |

## 自社カスタマイズ — フロントエンド設計レビューフロー

```python
from praxia.core.flow import Flow, FlowStep
from praxia.core.agent import Agent
from praxia.core.llm import LLM

class FrontendReviewFlow(Flow):
    name = "frontend_review_flow"
    description = "フロントエンド設計の専門レビュー (アクセシビリティ + パフォーマンス + UX)"

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()
        self.steps = [
            FlowStep(
                name="accessibility",
                agent=Agent("a11y", llm=llm, system_prompt="""
                    WCAG 2.2 AA 準拠の観点でレビュー。色コントラスト・キーボード
                    操作・スクリーンリーダー対応・フォーカス管理 を必ずチェック。
                """),
                inputs={"design": "${design}"},
            ),
            FlowStep(
                name="performance",
                agent=Agent("perf", llm=llm, system_prompt="""
                    Core Web Vitals (LCP/FID/CLS) 観点でレビュー。バンドルサイズ・
                    レンダリング戦略 (SSR/CSR/SSG) の妥当性を評価。
                """),
                inputs={"design": "${design}"},
            ),
            FlowStep(
                name="ux",
                agent=Agent("ux", llm=llm, system_prompt="""
                    UX 観点でレビュー。ユーザーフロー・状態管理・エラーハンドリング・
                    オフライン対応 を評価。
                """),
                inputs={"design": "${design}"},
            ),
            FlowStep(
                name="summary",
                agent=Agent("summary", llm=llm, system_prompt="""
                    3 つのレビュー結果を統合し、優先度別の改善リストを作成。
                """),
                inputs={
                    "a11y": "${accessibility}",
                    "perf": "${performance}",
                    "ux": "${ux}",
                },
            ),
        ]
```

```bash
# 利用
python -c "
from praxia import Praxia
from my_flows import FrontendReviewFlow

p = Praxia(user_id='alice')
result = p.run(FrontendReviewFlow, inputs={'design': open('design.md').read()})
print(result.final_output)
"
```

## 外部システム連携 — Confluence の代わりに SharePoint / GDrive 直接

設計レビューで参照する仕様書は SharePoint / GDrive にあるケースが多いはず:

```python
from praxia.connectors import get_connector
from praxia.skills import DesignSkill

gd = get_connector("gdrive", service_account_file="sa.json")
specs = gd.pull("0AbCdEfGhIjKl", limit=50)  # 設計仕様書のフォルダ

skill = DesignSkill()
for spec in specs:
    if spec.mime_type == "text/plain" or spec.name.endswith(".md"):
        review = skill.run(f"レビュー対象: {spec.name}\n\n{spec.content.decode()}")
        # 同じ場所にレビュー結果を Push
        gd.push("0AbCdEfGhIjKl", {"name": f"REVIEW_{spec.name}", "body": review})
```

## ACL — 機密設計仕様の隔離

知財的に機密な設計仕様書 (新規製品の特許出願前のもの等) は member ロールから完全隔離:

```bash
praxia policy add deny connector "gdrive:0AbCdEfPATENT*" \
    --principals "role:member,role:viewer" \
    --description "特許出願前の設計仕様は知財部 (operator+) のみ"
```

## アーキテクチャ判断パターンの組織配信

過去 10 年で痛い思いをしたパターンを「やってはいけない」プロンプトとして配信:

```bash
praxia prompt distribute architecture_anti_patterns anti.md \
    --target-roles operator,member \
    --description "過去案件の失敗事例を踏まえた回避すべきパターン"
```

新人アーキトの最初の design review で、自動的にこの観点が組み込まれます。

## まとめ

Praxia の設計業務での価値:

1. **時間圧縮**: シニアレビュー 2〜4h → 20〜40 分
2. **網羅性**: DRAGON 全 6 軸で抜け漏れ検出
3. **新人独り立ち**: 12〜18 ヶ月 → 6〜9 ヶ月
4. **組織記憶**: 失敗事例の永続化、同じ失敗を回避
5. **拡張性**: フロントエンド / モバイル / セキュリティ等の専門レビューフローを 30 行で追加可能

⭐ [GitHub](https://github.com/your-org/praxia) | 📦 `pip install praxia`

---

> **シリーズ次回**: 購買業務での Praxia 活用 — TCO で初期見積より +30% の真コスト発見
