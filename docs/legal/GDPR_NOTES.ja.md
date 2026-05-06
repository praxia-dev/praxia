# GDPR に関する留意事項

> 🇬🇧 English: [GDPR_NOTES.md](GDPR_NOTES.md)
> ステータス: **テンプレート — 商用利用前に弁護士レビュー必須。**

本書は Praxia を運用する際のシナリオ別 GDPR データ管理者の役割を整理した資料です。法的助言ではありません。「管理者 (controller)」と「処理者 (processor)」の区分は事実関係に強く依存します。EU ユーザを対象に本番運用する場合は、必ず privacy 専門弁護士に役割確認をしてください。

---

## 1. 役割の早見表

| シナリオ | あなたの行為 | EU データ主体は関与? | GDPR 上の役割 |
|---|---|---|---|
| **A.** PyPI / GitHub に Praxia を公開 | コード配布のみ | n/a | 適用対象外 (個人データ無し) |
| **B.** 自社内で Praxia を self-host | Praxia インストール運用 | 同僚 / 顧客 | **管理者** (メモリ + 監査 + OAuth トークン) |
| **C.** Praxia.dev ランディングを運用 | 静的サイト + 連絡用メール | EU 訪問者 | **管理者** (Cookie + フォーム送信) |
| **D.** マネージド Praxia サービス提供 | ホスト型 Praxia + テナントデータ | 顧客のエンドユーザ | テナントデータの **処理者**、課金 / アカウントデータの **管理者** |
| **E.** Praxia に PR を提出 | n/a | n/a | 適用対象外 |

---

## 2. シナリオ A — OSS 配布

GitHub / PyPI にコードを公開するだけの活動には **GDPR は適用されません**。個人データを収集・保管・処理していないためです。

**留意点:**
- GitHub 自体は寄稿者データ (commit author email, IP) を処理。これは GitHub の責任 (GitHub Privacy Statement 参照)
- Issue / PR の受付では、寄稿者の email・内容は GitHub のポリシー範疇
- Praxia 同梱のテンプレート (TERMS / PRIVACY / COOKIES / ACCEPTABLE_USE) は法的レビュー前提の雛形。法的助言ではありません

---

## 3. シナリオ B — Self-hosted Praxia

EU 内のユーザに対して `praxia ui` / `praxia serve` を自社インフラで運用する場合、**あなたが Praxia 内のデータの管理者** となります。

### 3.1 Praxia が保管する個人データ

コード調査からの整理:

| カテゴリ | 保管場所 | 適法性根拠 (典型的) |
|---|---|---|
| ユーザアカウント (username / email / role / last_login) | `.praxia/auth/users/` | 契約 / 正当な利益 |
| API キーハッシュ (bcrypt) | 同上 | 契約 |
| OAuth トークン (Box / SharePoint / Google 等) | `.praxia/auth/oauth_tokens.jsonl` (KMS による envelope 暗号化) | 同意 |
| 個人メモリ (episodes / facts / preferences / outcomes) | `.praxia/personal/<user_id>.jsonl` (または選択した LTM backend) | 契約 / 正当な利益 |
| 監査ログ | `.praxia/auth/audit/audit.jsonl` (追記専用、0600 perms) | 法的義務 / 正当な利益 |
| コネクタ pull/push | 監査ログに記録、ペイロード自体は既定で永続化なし | 契約 |
| スキル / フロー入出力 | エピソードとして記録 (mode 制御) | 契約 |
| セッション JWT | 永続化なし、`PRAXIA_JWT_SECRET` で署名 | 契約 |

### 3.2 データ主体の権利の充足方法

Praxia は GDPR 第 15-22 条のための運用ツールを提供:

| 権利 | 条 | Praxia での対応 |
|---|---|---|
| アクセス権 | 15 | `praxia admin export-memory --user-id <id>` + `praxia admin export-users` (対象 filter) + 監査ログ filter |
| 訂正権 | 16 | `praxia user update <id> --email X` |
| 消去権 | 17 | `praxia user delete <id>` (hard delete) — 個人メモリ + OAuth トークンも削除。監査ログには redacted な「削除実行」記録のみ残る |
| 処理制限権 | 18 | `praxia user deactivate <id>` (ソフト) または `praxia memory mode --user-id <id> read_only` |
| ポータビリティ権 | 20 | `praxia admin export-memory` で JSONL 出力 — 機械可読・構造化済 |
| 異議申立権 | 21 | ユーザ毎の memory mode を `read_only` に |
| 自動意思決定 (Art. 22) | — | Praxia の出力は補助的 — 自律的決定ではない |

**注**: 監査ログは追記専用設計のため `user.delete` 後も残存します (削除イベント記録のため)。第 17 条 (消去) と第 5(1)(f) 条 (完全性) のバランスは弁護士相談を — 多くの規制当局は監査の tombstoning を破棄より許容します。

### 3.3 本番運用での必須設定

| 設定 | 理由 |
|---|---|
| `PRAXIA_JWT_SECRET` (32 byte 以上のランダム値、固定) | 認証完全性。再起動跨いでセッション有効性確保 |
| `PRAXIA_TOKEN_ENC_KEY` または `PRAXIA_KMS_ADAPTER=aws/azure/gcp/vault` | OAuth トークンの保管暗号化 |
| `.praxia/` のファイルパーミッション | サービスユーザのみ。監査ファイルは既定 0600 |
| バックアップ暗号化 | `.praxia/` のバックアップは保管暗号化を維持すること |

### 3.4 サブ処理者 (self-host 時)

メモリバックエンドに `mem0` / `zep` / `hindsight` を選んだ場合 (または LLM プロバイダを利用する場合)、**あなたが管理者で、彼らがあなたの処理者** という関係になります。必要事項:

