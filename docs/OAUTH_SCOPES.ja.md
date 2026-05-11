# コネクタ別 OAuth スコープ

> 🇬🇧 [English](OAUTH_SCOPES.md)

各 per-user-OAuth コネクタについて以下を記載:

- Praxia 同梱の OAuth プロバイダ設定
- 必要スコープ (`praxia.connectors.oauth.providers` の既定値)
- 最小権限のために**削除可能な**スコープ
- 当該プロバイダでの OAuth アプリ登録 URL
- 設定すべき redirect URI

`praxia serve` を `PRAXIA_PUBLIC_URL=https://praxia.example.com` で運用する場合、redirect URI は **常に** `https://praxia.example.com/api/v1/oauth/{provider}/callback` です。

---

## 早見表

| コネクタ | プロバイダ設定 | 既定スコープ | アプリ登録 URL |
|---|---|---|---|
| Box | `BOX_OAUTH` | `root_readwrite` | <https://app.box.com/developers/console> |
| SharePoint / OneDrive / Teams | `MICROSOFT_OAUTH` | `offline_access User.Read Files.ReadWrite.All Sites.ReadWrite.All` (+ Teams 用追加) | <https://entra.microsoft.com/> |
| Dropbox | `DROPBOX_OAUTH` | `files.metadata.read files.content.read files.content.write` | <https://www.dropbox.com/developers/apps> |
| Google Drive / Gmail | `GOOGLE_OAUTH` | `https://www.googleapis.com/auth/drive` | <https://console.cloud.google.com/apis/credentials> |
| Salesforce | `SALESFORCE_OAUTH` | `api refresh_token offline_access` | <https://help.salesforce.com/> |
| Notion | `NOTION_OAUTH` | (workspace 単位の許可、スコープなし) | <https://www.notion.so/my-integrations> |
| Confluence + Jira | `ATLASSIAN_OAUTH` | `read:confluence-content.* write:confluence-content read:jira-work write:jira-work offline_access` | <https://developer.atlassian.com/console/myapps/> |
| Slack | `SLACK_OAUTH` | `channels:history channels:read groups:* im:history files:* chat:write users:read search:read` | <https://api.slack.com/apps> |
| GitHub | `GITHUB_OAUTH` | `repo read:org read:user` | <https://github.com/settings/developers> |
| HubSpot | `HUBSPOT_OAUTH` | `crm.objects.contacts.* crm.objects.companies.read crm.objects.deals.*` | <https://developers.hubspot.com/> |
| Zendesk | `ZENDESK_OAUTH` | `read write` | `<your-subdomain>.zendesk.com/admin/.../oauth_clients` |
| Linear | `LINEAR_OAUTH` | `read write` | <https://linear.app/settings/api> |
| kintone | `KINTONE_OAUTH` | `k:app_record:read k:app_record:write k:app_settings:read k:file:read k:file:write` | `<your-tenant>.cybozu.com` → cybozu.com共通管理 → OAuth クライアント |

---

## 1. Box (`box`)

**既定スコープ:** `root_readwrite`

**理由:** Box は API 単位ではなく高レベル "developer scopes" を採用。`pull` と `push` 両方に必要。

**最小権限:** 読み込み専用なら `root_readonly`。`extra_authorize_params={"scope": "root_readonly"}` で上書き可能。`push` は意図通り 403 で失敗します。

**アプリ登録手順:**
1. <https://app.box.com/developers/console> → Custom App → OAuth 2.0
2. Redirect URI: `https://praxia.example.com/api/v1/oauth/box/callback`
3. 環境変数: `PRAXIA_OAUTH_BOX_CLIENT_ID` / `PRAXIA_OAUTH_BOX_CLIENT_SECRET`

---

## 2. Microsoft (`microsoft` — SharePoint / OneDrive / Teams / Outlook 共通)

**既定 (Files / Sites):**
```
offline_access User.Read Files.ReadWrite.All Sites.ReadWrite.All
```

**Teams メッセージング追加:**
```
ChannelMessage.Read.All ChannelMessage.Send
```

**Outlook メール追加 (Email connector with backend="outlook"):**
```
Mail.Read Mail.Send Mail.ReadWrite
```

**最小権限:**
- Files のみ・読込専用: `Sites.ReadWrite.All` 削除、`Files.ReadWrite.All` → `Files.Read.All`
- Mail のみ・読込専用: `offline_access User.Read Mail.Read`

