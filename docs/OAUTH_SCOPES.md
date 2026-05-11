# OAuth scopes for each connector

> 🇯🇵 [日本語版](OAUTH_SCOPES.ja.md)

For every per-user-OAuth connector, this document lists:

- The exact OAuth provider configuration Praxia ships
- Required scopes (default in `praxia.connectors.oauth.providers`)
- Optional scopes you may want to **remove** for least privilege
- Where to register the OAuth app at the provider
- Redirect URI to configure

When you operate `praxia serve` with `PRAXIA_PUBLIC_URL=https://praxia.example.com`, the redirect URI is **always** `https://praxia.example.com/api/v1/oauth/{provider}/callback`.

---

## Quick map

| Connector | Provider config | Default scopes | App registration URL |
|---|---|---|---|
| Box | `BOX_OAUTH` | `root_readwrite` | <https://app.box.com/developers/console> |
| SharePoint / OneDrive / Teams | `MICROSOFT_OAUTH` | `offline_access User.Read Files.ReadWrite.All Sites.ReadWrite.All` (+ Teams scopes if used) | <https://entra.microsoft.com/> |
| Dropbox | `DROPBOX_OAUTH` | `files.metadata.read files.content.read files.content.write` | <https://www.dropbox.com/developers/apps> |
| Google Drive / Gmail | `GOOGLE_OAUTH` | `https://www.googleapis.com/auth/drive` | <https://console.cloud.google.com/apis/credentials> |
| Salesforce | `SALESFORCE_OAUTH` | `api refresh_token offline_access` | <https://help.salesforce.com/s/articleView?id=connected_app_overview.htm> |
| Notion | `NOTION_OAUTH` | (workspace-level grant; no per-scope) | <https://www.notion.so/my-integrations> |
| Confluence + Jira | `ATLASSIAN_OAUTH` | `read:confluence-content.* write:confluence-content read:jira-work write:jira-work offline_access` | <https://developer.atlassian.com/console/myapps/> |
| Slack | `SLACK_OAUTH` | `channels:history channels:read groups:history groups:read im:history files:read files:write chat:write users:read search:read` | <https://api.slack.com/apps> |
| GitHub | `GITHUB_OAUTH` | `repo read:org read:user` | <https://github.com/settings/developers> |
| HubSpot | `HUBSPOT_OAUTH` | `crm.objects.contacts.read crm.objects.contacts.write crm.objects.companies.read crm.objects.deals.read crm.objects.deals.write` | <https://developers.hubspot.com/docs/api/working-with-oauth> |
| Zendesk | `ZENDESK_OAUTH` | `read write` | `<your-subdomain>.zendesk.com/admin/apps-integrations/apis/zendesk-api/oauth_clients` |
| Linear | `LINEAR_OAUTH` | `read write` | <https://linear.app/settings/api> |
| kintone | `KINTONE_OAUTH` | `k:app_record:read k:app_record:write k:app_settings:read k:file:read k:file:write` | `<your-tenant>.cybozu.com` → cybozu.com共通管理 → OAuth クライアント |

---

## 1. Box (`box`)

**Default scopes:** `root_readwrite`

**Why:** Box uses high-level "developer scopes" not per-API ones. `root_readwrite` is required for both `pull` (read folders + files) and `push` (upload).

**Least-privilege alternative:** for read-only use cases, set up your Box app with **only** `root_readonly` and pass it in `extra_authorize_params={"scope": "root_readonly"}`. Praxia's `push` will then fail with 403, which is the desired outcome.

**App registration:**
1. Go to <https://app.box.com/developers/console>
2. Create custom app → OAuth 2.0 with JWT or Standard OAuth 2.0
3. Add redirect URI: `https://praxia.example.com/api/v1/oauth/box/callback`
4. Set `PRAXIA_OAUTH_BOX_CLIENT_ID` + `PRAXIA_OAUTH_BOX_CLIENT_SECRET`

---

## 2. Microsoft (`microsoft` — used by SharePoint, OneDrive, Teams, Outlook mail)

**Default scopes (Files / Sites):**
```
offline_access User.Read Files.ReadWrite.All Sites.ReadWrite.All
```

**Add for Teams messaging:**
```
ChannelMessage.Read.All ChannelMessage.Send
```

**Add for Outlook mail (Email connector with backend="outlook"):**
```
Mail.Read Mail.Send Mail.ReadWrite
```

**Least-privilege alternative:**
- Files-only, read-only: drop `Sites.ReadWrite.All`, change `Files.ReadWrite.All` → `Files.Read.All`
- Mail-only, read-only: `offline_access User.Read Mail.Read`

