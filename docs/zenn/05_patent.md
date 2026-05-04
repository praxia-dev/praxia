---
title: "Praxia × 特許業務 — 弁理士費用 50〜70% 削減、先行技術調査を 1〜2 日 → 2〜4 時間に"
emoji: "📑"
type: "tech"
topics: ["AI", "LLM", "特許", "知財", "Python"]
published: false
---

> **このシリーズについて**: [Praxia](https://github.com/your-org/praxia) は業務特化型マルチエージェント・オーケストレーター + 個人→組織メモリ自動循環機構 を持つ OSS。本記事は特許業務 (先行技術調査・クレーム作成・特許マップ) での具体的な活用例にフォーカスします。
> 全体紹介は [こちら](#)。

![Policies UI (出願前情報のアクセス制御)](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-policies.svg)

## 前提となる現場の課題

メーカーの研究開発部門・知財部門の典型的な業務:
- 月 10〜20 件の発明案件について「特許化すべきか / 営業秘密か」の判断資料作成
- 1 件あたり弁理士 + 研究員 1〜2 営業日
- 弁理士費用: 1 件 30〜50 万円
- 結果: 研究開発予算の **20〜30% が知財費用** に消える中小メーカーも

スタートアップは弁理士費用を抑えたいが、品質も担保したい。このジレンマを Praxia の PatentSkill が解消します。

## ユースケース 3 つ

### UC-1: 新規発明の先行技術調査 + 進歩性評価

PatentSkill には **5 段階フレームワーク** が組み込まれています:

1. **要素抽出**: 発明の構成要素を MECE に分解
2. **検索式設計**: IPC / FI / Fターム + キーワード (シノニム展開)
3. **ヒット文献分析**: 先行技術 vs 本願 を要素毎に対比表で整理
4. **新規性判断**: 構成要素のうち 1 つでも未開示なら新規性あり
5. **進歩性判断**: 当業者が容易想到か → 阻害要因 / 顕著効果を提示

```bash
praxia skill run patent "
発明:
- 名称: 高効率な太陽電池セル構造
- 概要: 三層ペロブスカイト + 銀ナノワイヤ電極 + 反射防止膜
- 技術分野: 太陽電池、特に薄膜系
- 発明者主張: 変換効率 28% (理論限界に近い)、量産プロセス低コスト

以下を実施:
1. 発明要素を MECE に分解
2. IPC / FI / Fターム を提示
3. シノニム展開込みの検索式案 (J-PlatPat 用)
4. 構成要素別の対比表ひな形
5. 新規性 / 進歩性 の予備判断と論拠

注: 最終判断は弁理士確認必須を明記すること
"
```

**出力例 (抜粋)**:
```markdown
## 1. 発明要素マップ
| 要素 | 内容 |
|------|------|
| 基体構造 | 三層ペロブスカイト |
| 電極 | 銀ナノワイヤ |
| 反射防止 | (要詳細化) |
| 製造プロセス | 量産可能性が要請 |

## 2. IPC / FI / F-term
- IPC: H01L 31/0224 (光電変換素子の電極)
- FI: 5F151BA22 (ペロブスカイト系)
- F-term: 4M118HA32 (反射防止膜)

## 3. 検索式案
"ペロブスカイト" AND ("銀ナノワイヤ" OR "Ag nanowire") AND ("反射防止" OR "AR coating")
※ シノニム展開: pe rovskite, lead halide, multi-junction, antireflection

## 4. 対比表ひな形
| 要素 | 本願 | 引例 1 (JP2024XXX) | 引例 2 (US2024YYY) | 引例 3 |
|------|------|---|---|---|
| 三層ペロブスカイト | ✓ | ✓ | △(2層) | ✗ |
| 銀ナノワイヤ電極 | ✓ | ✗ | ✓ | △(銅NW) |
| 反射防止膜 | ✓ | ✗ | ✗ | ✓ |

## 5. 予備判断
- 新規性: 全構成要素を同時開示する引例なし → ✓ 新規性アリ (予備)
- 進歩性: 銀NW + 三層ペロブスカイト の組合せに当業者の容易想到性が論点
  - 阻害要因: 銀NW のペロブスカイトへの腐食性 (引例 1 で指摘あり)
  - 顕著効果: 28% 変換効率 (理論値 24% を超過、実証必要)
  → 進歩性は実験データで補強する必要あり

⚠️ 最終出願は弁理士確認必須。本判定は予備調査結果です。
```

### Before / After

| 観点 | Before | After |
|------|--------|-------|
| 1 件あたり調査時間 | 1〜2 営業日 (弁理士 + 研究員) | **2〜4 時間** |
| 検索式設計 | 弁理士の経験次第 | **シノニム展開 + IPC/FI/Fターム を体系的に網羅** |
| 進歩性判断の根拠 | 「私の経験では…」 | **構成要素別の対比表 + 阻害要因 / 顕著効果** |
| 弁理士費用 | 1 件 30〜50 万円 | **1 件 10〜15 万円 (一次調査を内製化)** |

### UC-2: 特許クレームの初稿ドラフト

スタートアップで弁理士費用を抑えたいが、品質も担保したい場合:

```python
from praxia.skills import PatentSkill

skill = PatentSkill()
claims = skill.run("""
発明: 三層ペロブスカイト + 銀ナノワイヤ電極の太陽電池セル

以下のクレーム構造を提案:
1. 独立クレーム (請求項 1) — 必須要素のみで広く取る
2. 従属クレーム (請求項 2-5) — 段階的に限定 (中核 → 防御線)
3. 機能限定 (means-plus-function) を使うべきか/避けるべきかも判断

【クレーム作成原則】
- 独立クレームは subject-verb-object で必須要素のみ
- "comprising" (限定なし) と "consisting of" (閉じた定義) を使い分け
- 機能限定は範囲が狭まるため慎重に

最後に、日本・米国・欧州での出願戦略 (推奨国・タイミング・補正余地) も提示。
""")
```

| 観点 | Before | After |
|------|--------|-------|
| 初稿ドラフト所要時間 | 弁理士に丸投げ → 2 週間 | **Praxia で初稿 → 弁理士レビュー: 3 営業日** |
| 弁理士費用 | 50〜80 万円 | **15〜25 万円 (レビューのみ)** |
| クレーム記載の戦略性 | 弁理士任せ | **独立クレームの広さ / 従属クレームの段階的限定が事前検討済み** |

### UC-3: 競合特許マップの作成

新製品投入前の特許侵害リスク調査。

```python
from praxia import Praxia
from praxia.skills import PatentSkill

p = Praxia(user_id="ip_team", default_model="claude")

# 50〜100 件の競合特許 (J-PlatPat / Google Patents から取得済) を分析
competitors_patents = [...]

map_data = []
for patent in competitors_patents:
    skill = PatentSkill()
    analysis = skill.run(f"""
    以下の競合特許について、本社の新製品「Aurora Battery」に対する侵害リスクを評価:

    特許番号: {patent['number']}
    出願人: {patent['applicant']}
    技術分野: {patent['ipc']}
    クレーム要旨: {patent['claims_summary']}

    判定:
    1. 侵害リスク (要素単位の対応マトリクス)
    2. 重大度: 🔴 Critical / 🟡 Major / 🟢 Minor
    3. 回避設計案 (回避クレーム案 3 通り)
    """)
    map_data.append(analysis)

# 全分析を集計、ダッシュボード化
```

| 観点 | Before | After |
|------|--------|-------|
| 競合特許 50〜100 件の分析 | 1 ヶ月 (知財部 2 名) | **1 週間** |
| 侵害リスクの定量化 | 重大度 3 段階 (主観) | **要素単位の対応マトリクス** |
| 回避設計の提案 | 別途 1 ヶ月 | **同時生成 (回避クレーム案 3 通り)** |

## ガードレール — 弁理士法遵守

PatentSkill には弁理士法 (士業独占) を侵さないガードレールが組み込まれています:

```python
class PatentSkill(Skill):
    system_prompt = """
    ...
    【ガードレール】
    - 弁理士法上、出願代理は弁理士のみ可能。「最終出願は弁理士確認必須」を明示
    - 進歩性判断は審査官の主観余地が大きい — 確定的な保証はしない
    - 営業秘密 (Trade Secret) と特許の戦略的使い分けを助言
    ...
    """
```

これにより、無資格者の業務独占違反リスクを未然に防ぎます。

## 個人 → 組織知の循環例 — クロスドメイン技術の発見

知財部のベテランが磨いた **「半導体分野の検索式テンプレート」** が個人メモリに蓄積されているとします。

別分野 (例: 太陽電池) の研究員が Praxia 経由でアクセスすると、半導体の検索式が太陽電池研究にも適用できることが分かり、**クロスドメインの先行技術** が見つかることがあります。

```python
# Senior IP person uses for semiconductor patents
p_senior = Praxia(user_id="senior_ip_yamamoto")
# 月 50 件の半導体特許調査 → 検索式テンプレートが個人メモリに蓄積

# Researcher in solar cell domain uses
p_researcher = Praxia(user_id="solar_researcher_kenji")
result = p_researcher.run(PatentSkill, inputs={"query": "ペロブスカイト太陽電池の先行技術"})
# → 半導体ドメインの検索式テンプレートが組織共有プロンプトから自動引用
# → 半導体プロセス由来の先行技術 (薄膜形成法等) が新たに発見される
```

これが Praxia の **「組織として知財の蓄積が発酵する」** 機構です。

## 自社カスタマイズ — 営業秘密 vs 特許 判定スキル

```python
from praxia.skills.skill import Skill, SkillManifest

class TradeSecretVsPatentSkill(Skill):
    manifest = SkillManifest(
        name="trade_secret_vs_patent",
        description="発明を「特許出願」or「営業秘密」のどちらで保護すべきかを判定",
        domain="patent",
        tags=["ip-strategy"],
    )
    system_prompt = """
    あなたは知財戦略コンサルタントです。

    【判定軸】
    1. リバースエンジニアリング困難度: 高 → 営業秘密に有利
    2. 模倣検知容易性: 高 → 特許に有利
    3. ライフサイクル: 短 → 営業秘密に有利
    4. 開示による技術蓄積効果: 大 → 特許に有利
    5. 競合の特許化リスク: 大 → 特許に有利 (防衛出願)

    【出力】
    - 推奨: 特許 / 営業秘密 / ハイブリッド (一部だけ特許化)
    - 各判定軸での評価 (0-10)
    - 総合スコア + 理由
    - 営業秘密管理が必要な場合の推奨措置 (アクセス制御、NDA)
    """
```

## 外部システム連携 — Box / SharePoint の発明提案フォルダから直接取り込み

R&D 部門の発明提案書は Box / SharePoint 上にあるケースが多いはず:

```python
from praxia.connectors import get_connector
from praxia.skills import PatentSkill

box = get_connector("box", access_token=os.environ["BOX_TOKEN"])
proposals = box.pull("/RnD/InventionProposals/2026Q4", limit=20)

skill = PatentSkill()
results = []
for prop in proposals:
    analysis = skill.run(f"""
    発明提案書: {prop.name}

    {prop.content.decode() if isinstance(prop.content, bytes) else prop.content}

    以下を実施: 要素抽出 / 検索式設計 / 新規性予備判断 / 進歩性予備判断
    """)
    results.append({"name": prop.name, "analysis": analysis})

    # Salesforce や kintone の知財管理システムにプッシュ
    sf = get_connector("salesforce", username="...", password="...", security_token="...")
    sf.push("Patent_Application__c", json.dumps({
        "Name": prop.name,
        "Praxia_Pre_Search__c": analysis,
        "Status__c": "Awaiting_Attorney_Review",
    }))
```

## ACL — 出願前の発明情報を厳格に隔離

弁理士法・営業秘密管理規定に従い、出願前の発明情報は知財部以外からアクセス不可に:

```bash
praxia policy add deny connector "box:/RnD/InventionProposals/*" \
    --principals "role:member,role:viewer" \
    --description "出願前の発明情報は知財部 (operator) のみ"

praxia policy add deny memory "memory:patent_*" \
    --principals "role:member,role:viewer" \
    --description "特許関連メモリも同様"
```

これにより、誤って外部 LLM へ送信される事故を未然に防げます。

## 知財部ベテランの検索式テンプレートを配信

```bash
praxia prompt distribute semiconductor_search_template tmpl.md \
    --target-users r_and_d_engineer1,r_and_d_engineer2 \
    --description "半導体分野の特許検索テンプレ"

praxia skill distribute patent_analyst --target-roles operator
```

## まとめ

Praxia の特許業務での価値:

1. **時間圧縮**: 先行技術調査 1〜2 日 → 2〜4 時間
2. **コスト削減**: 弁理士費用 50〜70% 削減
3. **網羅性**: シノニム展開 + IPC/FI/F-term を体系的に
4. **クロスドメイン発見**: 別分野の検索式テンプレートが活用される
5. **戦略性**: クレーム作成原則 + 出願戦略を事前検討
6. **法令遵守**: 弁理士法のガードレール組み込み済み

⭐ [GitHub](https://github.com/your-org/praxia) | 📦 `pip install praxia`

---

> **シリーズ次回**: 法務業務での Praxia 活用 — M&A 外部法律事務所費用を半減