**アプリ登録 (Microsoft Entra ID):**
1. <https://entra.microsoft.com/> → アプリの登録 → 新規登録
2. プラットフォーム: **Web**
3. Redirect URI: `https://praxia.example.com/api/v1/oauth/microsoft/callback`
4. API のアクセス許可 → Microsoft Graph → 委任されたアクセス許可 → 上記スコープ追加
5. 証明書とシークレット → 新しいクライアント シークレット
6. `PRAXIA_OAUTH_MICROSOFT_CLIENT_ID` / `PRAXIA_OAUTH_MICROSOFT_CLIENT_SECRET`
7. (マルチテナント) `PRAXIA_SSO_TENANT_ID=common`、(シングルテナント) テナント ID 指定

---

## 3. Dropbox (`dropbox`)

**既定:**
```
files.metadata.read files.content.read files.content.write
```

**最小権限:**
- 読込専用: `files.content.write` 削除
- 単一フォルダ: アプリタイプを **App folder** にする (`/Apps/<your-app>/` のみ)

**アプリ登録:**
1. <https://www.dropbox.com/developers/apps> → Create app
2. Scoped access → App folder (推奨) または Full Dropbox
3. Redirect URI: `https://praxia.example.com/api/v1/oauth/dropbox/callback`
4. Permissions タブで上記 3 スコープ有効化
5. `PRAXIA_OAUTH_DROPBOX_CLIENT_ID` / `PRAXIA_OAUTH_DROPBOX_CLIENT_SECRET`

---

## 4. Google (`google` — Drive / Gmail / 将来 Calendar 用)

**既定:**
```
https://www.googleapis.com/auth/drive
```

**Gmail backend 追加:**
```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

**Calendar (将来):**
```
https://www.googleapis.com/auth/calendar.readonly
```

**最小権限:**
- Drive 読込専用: `https://www.googleapis.com/auth/drive.readonly`
- ユーザがピックしたファイルのみ: `https://www.googleapis.com/auth/drive.file`

**アプリ登録:**
1. <https://console.cloud.google.com/apis/credentials> → OAuth クライアント ID 作成 → ウェブアプリ
2. 承認済みリダイレクト URI: `https://praxia.example.com/api/v1/oauth/google/callback`
3. OAuth 同意画面 → "External" 公開 or Workspace 組織制限
4. `PRAXIA_OAUTH_GOOGLE_CLIENT_ID` / `PRAXIA_OAUTH_GOOGLE_CLIENT_SECRET`

> Google は refresh token のため `access_type=offline` + `prompt=consent` 必須。Praxia が自動設定。

---

## 5. Salesforce (`salesforce`)

**既定:**
```
api refresh_token offline_access
```

**Marketing Cloud / Pardot 等追加:**
```
chatter_api full
```

**最小権限:** `api` だけで SOQL + sObject 操作可能。`full` は管理 API が必要なときのみ。

**アプリ登録:**
1. Setup → アプリケーション マネージャ → 新規接続アプリケーション
2. OAuth 設定有効化、コールバック URL: `https://praxia.example.com/api/v1/oauth/salesforce/callback`
3. 選択された OAuth スコープ: API アクセス (`api`)、ユーザに代わって任意の時点でリクエスト実行 (`refresh_token, offline_access`)
4. **重要**: 機密クライアントの PKCE を有効化
5. 保存後 ~10 分待つ (反映時間)
6. `PRAXIA_OAUTH_SALESFORCE_CLIENT_ID` / `PRAXIA_OAUTH_SALESFORCE_CLIENT_SECRET`

---

## 6. Notion (`notion`)

**既定スコープ:** なし — Notion は **workspace 単位の許可** モデル。インストール時にユーザがアクセス許可するページ / DB を選択。

**ページ単位制限:** OAuth フロー中にユーザがアクセス対象を選択。コード側で制限する手段は無し (完全にユーザコントロール)。

**アプリ登録:**
1. <https://www.notion.so/my-integrations> → New integration
2. Type: **Public integration** (OAuth 用)
3. Redirect URI: `https://praxia.example.com/api/v1/oauth/notion/callback`
4. Capabilities: Read content / Update content / Insert content (必要に応じて)
5. `PRAXIA_OAUTH_NOTION_CLIENT_ID` / `PRAXIA_OAUTH_NOTION_CLIENT_SECRET`

> Notion はトークンエンドポイントで **HTTP Basic 認証** (Bearer ではない)、PKCE **非対応**。Praxia の `OAuthFlow` は `pkce=False` で対応。

---

## 7. Atlassian (`atlassian` — Confluence + Jira 共通)

**既定:**
```
read:confluence-content.summary
read:confluence-content.all
write:confluence-content
read:jira-work
write:jira-work
offline_access
```

**最小権限:**
- Confluence 読込専用: `*jira*` 4 つ + `write:confluence-content` 削除
- Jira 読込専用: `*confluence*` 4 つ + `write:jira-work` 削除
- 全読込専用: `write:*` 削除