**App registration (Microsoft Entra ID):**
1. Go to <https://entra.microsoft.com/> → App registrations → New registration
2. Platform: **Web** (not Single-page app)
3. Redirect URI: `https://praxia.example.com/api/v1/oauth/microsoft/callback`
4. After creation: API permissions → Microsoft Graph → Delegated → add the scopes above
5. Certificates & secrets → New client secret
6. Set `PRAXIA_OAUTH_MICROSOFT_CLIENT_ID` + `PRAXIA_OAUTH_MICROSOFT_CLIENT_SECRET`
7. (Multi-tenant apps) set `PRAXIA_SSO_TENANT_ID=common`; (single-tenant) use your tenant ID

---

## 3. Dropbox (`dropbox`)

**Default scopes:**
```
files.metadata.read files.content.read files.content.write
```

**Least-privilege alternatives:**
- Read-only: drop `files.content.write`
- Single-folder: use Dropbox **app folder** access type (limited to `/Apps/<your-app>/`)

**App registration:**
1. <https://www.dropbox.com/developers/apps> → Create app
2. Choose **Scoped access** → **App folder** (recommended) or **Full Dropbox**
3. Redirect URI: `https://praxia.example.com/api/v1/oauth/dropbox/callback`
4. Permissions tab → enable the 3 scopes above
5. `PRAXIA_OAUTH_DROPBOX_CLIENT_ID` + `PRAXIA_OAUTH_DROPBOX_CLIENT_SECRET`

---

## 4. Google (`google` — used by Drive, Gmail, future Calendar)

**Default scopes:**
```
https://www.googleapis.com/auth/drive
```

**Add for Gmail backend (Email connector):**
```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

**Add for Calendar (future):**
```
https://www.googleapis.com/auth/calendar.readonly
```

**Least-privilege alternatives:**
- Drive read-only: `https://www.googleapis.com/auth/drive.readonly`
- Drive single file/folder picker: `https://www.googleapis.com/auth/drive.file` (only files the user picks)

**App registration:**
1. <https://console.cloud.google.com/apis/credentials> → Create OAuth client ID → Web app
2. Authorized redirect URI: `https://praxia.example.com/api/v1/oauth/google/callback`
3. OAuth consent screen → publish to "External" or restrict to your Workspace org
4. Set `PRAXIA_OAUTH_GOOGLE_CLIENT_ID` + `PRAXIA_OAUTH_GOOGLE_CLIENT_SECRET`

> Google requires `access_type=offline` + `prompt=consent` to get refresh tokens. Praxia configures these automatically (`extra_authorize_params`).

---

## 5. Salesforce (`salesforce`)

**Default scopes:**
```
api refresh_token offline_access
```

**Add for Marketing Cloud / Pardot / etc.:**
```
chatter_api full
```

**Least-privilege:** the `api` scope alone is enough for SOQL queries + sObject operations. Drop `full` unless you specifically need administrative APIs.

**App registration:**
1. Setup → App Manager → New Connected App
2. Enable OAuth Settings, callback URL: `https://praxia.example.com/api/v1/oauth/salesforce/callback`
3. Selected OAuth Scopes: API access (`api`), perform requests on your behalf at any time (`refresh_token, offline_access`)
4. **Important**: enable PKCE for confidential clients
5. After save, wait ~10 min for propagation
6. `PRAXIA_OAUTH_SALESFORCE_CLIENT_ID` + `PRAXIA_OAUTH_SALESFORCE_CLIENT_SECRET`

---

## 6. Notion (`notion`)

**Default scopes:** None — Notion uses **workspace-level grants**. The user picks which pages/databases the integration can see at install time.

**Per-page restriction:** at OAuth time, the user is prompted to select which pages/databases to grant access to. There is no scope to limit this in code; it's entirely user-controlled.

**App registration:**
1. <https://www.notion.so/my-integrations> → New integration
2. Type: **Public integration** (for OAuth)
3. Redirect URI: `https://praxia.example.com/api/v1/oauth/notion/callback`
4. Capabilities: Read content, Update content, Insert content (toggle as needed)
5. `PRAXIA_OAUTH_NOTION_CLIENT_ID` + `PRAXIA_OAUTH_NOTION_CLIENT_SECRET`

> Notion uses **HTTP Basic auth** at the token endpoint (not bearer). PKCE is **not supported**. Praxia's `OAuthFlow` handles this via `pkce=False` in `NOTION_OAUTH`.

---

## 7. Atlassian (`atlassian` — used by Confluence + Jira)

