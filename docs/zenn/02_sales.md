---
title: "Praxia × 営業業務 — 商談準備 6h → 1h、提案合意率 +15〜20pt"
emoji: "📈"
type: "tech"
topics: ["AI", "LLM", "営業", "B2B", "Python"]
published: false
---

> **このシリーズについて**: [Praxia](https://github.com/your-org/praxia) は業務特化型マルチエージェント・オーケストレーター + 個人→組織メモリ自動循環機構 を持つ OSS。本記事は営業業務での具体的な活用例にフォーカスします。
> 全体紹介は [こちら](#)。

![Run Flow UI](https://raw.githubusercontent.com/your-org/praxia/main/docs/images/ui-run-flow.svg)

## 前提となる現場の課題

B2B 営業の現場でよく聞く失敗:

> 「IR をざっと読んだだけで臨んだら、相手 CFO から『3 ヶ月前のあの設備投資、御社の製品でカバーできますか?』と聞かれて固まった」

商談前の準備が浅いと、その場で勝負が決まる質問への対応で詰まります。一方で、丁寧に IR / プレス / 業界レポートを読み込むと 1 商談あたり 4〜8 時間かかり、週 3 件で限界。

## ユースケース 3 つ

### UC-1: 新規アカウントの事前リサーチ + 商談ストーリーボード

**業務シーン**: B2B SaaS の営業が、新規大手顧客との初回商談に向けて準備する。

```bash
# 一発で完結
praxia run sales \
  --customer-name "株式会社 Acme Manufacturing" \
  --product "Praxia Sales" \
  --additional-context "製造業向け SaaS。直近の中期経営計画で DX 投資を 300 億円計上"
```

このコマンドが内部で **3 エージェント** を走らせます:

1. **Research Agent**: IR + プレス + 業界レポートから経営トピック抽出
2. **Hypothesis Agent**: 経営課題の上位 3 仮説を立案
3. **Proposal Agent**: 商談 FAQ 5 本 + 提案書アウトラインを生成

**出力例 (抜粋)**:
```markdown
## エグゼクティブサマリ
- 直近 6 ヶ月で発表した DX 投資 300 億円のうち、120 億円が
  電子部品関連 (推測 [仮説])
- 工場 IoT / 異常検知への投資意欲が公開資料から読み取れる
- 現状: 2 工場で PoC 中、本格展開は 2026 Q3 想定

## 仮説課題 TOP3
1. 工場間データ連携の遅延 → Praxia Sales でルートマップ
2. ベテラン技能伝承 → 個人 → 組織メモリ循環でカバー
3. 提案チームのスキルばらつき → スキルレジストリで標準化

## 商談 FAQ
| 想定質問 | 推奨回答 | 公開ソース |
|---------|---------|----------|
| 「3 ヶ月前のあの設備投資カバーできる?」 | はい — Praxia の Layer 1 が現場ノウハウを取り込みます | IR 報告書 P12 |
| 「どの業種で実績ある?」 | 製造業 5 社、うち上場 2 社で運用中 | (内部資料) |
| 「セキュリティは?」 | OSS+ 自社運用で完全在内、SOC2 準拠 (Enterprise エディション) | NOTICE.md |
...
```

### Before / After

| 観点 | Before | After |
|------|--------|-------|
| リサーチ所要時間 | 4〜8 時間 (IR + プレス + 業界レポート読み込み) | **30〜60 分** |
| 商談ストーリーボード作成 | 別途 2〜3 時間 | **同時生成 (フロー内で完結)** |
| 仮説の質 | 主要 1〜2 仮説 | 上位 3 仮説 + 各々の根拠と反証 |
| FAQ の準備 | 想定 5 問程度を口頭で確認 | **5 問の表形式 (質問 / 推奨回答 / 公開ソース)** |
| 提案合意率 | ベース | **+15〜20pt** |
| 1 商談あたりの準備時間 | 6 時間 | **1 時間** |
| 週次商談本数 | 3 件 | **6〜8 件** |

### UC-2: RFP 回答書の作成支援

**業務シーン**: SIer が官公庁・大企業の RFP に対する 50〜100 ページの回答書を作る。

```python
from praxia import Praxia
from praxia.flows import SalesAgentFlow

p = Praxia(user_id="se_kenta", default_model="claude")

# 過去案件からの転用率を高めるため、個人メモリを活用
result = p.run(SalesAgentFlow, inputs={
    "customer_name": "公的機関 X",
    "product": "業務システム刷新",
    "additional_context": open("rfp_doc.pdf").read(),  # PDFテキスト化
})

# Praxia の個人メモリに過去 100 案件分の RFP 対応パターンが
# 蓄積されているため、自動的にコンテキストに含まれる
print(result.final_output)
```

| 観点 | Before | After |
|------|--------|-------|
| 回答書ドラフト時間 | 2 週間 (営業 2 名 + SE 3 名) | **3〜5 営業日** |
| 過去案件からの転用率 | 30〜50% (担当者の記憶頼み) | **70〜85%** (個人メモリから自動引用) |
| 抜け漏れ件数 | 5〜10 件 (再質問発生) | **1〜2 件** |
| 受注率 | ベース | **+5〜10pt** |

### UC-3: インサイドセールスのリード優先順位付け

**業務シーン**: SaaS スタートアップで毎日 50〜100 件の問合せを処理する IS チーム。

```python
# IS チーム共有スキルとして登録
class LeadScoringSkill(Skill):
    manifest = SkillManifest(
        name="lead_scoring",
        description="リードを Hot / Warm / Cold に分類",
        domain="sales",
    )
    system_prompt = """
    あなたは IS の専門家です。問い合わせフォームの内容、企業規模、業界、
    記述された課題から以下を判定:
    - Hot: 1 週間以内のフォロー必須 (具体的予算・期限あり)
    - Warm: 1 ヶ月以内のフォロー
    - Cold: 四半期に 1 回でいい
    各分類の根拠を必ず明示。
    """
```

| 観点 | Before | After |
|------|--------|-------|
| リード分類所要時間 | 1 件あたり 5 分 (SDR 判断) | **30 秒 (AI 一次判定 → SDR 確認)** |
| Hot リード見逃し率 | 10〜15% | **3〜5%** |
| 1 日処理件数 | 50〜80 件 | **150〜200 件** |
| アポ獲得率 | ベース | **+8〜12pt** |

## 個人 → 組織知の循環例

ベテラン SE が「金融業向け RFP の付帯条件記述パターン」を 10 年かけて蓄積していたとします:

```python
# Senior SE が日常的に使う中で、効果的なパターンが個人メモリに溜まる
p_senior = Praxia(user_id="senior_se_taro")
# 100 案件 RFP 対応 → 個人メモリに 100 件のパターン蓄積

# 受注時に成果記録 (Phase 2)
for episode_id, won in episode_outcomes.items():
    p_senior.personal_memory.record_outcome(
        episode_id=episode_id,
        success=won,  # 受注 / 失注
        score=contract_value if won else 0,
    )

# 夜間バッチで Sleep-time Consolidator 実行
# → 3 名以上の SE が類似パターンを使うようになる
# → 受注率との相関 0.8 以上
# → 自動昇格 (auto_threshold=0.75 超)
```

組織共有プロンプトに自動追加されると、

```bash
praxia user list
# admin   senior_se_taro
# member  junior_se_yuki

praxia skill promote --candidates
# 候補:
#   sales_rfp_finance         (users=4, count=15, success_rate=72%)
```

新人は初日から同じ品質で動けるようになります。

## 自社カスタマイズ例

### CRM 連携 (Salesforce)

```python
from praxia.skills.skill import Skill, SkillManifest

class SalesforceProspectingSkill(Skill):
    manifest = SkillManifest(
        name="sf_prospecting",
        description="Salesforce アカウントから商談機会を発掘",
        domain="sales",
    )
    system_prompt = """
    Salesforce のアカウントデータから、以下の観点で商談機会を発掘:
    1. 直近 6 ヶ月で活動が止まっているアカウント (休眠開拓)
    2. 同業他社で導入実績があるが当社未導入のアカウント
    3. 拡大可能性の高い既存顧客 (アップセル候補)

    各観点ごとに上位 5 社をリスト化、推奨アプローチも併記。
    """
```

```python
# Salesforce SDK と組み合わせ
from simple_salesforce import Salesforce
import os

sf = Salesforce(username=os.environ["SF_USER"], password=os.environ["SF_PASS"], security_token=os.environ["SF_TOKEN"])

accounts = sf.query("SELECT Id, Name, Industry, AnnualRevenue FROM Account WHERE LastActivityDate < LAST_N_DAYS:180")
for acc in accounts['records']:
    skill = SalesforceProspectingSkill()
    insights = skill.run(f"Account: {acc['Name']}, Industry: {acc['Industry']}, AR: {acc['AnnualRevenue']}")
    # Slack や Salesforce にループバック
```

## 外部システム連携 — Salesforce + SharePoint + kintone と双方向

営業現場のシステム連携 3 セット:

```python
from praxia.connectors import get_connector
from praxia.flows import SalesAgentFlow
from praxia import Praxia

p = Praxia(user_id="alice", default_model="claude")

# (1) Salesforce から休眠アカウントを Pull
sf = get_connector("salesforce", username="...", password="...", security_token="...")
dormant = sf.pull(
    "SELECT Id, Name, Industry, LastActivityDate FROM Account "
    "WHERE LastActivityDate < LAST_N_DAYS:180 AND AnnualRevenue > 5000000000",
    limit=30,
)

# (2) SharePoint から関連 IR / 議事録を Pull
sp = get_connector("sharepoint", tenant_id="...", client_id="...", client_secret="...")

for acc in dormant:
    ir_files = sp.pull(f"<drive_id>:/IR/{acc.metadata['account_name']}", limit=5)

    # (3) Praxia で商談準備
    result = p.run(SalesAgentFlow, inputs={
        "customer_name": acc.name,
        "product": "Praxia Sales",
        "additional_context": "\n\n".join(f.content[:2000] for f in ir_files),
    })

    # (4) kintone の営業管理アプリにプッシュ (ToDo として)
    kt = get_connector("kintone", subdomain="acme", api_token=os.environ["KINTONE_TOKEN"])
    kt.push("42", json.dumps({
        "account_id": {"value": acc.id},
        "preparation_summary": {"value": result.final_output[:5000]},
        "status": {"value": {"value": "ready_for_outreach"}},
    }))
```

## ACL で営業データへのアクセスを制御

「アシスタント (member) は休眠リストには触れさせたくない」場合:

```bash
praxia policy add deny connector "salesforce:*LastActivityDate*" \
    --principals "role:member" \
    --description "休眠リストはセールス・オペレーターのみ"
```

## ベスプラの組織配信

ベテラン営業の RFP 回答テンプレを全社員に配信:

```bash
praxia prompt distribute b2b_rfp_template rfp_template.md \
    --target-roles member,operator \
    --description "金融業向け RFP 回答テンプレ (実績 +12pt)"

praxia skill distribute sales_strategist --target-roles member
```

## まとめ

Praxia の営業業務での価値:

1. **時間圧縮**: 商談準備 6h → 1h
2. **品質向上**: 提案合意率 +15〜20pt、Hot リード見逃し −66%
3. **組織知の自動化**: 過去 RFP の効果的パターンが新人にも届く
4. **CRM/CS 連携**: Salesforce / HubSpot / Slack に組み込み可能
5. **ガードレール**: 公開情報のみを根拠にする、与信情報は扱わない、過剰なクロージングを避ける

⭐ [GitHub](https://github.com/your-org/praxia) | 📦 `pip install praxia`

---

> **シリーズ次回**: 設計業務での Praxia 活用 — シニア・アーキトの可処分時間を週 16h → 4h に