**アプリ登録:**
1. <https://developer.atlassian.com/console/myapps/> → Create → OAuth 2.0 (3LO) integration
2. Permissions タブ → Confluence API + Jira API 追加
3. 上記スコープから必要なもの追加
4. Authorization タブ → callback URL: `https://praxia.example.com/api/v1/oauth/atlassian/callback`
5. Distribution タブ → 公開準備完了で "Sharing" に
6. `PRAXIA_OAUTH_ATLASSIAN_CLIENT_ID` / `PRAXIA_OAUTH_ATLASSIAN_CLIENT_SECRET`

> 実行時に `cloud_id` (または `site_url`) を connector に渡す必要があります — Atlassian アプリは複数サイトにインストール可能なため、対象を指定する必要あり。

---

## 8. Slack (`slack`)

**既定 (bot):**
```
channels:history channels:read
groups:history groups:read
im:history
files:read files:write
chat:write
users:read
search:read
```

**最小権限:**
- 読込のみ: `chat:write` + `files:write` 削除
- パブリックチャンネルのみ: `groups:*` + `im:history` 削除
- ファイルアップロード不要: `files:write` 削除

**アプリ登録:**
1. <https://api.slack.com/apps> → Create New App → From scratch
2. OAuth & Permissions → Redirect URLs: `https://praxia.example.com/api/v1/oauth/slack/callback`
3. Bot Token Scopes に上記スコープ追加
4. ワークスペースにアプリインストール
5. `PRAXIA_OAUTH_SLACK_CLIENT_ID` / `PRAXIA_OAUTH_SLACK_CLIENT_SECRET`

> Slack v2 OAuth は機密クライアント (PKCE 不使用)。**bot token** (`xoxb-...`) と任意で **user token** (`xoxp-...`) を発行。Praxia は既定で bot token を使用。

---

## 9. GitHub (`github`)

**既定:**
```
repo read:org read:user
```

**最小権限:**
- public repo のみ: `repo` → `public_repo`
- 組織情報不要: `read:org` 削除
- ユーザ情報不要: `read:user` 削除

**fine-grained access には GitHub App を使用** (OAuth App ではなく) — 別 connector パターン (v1.2 で計画)。

**アプリ登録:**
1. <https://github.com/settings/developers> → OAuth Apps → New OAuth App
2. Authorization callback URL: `https://praxia.example.com/api/v1/oauth/github/callback`
3. 作成後: Generate a new client secret
4. `PRAXIA_OAUTH_GITHUB_CLIENT_ID` / `PRAXIA_OAUTH_GITHUB_CLIENT_SECRET`

---

## 10. HubSpot (`hubspot`)

**既定:**
```
crm.objects.contacts.read
crm.objects.contacts.write
crm.objects.companies.read
crm.objects.deals.read
crm.objects.deals.write
```

**チケット / engagement 追加:**
```
crm.objects.tickets.read crm.objects.tickets.write
sales-email-read content
```

**最小権限:**
- CRM 読込専用: `*.write` 全削除
- 商談不要: `crm.objects.deals.*` 削除

**アプリ登録:**
1. <https://developers.hubspot.com/> で開発者アカウント作成
2. Public App 作成 → Auth タブ → Redirect URL: `https://praxia.example.com/api/v1/oauth/hubspot/callback`
3. Scopes タブ → 上記スコープ有効化
4. `PRAXIA_OAUTH_HUBSPOT_CLIENT_ID` / `PRAXIA_OAUTH_HUBSPOT_CLIENT_SECRET`

---

## 11. Zendesk (`zendesk`)

**既定:**
```
read write
```

**注:** Zendesk のスコープは `read` / `write` の 2 段階のみ (チケット専用なら `tickets:read` / `tickets:write`)。既定で全オブジェクトをカバー。

**アプリ登録:**
1. Zendesk アカウントにサインイン: `<your-subdomain>.zendesk.com/admin`
2. Apps and integrations → APIs → Zendesk API → OAuth Clients → Add OAuth client
3. Redirect URLs: `https://praxia.example.com/api/v1/oauth/zendesk/callback`
4. 保存 → Unique Identifier 控え + secret コピー (一度のみ表示)
5. `PRAXIA_OAUTH_ZENDESK_CLIENT_ID` / `PRAXIA_OAUTH_ZENDESK_CLIENT_SECRET`

> Zendesk URL は **サブドメイン依存**。Praxia の `ZENDESK_OAUTH.authorize_url` には `{subdomain}` プレースホルダ。connector / OAuth フローが `PRAXIA_CONN_ZENDESK_SUBDOMAIN` から展開。

---

## 12. Linear (`linear`)

**既定:**
```
read write
```