**Default scopes:**
```
read:confluence-content.summary
read:confluence-content.all
write:confluence-content
read:jira-work
write:jira-work
offline_access
```

**Least-privilege alternatives:**
- Confluence-only, read: drop the four `*jira*` scopes + `write:confluence-content`
- Jira-only, read: drop the four `*confluence*` scopes + `write:jira-work`
- Read-only: drop both `write:*` scopes

**App registration:**
1. <https://developer.atlassian.com/console/myapps/> → Create → OAuth 2.0 (3LO) integration
2. Permissions tab → add Confluence API + Jira API
3. Add the scopes you need from the list above
4. Authorization tab → add callback URL: `https://praxia.example.com/api/v1/oauth/atlassian/callback`
5. Distribution tab → set to "Sharing" (public) when ready
6. `PRAXIA_OAUTH_ATLASSIAN_CLIENT_ID` + `PRAXIA_OAUTH_ATLASSIAN_CLIENT_SECRET`

> The `cloud_id` (or `site_url`) must be passed to the connector at runtime — Atlassian apps can be installed on multiple sites and Praxia needs to know which one.

---

## 8. Slack (`slack`)

**Default scopes (bot):**
```
channels:history channels:read
groups:history groups:read
im:history
files:read files:write
chat:write
users:read
search:read
```

**Least-privilege alternatives:**
- Read-only ingest: drop `chat:write` + `files:write`
- Public-channels-only: drop `groups:*` + `im:history`
- No file uploads: drop `files:write`

**App registration:**
1. <https://api.slack.com/apps> → Create New App → From scratch
2. OAuth & Permissions → Redirect URLs: `https://praxia.example.com/api/v1/oauth/slack/callback`
3. Bot Token Scopes → add the scopes above
4. Install app to workspace
5. `PRAXIA_OAUTH_SLACK_CLIENT_ID` + `PRAXIA_OAUTH_SLACK_CLIENT_SECRET`

> Slack v2 OAuth uses confidential clients (no PKCE). The app issues both a **bot token** (`xoxb-...`) for actions and optionally a **user token** (`xoxp-...`). Praxia uses the bot token by default.

---

## 9. GitHub (`github`)

**Default scopes:**
```
repo read:org read:user
```

**Least-privilege alternatives:**
- Public repos only: `public_repo` instead of `repo`
- No org membership reading: drop `read:org`
- No user info: drop `read:user`

**For fine-grained access, use a GitHub App instead of OAuth App** — that's a separate Praxia connector pattern (planned for v1.2).

**App registration:**
1. <https://github.com/settings/developers> → OAuth Apps → New OAuth App
2. Authorization callback URL: `https://praxia.example.com/api/v1/oauth/github/callback`
3. After creation: Generate a new client secret
4. `PRAXIA_OAUTH_GITHUB_CLIENT_ID` + `PRAXIA_OAUTH_GITHUB_CLIENT_SECRET`

---

## 10. HubSpot (`hubspot`)

**Default scopes:**
```
crm.objects.contacts.read
crm.objects.contacts.write
crm.objects.companies.read
crm.objects.deals.read
crm.objects.deals.write
```

**Add for tickets / engagements:**
```
crm.objects.tickets.read crm.objects.tickets.write
sales-email-read content
```

**Least-privilege:**
- CRM read-only: drop both `*.write` scopes
- No deals: drop `crm.objects.deals.*`

**App registration:**
1. Create a HubSpot Developer account at <https://developers.hubspot.com/>
2. Create a Public App → Auth tab → Redirect URL: `https://praxia.example.com/api/v1/oauth/hubspot/callback`
3. Scopes tab → enable the scopes above
4. `PRAXIA_OAUTH_HUBSPOT_CLIENT_ID` + `PRAXIA_OAUTH_HUBSPOT_CLIENT_SECRET`

---

## 11. Zendesk (`zendesk`)

**Default scopes:**
```
read write
```

**Note:** Zendesk has only two scope levels (`read` / `write`) plus `tickets:read` / `tickets:write` for ticket-only apps. The default covers all object types.

**App registration:**
1. Sign in to your Zendesk account: `<your-subdomain>.zendesk.com/admin`
2. Apps and integrations → APIs → Zendesk API → OAuth Clients → Add OAuth client
3. Redirect URLs: `https://praxia.example.com/api/v1/oauth/zendesk/callback`
4. Save → note the Unique Identifier and copy the secret (shown once)
5. `PRAXIA_OAUTH_ZENDESK_CLIENT_ID` + `PRAXIA_OAUTH_ZENDESK_CLIENT_SECRET`