- 当該ベンダーとの DPA (Data Processing Agreement)
- EU → 米国データ移転がある場合は SCC (Standard Contractual Clauses) (OpenAI, Anthropic, Google, AWS 等は click-through で対応済)
- EU ユーザへのサブ処理者開示

Praxia は完全オンプレ運用 (Ollama Gemma + JSON backend) もサポート — この構成では第三者サブ処理者なし。規制が厳しい EU 顧客への最短ルートです。

---

## 4. シナリオ C — Praxia.dev ランディングページ

静的ランディングページが処理するデータ:

| データ | Cookie / 方式 | 適法性根拠 |
|---|---|---|
| 選択言語 | `localStorage["praxia-lang"]` | 厳密に必要 (Art. 6(1)(f)) |
| Cookie 同意記録 | `localStorage["praxia-consent"]` | 厳密に必要 |
| 匿名訪問数 | Cloudflare Web Analytics (Cookie レス) — **opt-in 時のみ** | 同意 (Art. 6(1)(a)) |
| 連絡メール (`hello@praxia.dev`) 受信 | メール inbox | 正当な利益 |

**同意バナー** ([consent.js](../landing/consent.js)) の実装:
- 分析は既定 OFF (明示的な opt-in なしには分析 Cookie を設定しない)
- 「すべて許可」/「必須のみ」/「詳細設定」の 3 択
- フッタの「Cookie 設定」リンクで再オープン可能
- バージョン付き同意記録 (ポリシー変更時に再表示)

**サイト商用化時に推奨される対応:**
1. 本フォルダのテンプレートを実際の弁護士でレビュー
2. サブ処理者一覧を記載 (Cloudflare、GitHub Pages、Cloudflare Pages、メールプロバイダ等)
3. PRIVACY.md に実際の連絡窓口住所を記載
4. DPO 配置義務を判定 (規模拡大時 / 特別カテゴリデータ取扱時)

---

## 5. シナリオ D — マネージド Praxia サービス (Team プラン)

複数テナントのホスト型 Praxia を有償提供する場合:

- **顧客アカウントデータ** (課金、ログイン email) → あなたが管理者
- **顧客テナント内のエンドユーザデータ** (メモリ、OAuth トークン) → 通常あなたは処理者、顧客が管理者
- 必要事項:
  - 各企業顧客との DPA 締結 (テンプレート + click-through)
  - サブ処理者一覧 (ホスティング、KMS、選択された LLM プロバイダ等)
  - 漏洩通知プロセス: 顧客への 72 時間以内通知 (顧客が必要に応じて自社規制当局へ通知)
  - 保持ポリシー (アクティブアカウントは既定 12-24 ヶ月、監査ログは法的保管要件に応じて延長)
  - 忘れられる権利のワークフロー (`praxia user delete` + `praxia connector revoke-all` 経路と紐付け)

Praxia v1.0 はホスト型サービスとして**まだ提供されていません**。Team プラン開始時、本書は具体的なサブ処理者一覧を記載した版に更新します。

---

## 6. 特別カテゴリのデータ (Art. 9)

Praxia は健康 / 政治信条 / 生体 / 性的指向データの処理を**想定していません**。これらに該当する用途 (医療、HR バックグラウンド調査、犯罪歴) では第 9 条が追加保護を要求:

- 適法性根拠の高基準 (明示同意または特定例外)
- DPIA (Art. 35) がしばしば必要
- 厳格な保持 + アクセス制御

該当用途では以下を推奨:
- 機微コンテンツのセッションは `praxia memory mode --user-id X read_only` を都度設定
- テナント全体強制は `praxia admin memory-policy-set --enforced-backend mem0 --mode-locked --default-mode read_only`
- OAuth トークンは KMS 暗号化 (`PRAXIA_KMS_ADAPTER=aws` 以上)
- 可能ならエアギャップ運用 (Gemma + Ollama + JSON backend)

---

## 7. 国際移転

EU ユーザのデータが EU/EEA 外 (例: 米国ホスト LLM プロバイダ) へ移転される場合:

- 移転メカニズムが必要: SCC (Standard Contractual Clauses) が最も一般的。一部ベンダーは 2024 年以降 EU-US Data Privacy Framework 認定済
- Praxia は **移転を完全に回避できる** — EU リージョンの LLM endpoint 利用 or 完全ローカルモデル (Gemma / Qwen via Ollama)
- 判断と保護措置を Privacy Policy に明記してください

---

## 8. 子供のデータ

Praxia はビジネス / 専門用途を想定。16 歳未満の子供のデータを意図的に処理しません。TERMS テンプレートは利用者に対し 16 歳以上 (または当該地域のオンライン同意最低年齢以上) の確認を求めています。

---

## 9. 参考リンク

- EDPB ガイドライン: <https://www.edpb.europa.eu/our-work-tools/our-documents_en>
- ICO (英国) GDPR ガイド: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/>
- CNIL (フランス): <https://www.cnil.fr/en/data-protection-around-the-world>
- 個人情報保護委員会 (日本): <https://www.ppc.go.jp/personalinfo/>
- 標準契約条項 (SCC): <https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/standard-contractual-clauses-scc_en>

---

## 10. プライバシー懸念の報告

Praxia の使われ方が GDPR 違反だと思われる場合、またはコードベースのセキュリティ / プライバシー問題を発見された場合:

- <https://github.com/genarch/praxia/issues> で `privacy` ラベルを付けた issue を起票
- または `security@praxia.dev` までメール (PGP 鍵は今後公開予定)

7 日以内に応答することを目指しています。