**注:** Linear のスコープは `read` / `write` / `issues:create` / `admin` の 4 種。既定で通常ワークフローをカバー。

**アプリ登録:**
1. <https://linear.app/settings/api> → OAuth applications → New OAuth application
2. Callback URLs: `https://praxia.example.com/api/v1/oauth/linear/callback`
3. Permissions: Read + Write (or 取り込み専用なら Read のみ)
4. `PRAXIA_OAUTH_LINEAR_CLIENT_ID` / `PRAXIA_OAUTH_LINEAR_CLIENT_SECRET`

> Linear は OAuth 不要の個人 API key も受け付ける — シングルユーザ / スクリプト用途は connector に `api_key=...`。

---

## 13. kintone (`kintone`)

**既定:**
```
k:app_record:read k:app_record:write k:app_settings:read k:file:read k:file:write
```

**注:** kintone のスコープはリソース別: `k:app_record:read|write` がレコード CRUD、`k:app_settings:read|write` がアプリ設定、`k:file:read|write` が添付ファイル。Praxia にアプリ設定変更を許可しない場合は `k:app_settings:write` を外す。

**テナント別 URL:** kintone OAuth エンドポイントはテナントのサブドメインを埋め込みます。環境変数 `PRAXIA_OAUTH_KINTONE_SUBDOMAIN` に自社テナント(例: `acme` ⇒ `acme.cybozu.com`)を設定。flow が `https://acme.cybozu.com/oauth2/authorization` / `/token` に解決します。

**アプリ登録:**
1. cybozu.com 管理者 → 「cybozu.com 共通管理」→ OAuth クライアント → 「追加する」
2. Redirect URL: `https://praxia.example.com/api/v1/oauth/kintone/callback`
3. スコープにチェック: `k:app_record:read`, `k:app_record:write`, `k:app_settings:read`, `k:file:read`, `k:file:write` (Praxia にアプリ設定変更を許可しないなら `k:app_settings:write` は外す)
4. `PRAXIA_OAUTH_KINTONE_CLIENT_ID` / `PRAXIA_OAUTH_KINTONE_CLIENT_SECRET` / `PRAXIA_OAUTH_KINTONE_SUBDOMAIN`

> kintone は静的な `X-Cybozu-API-Token` (アプリ単位、ユーザ単位ではない) や HTTP Basic 認証 (`username`+`password`) も受け付けますが、新規導入は OAuth を推奨 — 各 Praxia ユーザは kintone 側で自分のアカウントに許可されたレコードのみアクセスできます。

---

## デプロイメント別スコープカスタマイズ

既定と異なるスコープが必要な場合 (テナント別の読込専用ビルド等)、construction time にオーバライド:

```python
from praxia.connectors.oauth import OAuthFlow, BOX_OAUTH

# カスタム: 読込専用 Box
flow = OAuthFlow(
    BOX_OAUTH,
    client_id=...,
    client_secret=...,
    redirect_uri=...,
)
url, state = flow.authorization_url(
    user_id="alice",
    scopes=["root_readonly"],   # BOX_OAUTH.default_scopes をオーバライド
)
```

HTTP `/api/v1/oauth/{provider}/start` endpoint は現在既定スコープを使用。リクエスト毎カスタマイズが必要なら fork or `scope_override` query param サポート PR を歓迎。

---

## 付与されたスコープの確認

OAuth 完了後、ユーザが実際に許可したスコープを確認:

```python
from praxia.connectors.oauth import OAuthTokenStore

store = OAuthTokenStore()
token = store.get("alice", "slack")
print(token.scope)         # スペース区切りのスコープ文字列
print(token.extra)         # token endpoint 応答の生データ (provider 固有 extras)
```

監査用途では、OAuth 交換成功毎に `oauth.complete` ログが書かれます (provider 名 + user id のみ。スコープは token-store の責任)。

---

## セキュリティ考慮事項

- **常に最小権限から開始**。必要に応じてスコープ追加
- **トークンは保管暗号化** — 設定された KMS adapter で envelope encryption。詳細: [`docs/legal/GDPR_NOTES.ja.md`](legal/GDPR_NOTES.ja.md), [`SECURITY.md`](../SECURITY.md)
- **per-user OAuth ⇒ 各 Praxia ユーザが自身のトークンを許可**。admin アカウント侵害だけでは保管トークンに直接アクセスできない (KMS 鍵 + user_id マッピング必要)
- **client secret を四半期毎にローテート**。Praxia は env から読むのでコード変更不要
- **失効:** `praxia oauth revoke <provider> --user-id <id>` (CLI) または `DELETE /api/v1/oauth/{provider}` (HTTP)。一部プロバイダは長期未使用で自動失効
