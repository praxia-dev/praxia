# Praxia 商標ポリシー

> 🇬🇧 English: [TRADEMARK.md](TRADEMARK.md)
> ステータス: **policy v1.0 — 出願中。本書は登録状況に関わらず Praxia 名称の使用を規律します。**

---

## 1. 商標とその所有者

**「Praxia」**(文字商標) と Praxia 視覚マーク (▣) は、本 OSS プロジェクトを公開する個人事業主 **GenArch** が所有します。

商標出願中の管轄:
- 日本 (JPO) — 第 9 類, 第 42 類
- 米国 (USPTO) — 第 9 類, 第 42 類
- 欧州連合 (EUIPO) — 第 9 類, 第 42 類

登録完了までの間、GenArch は 2026 年からの継続使用に基づく未登録 (コモンロー) 商標権を主張します。

---

## 2. なぜ Apache 2.0 プロジェクトに商標ポリシーが必要か

Apache License Version 2.0 は **商標権を付与しません**。同ライセンス [第 6 条](https://www.apache.org/licenses/LICENSE-2.0#trademarks) は明示しています:

> "This License does not grant permission to use the trade names, trademarks,
> service marks, or product names of the Licensor."

本ポリシーはこのギャップを埋めます。コードの利用・改変・再配布は自由ですが、「Praxia」という名称の使用は本ポリシーで規律します。

---

## 3. 許諾不要な利用 (申請なしで OK)

### 3.1 Nominative fair use (指示的フェアユース)

Praxia を名称で参照し、自社ソフトウェアとの関係を説明する用途:

- 「MyApp は Praxia をメモリ循環に利用しています」
- 「Praxia 1.0+ 互換」
- 「Praxia 用アダプタ」
- 「PyCon で Praxia について発表しました」

### 3.2 改変なしの再配布

Apache 2.0 ライセンスの下、NOTICE ファイルを含めて Praxia をそのまま (バイナリ / ソース) 再配布する場合は「Praxia」名称を維持して構いません。**ただし**、上流から本質的に乖離する機能追加をしたものを「Praxia」と呼び続けるのは不可。

### 3.3 プラグイン・拡張

Praxia を **拡張** するパッケージは、明確な複合・記述的形式での名称使用 OK:

- ✅ `praxia-connector-notion`
- ✅ `praxia-skill-hr-recruiting`
- ✅ "Praxia 用 Notion コネクタ"
- ❌ `praxia-pro` (公式ティアを示唆)
- ❌ `praxia-enterprise` (同上)
- ❌ `praxia-cloud` (同上)

コネクタ / バックエンド / パーサ / エクスポータ / OAuth プロバイダ / スキルは `praxia-<noun>-<service>` 形式を推奨。詳細は [CUSTOM_CONNECTORS.ja.md](../CUSTOM_CONNECTORS.ja.md)。

### 3.4 書籍・記事・コース・登壇

教材タイトル + 内容での Praxia 名称使用 OK:

- ✅ 「Praxia で構築するエージェント: ハンズオンチュートリアル」
- ✅ YouTube シリーズ「Praxia 30 分入門」
- ✅ Coursera コース「Praxia でメモリアーキテクチャを学ぶ」

`hello@praxia.dev` への通知は (任意ですが) 歓迎 — こちらで宣伝協力できます。

### 3.5 Praxia ロゴ (▣)

`▣` マークの使用条件:
- ✅ Praxia を参照するドキュメント内
- ✅ サービス上の「Powered by Praxia」バッジ
- ❌ 自社プロダクトロゴとしての使用
- ❌ 改変 (色変え / 回転 / 他マークとの結合) は許諾なしには不可

---

## 4. 許諾必要な利用

GenArch の事前書面許諾なしには以下を行えません:

### 4.1 フォークの「Praxia X」改名

Praxia を fork し、本質的改変を加えて再配布する場合、**「Praxia」を含まない名称** に改名する必要があります:

- ❌ `Praxia Plus`, `Praxia Enterprise`, `Praxia 2`, `MyCorp Praxia`
- ✅ `MemoryAgent`, `WorkflowOrchestratorX`, `Acme AI` — 新規名称を選定

ドキュメントに「Praxia から fork」と記載するのは Nominative fair use として OK。

### 4.2 「Praxia」を冠する SaaS / ホスト型サービス

以下は不可:

- ❌ `praxia.acme-corp.com` (Acme Corp が GenArch でない場合)
- ❌ 「Praxia by Acme」(サードパーティによる Praxia ホスト型販売)
- ❌ Slack アプリ「Praxia for Slack」(GenArch 提供でない場合)
- ✅ 「Acme AI (Praxia ベース)」— 参照のみ、名称専有なし

### 4.3 ドメイン名

以下のドメイン登録は不可:
- TLD で「praxia」を SLD として GenArch がプレゼンスを持つ領域 (`praxia.com`, `praxia.io`, `praxia.ai` 等は GenArch 意図的 reserve、未登録でも対象)
- 紛らわしい variant: `praxia-ai.com`, `praxiahq.com`, `getpraxia.com`

既に上記ドメイン登録済の場合は公開前に連絡を — 通常はコンテキスト次第で礼譲移転 / 共存対応します。

### 4.4 グッズ販売

Praxia 名称 / ロゴ付きの T シャツ・ステッカー・グッズの **有償販売** には書面ライセンス要。Meetup での無償配布 (200 個以下、視覚ガイドライン準拠) は許諾不要。

### 4.5 提携の誤導

以下は不可:
- 「Praxia / GenArch と公式提携」「公認」「承認済」と主張
- 「Praxia Certified」「Praxia Authorized」— 書面契約のあるパートナー専用
- フォークの動作について GenArch に責任があると示唆

---

## 5. 許諾申請方法

`trademark@praxia.dev` 宛 (または `trademark` ラベル付き GitHub Issue) に以下を含めて連絡:

1. 申請者 + 計画している名称
2. 「Praxia」の使用箇所 + 視覚的コンテキスト (mockup あれば)
3. あなたの活動と上流 Praxia の関係
4. 対象市場での混同懸念があれば

**通常許諾するもの:**
- 翻訳コミュニティ「Praxia 中文社区」「Praxia Japan」(非公式である旨明示)
- カンファレンスワークショップ「Praxia ハンズオン」
- 書籍 / 出版社利用

**通常拒絶するもの:**
- ホスト型サービスの「X-Praxia」改名
- 上流から本質的に乖離するフォークが「Praxia」名称を保持

14 日以内の応答を目指します。

---

## 6. 商標誤用の報告

以下の場合は `trademark@praxia.dev` に連絡:
- フォークが「Praxia X」と改名して公開されている
- ドメインスクワット
- タイポスクワット (「praxxia」「praxiaa」) / なりすまし

実際には大半のケースは「別名へ変更してください」の礼儀正しいメールで解決します。

---

## 7. 共存と grandfathering

本 OSS が 2026 年に launch される以前から「Praxia」または類似名称を使っているプロジェクトの取り扱い:

- **Praxia** は「習慣化された実践」を意味するラテン語 / 哲学用語。学術的小規模利用 (研究論文、哲学ブログ) は通常ソフトウェア商標 (第 9 類, 第 42 類) と抵触しません
- 既存ソフトウェアプロジェクトで「Praxia」または類似名称を使用中の方は連絡を — 先行使用を尊重しつつ当方マークを保護する共存合意を協議します

---

## 8. ポリシー改定

本ポリシーは進化します。最新版は `main` ブランチの [`docs/legal/TRADEMARK.ja.md`](TRADEMARK.ja.md)、各バージョンタグはリポジトリタグに anchor。**改定時、開始時点で許諾されていた利用を遡及的に制限することはありません。**

---

## 9. 連絡先

| 用途 | 連絡先 |
|---|---|
| 許諾申請 | trademark@praxia.dev |
| 誤用報告 | trademark@praxia.dev |
| 一般質問 | hello@praxia.dev |
| 公開議論 | GitHub Issue with `trademark` label |

---

## 10. 最後に

Apache 2.0 ライセンスは **コードのフォーク・改変・出荷の自由** を保証。商標ポリシーは **名称が出所識別の信頼できるシグナルであり続けること** を保証。両者は OSS の持続可能性のために設計されています。

境界を尊重いただきありがとうございます。