> Zendesk URLs are **subdomain-specific**. Praxia's `ZENDESK_OAUTH.authorize_url` includes a `{subdomain}` placeholder; the connector / OAuth flow templates this from `PRAXIA_CONN_ZENDESK_SUBDOMAIN` (env or kwarg).

---

## 12. Linear (`linear`)

**Default scopes:**
```
read write
```

**Note:** Linear has 4 scopes: `read`, `write`, `issues:create`, `admin`. The default covers normal workflow needs.

**App registration:**
1. <https://linear.app/settings/api> → OAuth applications → New OAuth application
2. Callback URLs: `https://praxia.example.com/api/v1/oauth/linear/callback`
3. Set permissions: Read + Write (or just Read for ingest-only)
4. `PRAXIA_OAUTH_LINEAR_CLIENT_ID` + `PRAXIA_OAUTH_LINEAR_CLIENT_SECRET`

> Linear also accepts a personal API key without OAuth — pass `api_key=...` to the connector for single-user / scripts.

---

## 13. kintone (`kintone`)

**Default scopes:**
```
k:app_record:read k:app_record:write k:app_settings:read k:file:read k:file:write
```

**Note:** kintone scopes are per-resource: `k:app_record:read|write` for record CRUD, `k:app_settings:read|write` for app schema, `k:file:read|write` for file attachments. Add `k:app_settings:write` only if Praxia needs to modify app forms.

**Per-tenant URL:** kintone OAuth endpoints embed the tenant subdomain. Set `PRAXIA_OAUTH_KINTONE_SUBDOMAIN` to your tenant (e.g. `acme` for `acme.cybozu.com`). The flow then resolves to `https://acme.cybozu.com/oauth2/authorization` and `/token`.

**App registration:**
1. cybozu.com admin → 「cybozu.com 共通管理」→ OAuth クライアント → 「追加する」
2. Redirect URL: `https://praxia.example.com/api/v1/oauth/kintone/callback`
3. Scopes: tick `k:app_record:read`, `k:app_record:write`, `k:app_settings:read`, `k:file:read`, `k:file:write` (uncheck `k:app_settings:write` if Praxia shouldn't modify app schemas).
4. `PRAXIA_OAUTH_KINTONE_CLIENT_ID` + `PRAXIA_OAUTH_KINTONE_CLIENT_SECRET` + `PRAXIA_OAUTH_KINTONE_SUBDOMAIN`

> kintone also accepts a static `X-Cybozu-API-Token` (per-app, not per-user) or HTTP Basic auth (`username`+`password`). For new deployments, prefer OAuth so each Praxia user only sees records kintone grants to their own account.

---

## Customizing scopes per deployment

If you want different scopes than the defaults (e.g., read-only build of Praxia for a specific tenant), override at construction time:

```python
from praxia.connectors.oauth import OAuthFlow, BOX_OAUTH

# Custom: read-only Box
flow = OAuthFlow(
    BOX_OAUTH,
    client_id=...,
    client_secret=...,
    redirect_uri=...,
)
url, state = flow.authorization_url(
    user_id="alice",
    scopes=["root_readonly"],   # overrides BOX_OAUTH.default_scopes
)
```

The HTTP `/api/v1/oauth/{provider}/start` endpoint currently uses the default scopes. To customize per request, fork the endpoint or add `scope_override` query param support — happy to accept a PR.

---

## Verifying granted scopes

After authorization, you can inspect what the user actually granted:

```python
from praxia.connectors.oauth import OAuthTokenStore

store = OAuthTokenStore()
token = store.get("alice", "slack")
print(token.scope)         # space-separated string of granted scopes
print(token.extra)         # raw token-endpoint response (provider-specific extras)
```

For audit purposes, every successful OAuth exchange writes `oauth.complete` to the audit log with the provider name + user id (but **not** the scopes — that's the token-store's job).

---

## Security considerations

- **Always start from least privilege.** Add scopes incrementally as needed.
- **Tokens are envelope-encrypted at rest** via the configured KMS adapter — see [`docs/legal/GDPR_NOTES.md`](legal/GDPR_NOTES.md) and [`SECURITY.md`](../SECURITY.md).
- **Per-user OAuth means each Praxia user authorizes their own tokens.** A compromised admin account does not give attackers access to user-stored tokens directly (they would still need the KMS key + user_id mapping).
- **Rotate client secrets quarterly.** All Praxia provider configs read `client_secret` from env — rotation requires no code change.
- **Revocation:** call `praxia oauth revoke <provider> --user-id <id>` (CLI) or `DELETE /api/v1/oauth/{provider}` (HTTP). Some providers also auto-revoke after long inactivity.
