# Praxia 機能仕様書

> ステータス: **v1.0** · 最終更新: 2026-05 · 日本語版 (English version follows when requested)
> 関連文書: [基本設計](basic-design.ja.md) · [I/F 仕様](interface-spec.ja.md) · [詳細設計](detailed-design.ja.md)

---

## 0. 本書について

### 0.1 目的

Praxia v1.0 が提供する **全機能** の動作仕様を網羅的に記述します。基本設計書が「なぜ・なにを」を記述するのに対し、本書は「**どのように使うか・どのように振る舞うか**」に焦点を当てます。

### 0.2 対象読者

- **採用検討中の意思決定者** — 機能ギャップ評価
- **導入担当者 (情報システム部)** — 認証認可・監査・運用設定の確認
- **エンドユーザ (現場担当者)** — 各機能の使い方
- **拡張開発者** — 拡張ポイントの仕様
- **監査担当者** — コンプライアンス確認

### 0.3 本書の構成

| 章 | 内容 |
|---|---|
| 1 | システム全体像 |
| 2-3 | 認証 / 認可 |
| 4-6 | ユーザ管理 / 監査 / データフロー |
| 7-10 | メモリ / プロンプト / スキル / フロー |
| 11-13 | LLM / 連携 / I/O |
| 14-17 | 音声 / ダッシュボード / CLI / UI / HTTP |
| 18-20 | 設定 / デプロイ / 拡張性 |
| 21-22 | 法的配慮 / 用語集 |

---

## 1. システム全体像

### 1.1 機能カタログ

Praxia v1.0 が提供する機能は以下の 9 カテゴリに分類されます。

| カテゴリ | 機能 |
|---|---|
| **A. オーケストレーション** | マルチエージェントフロー / 単一スキル実行 / メモリ循環 |
| **B. メモリ** | 5 層スタック / 6 LTM バックエンド / 複数 LTM 同時利用 / モード切替 / 管理者ポリシー |
| **C. スキル** | 6 業務ドメイン / 出力形式判定 / レジストリ / 昇格 / 配信 |
| **D. LLM** | 5+ プロバイダ + 100+ via LiteLLM / Gemma 対応 / auto_detect |
| **E. 認証認可** | API キー / JWT / OIDC SSO 5 種 / 4 ロール RBAC / リソース ACL / 監査ログ |
| **F. 連携** | 6 ストレージ/SaaS / ユーザ委譲 OAuth |
| **G. I/O** | ファイルパーサ 13 拡張子 / 出力エクスポータ 5 形式 / 音声 STT+TTS |
| **H. 運用** | ダッシュボード / 管理者エクスポート / 設定統合 |
| **I. デプロイ** | フルスタック / SDK 埋込 / HTTP サーバ |

### 1.2 利用形態

```
┌──────────────────────────────────────────────────────┐
│  操作インターフェース                                │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐   │
│  │  CLI   │  │ Streamlit│ │   SDK   │ │ HTTP API │   │
│  │(typer) │  │   UI     │ │(Python) │ │(FastAPI) │   │
│  └───┬────┘  └────┬─────┘ └────┬────┘ └────┬─────┘   │
└──────┼────────────┼────────────┼───────────┼─────────┘
       └────────────┴────────────┴───────────┘
                        │
                        ▼
            ┌────────────────────┐
            │  Praxia オーケストレータ │
            └────────────────────┘
```

**4 つの操作インターフェース全てが同一のコアロジックを共有** — 認証認可・監査・メモリ・スキル動作はインターフェースに依存せず一貫します。

### 1.3 主要データフロー (概観)

```
[ユーザ操作]
    │
    ▼
[認証] ─── 失敗 → 401
    │
    ▼
[認可 (RBAC + ACL)] ─── 拒否 → 403 + 監査記録
    │
    ▼
[メモリ設定解決] ── admin policy + user pref
    │
    ▼
[スキル / フロー実行]
    │
    ├─ LLM 呼出
    ├─ メモリ検索 (関連コンテキスト)
    └─ メモリ記録 (mode=accumulate のみ)
    │
    ▼
[出力エクスポート] ── 任意形式 (md/html/pptx/docx/json)
    │
    ▼
[監査ログ記録] (append-only)
    │
    ▼
[結果返却]
```

---

## 2. 認証 (Authentication)

### 2.1 認証経路の全体像

Praxia は **3 つの認証経路** を提供。すべて `AuthManager.authenticate()` に集約。

| 経路 | 用途 | 実装 | 必要設定 |
|---|---|---|---|
| **API キー** | CLI / プログラム的アクセス | bcrypt ハッシュ照合 | `praxia user create` で発行 |
| **JWT** | UI / HTTP セッション | HS256 署名 | `PRAXIA_JWT_SECRET` |
| **OIDC SSO** | エンタープライズ統合 | authorization_code flow | `PRAXIA_SSO_*` 各種 |

### 2.2 API キー認証

#### 2.2.1 発行

```bash
praxia user create alice --role member --email alice@example.com
# 出力例:
# ✅ User created: alice (member)
# 🔑 API Key: praxia_aBc123xYz... (このキーは1回のみ表示されます)
```

**特性:**
- ランダム 32 byte → URL-safe base64 → `praxia_` プレフィックス
- 平文は **発行時のみ** 表示。サーバ側は `bcrypt` ハッシュ (`api_key_hash`) のみ保管
- 再表示は不可 — 紛失時は `praxia user rotate-key` で再発行

#### 2.2.2 利用

```python
# SDK
from praxia.auth import AuthManager
auth = AuthManager()
user = auth.authenticate(api_key="praxia_aBc123xYz...")
if user is None:
    raise PermissionError("invalid API key")
```

```bash
# HTTP
curl -H "X-API-Key: praxia_aBc123xYz..." https://praxia.example/api/v1/me
```

```bash
# Streamlit UI: ログイン画面で入力
```

#### 2.2.3 ローテーション

```bash
praxia user rotate-key alice
# 旧キーは即時無効化、新キーが発行される
```

監査ログに `user.rotate_key` イベント記録。旧キーで認証試行すると 401 + `auth.fail` 監査。

#### 2.2.4 失効

```bash
praxia user deactivate alice    # 一時無効化 (再有効化可能)
praxia user delete alice        # 完全削除 (不可逆)
```

### 2.3 JWT 認証

#### 2.3.1 発行

```python
auth = AuthManager()
user = auth.authenticate(api_key="praxia_...")
token = auth.issue_token(user.id, ttl_seconds=3600)
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

ペイロード構造:
```json
{
  "sub": "user_id",
  "username": "alice",
  "role": "member",
  "iat": 1714945200,
  "exp": 1714948800,
  "iss": "praxia"
}
```

#### 2.3.2 検証

```python
user = auth.authenticate(token="eyJhbGciOiJIUzI1NiIs...")
# 失敗ケース:
#   - 署名不正 → None
#   - exp 期限切れ → None
#   - sub に該当ユーザなし → None
#   - is_active=False → None
```

#### 2.3.3 設定

| 設定 | 用途 | 既定値 |
|---|---|---|
| `PRAXIA_JWT_SECRET` | HS256 署名鍵 | (必須・無設定時はランダム生成 → 再起動で全 token 失効) |
| `PRAXIA_JWT_TTL` | デフォルト TTL (秒) | 3600 |
| `PRAXIA_JWT_ISSUER` | iss クレーム | `praxia` |

**本番運用時の必須要件:**
- `PRAXIA_JWT_SECRET` を 32 byte 以上のランダム文字列で固定
- ステートレスホスト間で共有

### 2.4 SSO (OIDC)

#### 2.4.1 対応プロバイダ

| プロバイダ | provider 値 | 必要追加設定 |
|---|---|---|
| Google Workspace | `google` | (なし) |
| Microsoft Entra ID | `microsoft` | `PRAXIA_SSO_TENANT_ID` |
| Okta | `okta` | `PRAXIA_SSO_OKTA_DOMAIN` |
| GitHub | `github` | (なし — Org 制限は別途) |
| Keycloak | `keycloak` | `PRAXIA_SSO_KEYCLOAK_BASE_URL` + `PRAXIA_SSO_KEYCLOAK_REALM` |
| 汎用 OIDC | `custom_oidc` | `PRAXIA_SSO_ISSUER_URL` |

#### 2.4.2 共通フロー (PKCE 付き Authorization Code)

```
[Browser]    [Praxia]      [IdP]
    │           │           │
    │ GET /auth/login
    ├──────────►│           │
    │           │ generate state + code_verifier (PKCE)
    │           │ store {state: code_verifier} in cache
    │           │
    │ 302 redirect IdP authorize URL
    │◄──────────┤           │
    │  with state, code_challenge, scope=openid email profile
    │           │           │
    │           │           │
    ├──────────────────────►│
    │           │           │ login + consent
    │ 302 redirect to callback?code=...&state=...
    │◄──────────────────────┤
    │           │           │
    │ GET /auth/callback?code=...&state=...
    ├──────────►│           │
    │           │ verify state matches stored entry
    │           │           │
    │           │ POST /token (code, code_verifier, client_id, client_secret)
    │           ├──────────►│
    │           │ id_token (JWT) + access_token
    │           │◄──────────┤
    │           │
    │           │ verify id_token signature (JWKS)
    │           │ extract email, sub, name
    │           │
    │           │ lookup or auto-provision User by email
    │           │ issue Praxia JWT for that user
    │           │
    │ 302 redirect to home + Set-Cookie: praxia_session
    │◄──────────┤
```

#### 2.4.3 自動プロビジョニング

初回 SSO ログイン時、`SSOLoginHandler.on_first_login()` が呼ばれます:

| 条件 | 挙動 |
|---|---|
| 既存ユーザ (email 一致) あり | 既存ユーザに紐付け、ロール変更なし |
| 該当ユーザなし & 自動プロビ有効 | `Role.MEMBER` で新規作成 |
| 該当ユーザなし & 自動プロビ無効 | 401 + 監査ログ `auth.sso.unprovisioned` |

設定:
```bash
praxia config set PRAXIA_SSO_AUTO_PROVISION true
```

#### 2.4.4 設定例 (Google Workspace)

```bash
# .env
PRAXIA_SSO_PROVIDER=google
PRAXIA_SSO_CLIENT_ID=your-client-id.apps.googleusercontent.com
PRAXIA_SSO_CLIENT_SECRET=GOCSPX-xxxxxxxxxx
PRAXIA_SSO_REDIRECT_URI=https://praxia.example.com/auth/callback
PRAXIA_SSO_AUTO_PROVISION=true
```

Google Cloud Console での OAuth クライアント設定:
- Authorized redirect URIs: `https://praxia.example.com/auth/callback`
- Authorized JavaScript origins: `https://praxia.example.com`
- Required scopes: `openid email profile`

#### 2.4.5 設定例 (Microsoft Entra ID)

```bash
PRAXIA_SSO_PROVIDER=microsoft
PRAXIA_SSO_CLIENT_ID=00000000-0000-0000-0000-000000000000
PRAXIA_SSO_CLIENT_SECRET=secret~value
PRAXIA_SSO_TENANT_ID=00000000-0000-0000-0000-000000000000
PRAXIA_SSO_REDIRECT_URI=https://praxia.example.com/auth/callback
```

Entra ID app 登録:
- Platform: Web
- Redirect URI: `https://praxia.example.com/auth/callback`
- API permissions: `openid`, `profile`, `email`

#### 2.4.6 設定例 (Keycloak)

```bash
PRAXIA_SSO_PROVIDER=keycloak
PRAXIA_SSO_CLIENT_ID=praxia
PRAXIA_SSO_CLIENT_SECRET=...
PRAXIA_SSO_KEYCLOAK_BASE_URL=https://kc.example.com
PRAXIA_SSO_KEYCLOAK_REALM=corp
PRAXIA_SSO_REDIRECT_URI=https://praxia.example.com/auth/callback
```

Keycloak 側設定:
- Client → Settings: Client authentication ON, Standard flow ON
- Valid redirect URIs: `https://praxia.example.com/auth/callback`

### 2.5 認証エラーパターン

| パターン | HTTP 応答 | 監査記録 |
|---|---|---|
| API キー不一致 | 401 | `auth.fail` (api_key) |
| JWT 期限切れ | 401 | `auth.fail` (jwt_expired) |
| JWT 署名不正 | 401 | `auth.fail` (jwt_invalid) |
| SSO state 不一致 | 401 | `auth.sso.state_mismatch` |
| SSO IdP がエラー | 502 | `auth.sso.idp_error` |
| ユーザ無効化済 | 401 | `auth.fail` (deactivated) |

---

## 3. 認可 (Authorization)

### 3.1 認可の 2 段階モデル

```
[ユーザ操作]
   │
   ├── ① RBAC チェック (action ベース)
   │   └─ AuthManager.authorize(user, action, resource)
   │      └─ ロール × アクション 表で許可判定
   │
   └── ② リソース ACL チェック (resource ベース)
       └─ PolicyManager.evaluate(user_id, role, resource_type, resource_id, action)
          └─ glob パターンマッチ + deny 優先
```

両方クリアして初めて操作実行。どちらか拒否で 403 + 監査記録。

### 3.2 RBAC モデル

#### 3.2.1 ロール定義

| ロール | 既定権限 | 想定 |
|---|---|---|
| **admin** | 全権限 | 情報システム部 / プラットフォーム管理者 |
| **operator** | 業務 + 一部管理 | チームリーダー |
| **member** | 業務 (フロー / スキル / メモリ書込) | 一般エンドユーザ |
| **viewer** | 業務 (read-only) | 監査者 / 期間限定ユーザ |

#### 3.2.2 アクション一覧

| アクション | admin | operator | member | viewer |
|---|---|---|---|---|
| `run_flows` | ✅ | ✅ | ✅ | ✅ |
| `run_skills` | ✅ | ✅ | ✅ | ✅ |
| `read_personal_memory` | ✅ | ✅ | ✅ | ✅ |
| `write_personal_memory` | ✅ | ✅ | ✅ | ❌ |
| `read_shared_memory` | ✅ | ✅ | ✅ | ✅ |
| `write_shared_memory` | ✅ | ✅ | ❌ | ❌ |
| `freeze_blocks` | ✅ | ✅ | ❌ | ❌ |
| `consolidate` | ✅ | ✅ | ❌ | ❌ |
| `promote_skills` | ✅ | ✅ | ❌ | ❌ |
| `distribute_prompts` | ✅ | ✅ | ❌ | ❌ |
| `manage_users` | ✅ | ❌ | ❌ | ❌ |
| `manage_policies` | ✅ | ❌ | ❌ | ❌ |
| `export_data` | ✅ | ❌ | ❌ | ❌ |
| `manage_memory_policy` | ✅ | ❌ | ❌ | ❌ |
| `connector_pull` | ✅ | ✅ | ✅ | ✅ |
| `connector_push` | ✅ | ✅ | ✅ | ❌ |
| `oauth_authorize` | ✅ | ✅ | ✅ | ❌ |

#### 3.2.3 ロール変更

```bash
praxia user grant alice operator    # ロール昇格
```

監査ログ: `user.role_grant` で旧ロール / 新ロールを記録。

### 3.3 リソース ACL (PolicyManager)

#### 3.3.1 ポリシー構造

```python
@dataclass
class Policy:
    id: str                   # auto-generated
    effect: "allow" | "deny"
    resource_type: str        # "connector" | "memory" | "prompt" | "skill" | "block" | "*"
    resource_pattern: str     # glob — "box:/Confidential/*"
    actions: list[str]        # ["read", "write"]
    principals: list[str]     # ["role:member", "user:alice"]
    description: str
    created_at: float
    created_by: str
```

#### 3.3.2 評価アルゴリズム

```python
def evaluate(user_id, role, resource_type, resource_id, action) -> Decision:
    matches = []
    for p in self.policies:
        if p.resource_type not in (resource_type, "*"):
            continue
        if not fnmatch(resource_id, p.resource_pattern):
            continue
        if action not in p.actions:
            continue
        # principal フィルタ
        if not any(
            pr == f"user:{user_id}" or pr == f"role:{role}"
            for pr in p.principals
        ):
            continue
        matches.append(p)

    # deny 優先
    if any(p.effect == "deny" for p in matches):
        return Decision(allowed=False, matched=...)
    if any(p.effect == "allow" for p in matches):
        return Decision(allowed=True, matched=...)
    # マッチなし → 既定値
    return Decision(allowed=self.default_decision == "allow", matched=None)
```

#### 3.3.3 ポリシー追加例

```bash
# 例 1: 機密フォルダは operator+ のみアクセス可
praxia policy add deny connector "box:/Confidential/*" \
    --principals "role:member,role:viewer" \
    --actions read,write \
    --description "機密フォルダは operator 以上のみ"

# 例 2: 特定ユーザに特別権限
praxia policy add allow memory "memory:user/charlie/*" \
    --principals "user:charlie,role:admin" \
    --actions read,write \
    --description "Charlie は他ユーザのメモリを参照可"

# 例 3: 全 viewer の書込を deny
praxia policy add deny "*" "*" \
    --principals "role:viewer" \
    --actions write \
    --description "viewer は全リソース書込不可"
```

#### 3.3.4 ポリシーテスト

```bash
praxia policy test alice member connector box:/Confidential/q3.pdf read
# 出力例:
# ❌ DENIED by policy abc123 (deny: 機密フォルダは operator 以上のみ)
```

#### 3.3.5 評価対象リソースタイプ

| resource_type | resource_id 例 | 評価ポイント |
|---|---|---|
| `connector` | `box:0/foo` `salesforce:Lead` | pull/push 前 |
| `memory` | `memory:user/alice/*` `memory:org/*` | 検索/記録前 |
| `prompt` | `prompt:org/qualifier` | 配信/参照前 |
| `skill` | `skill:investment_analyst` | 実行/promote 前 |
| `block` | `block:team_norms` | 共有メモリ操作前 |
| `*` | (任意) | 全タイプにマッチ |

### 3.4 認可エラー時の挙動

```python
# SDK
try:
    auth.require(user, "manage_users")
except PermissionError as e:
    print(f"Denied: {e}")
    # 監査ログに既に "auth.deny" が記録されている
```

```bash
# CLI
$ praxia user create bob --role admin
✗ Permission denied: action=manage_users requires admin role
```

```http
# HTTP API
POST /api/v1/users
HTTP/1.1 403 Forbidden
{"detail": "Permission denied: action=manage_users"}
```

---

## 4. ユーザ管理

### 4.1 User データモデル

```python
@dataclass
class User:
    id: str                  # uuid4
    username: str            # 一意
    email: str | None
    role: str                # admin | operator | member | viewer
    is_active: bool          # 無効化フラグ
    created_at: float
    last_login_at: float | None
    api_key_hash: str        # bcrypt
    sso_subject: str | None  # SSO 経由の場合の sub クレーム
    metadata: dict
```

`api_key_hash` `password_hash` は admin export 時にも除外される (チェーン・オブ・カストディ保持)。

### 4.2 操作と監査

| 操作 | コマンド | 監査アクション |
|---|---|---|
| 作成 | `praxia user create` | `user.create` |
| 一覧 | `praxia user list` | (記録対象外) |
| 編集 | `praxia user update` | `user.update` |
| ロール変更 | `praxia user grant` | `user.role_grant` |
| キーローテ | `praxia user rotate-key` | `user.rotate_key` |
| 無効化 | `praxia user deactivate` | `user.deactivate` |
| 削除 | `praxia user delete` | `user.delete` |
| 監査閲覧 | `praxia user audit` | (記録対象外 — 閲覧自体) |

### 4.3 bootstrap admin

初回 `praxia init` 実行時に admin ユーザが自動作成され、API キーが `.praxia/auth/BOOTSTRAP_API_KEY.txt` に**1回だけ**書き出されます (読み取り後ファイル削除推奨)。

```bash
praxia init --user-id bootstrap_admin
cat .praxia/auth/BOOTSTRAP_API_KEY.txt
# praxia_AbcDef123...
rm .praxia/auth/BOOTSTRAP_API_KEY.txt   # 安全のため即削除
```

このキーで他ユーザを作成 → 通常運用へ。

### 4.4 UI 経由のユーザ管理

Streamlit UI **⚙ Admin → 👥 Users サブタブ** (admin ロールのみアクセス可):

- ユーザリスト (検索・並び替え)
- 新規作成ダイアログ (role / email 指定)
- 編集・削除・無効化ボタン
- API キーローテートボタン (新キーをワンタイム表示)
- 各ユーザの最終ログイン時刻

> Admin ビューは role-aware ナビゲーションで admin / unknown (= 単一ユーザ
> 開発モード) ロールでのみ top-bar に表示される。ユーザ未登録の状態では
> "single-user dev mode" の警告バナーを表示し、認証なしの操作を許容
> しつつ運用者にアラートを出す。

---

## 5. 監査ログ (Audit Log)

### 5.1 形式

`.praxia/auth/audit/audit.jsonl` への append-only JSONL。

```jsonl
{"id": "uuid", "timestamp": 1714945200.123, "actor_id": "alice_id", "actor_username": "alice", "action": "user.create", "resource": "user:bob", "success": true, "metadata": {"role": "member", "email": "bob@example.com"}}
```

#### 5.1.1 フィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | str | レコード一意 ID (uuid4) |
| `timestamp` | float | UNIX 時刻 (秒, 小数有り) |
| `actor_id` | str | 操作実行ユーザの ID |
| `actor_username` | str | 同 username (補助) |
| `action` | str | 動詞.名詞 形式 (`user.create`) |
| `resource` | str \| null | 対象リソース (`user:bob`) |
| `success` | bool | 操作成功可否 |
| `metadata` | dict | 任意の追加情報 |

### 5.2 記録対象アクション全リスト

| アクション | 発生箇所 | 主な metadata |
|---|---|---|
| `auth.success` | API キー / JWT 認証成功 | `method` |
| `auth.fail` | 認証失敗 | `method`, `reason` |
| `auth.sso.start` | SSO 開始 | `provider` |
| `auth.sso.complete` | SSO コールバック成功 | `provider`, `email` |
| `auth.sso.fail` | SSO 失敗 | `provider`, `reason` |
| `auth.deny` | RBAC 拒否 | `action`, `resource` |
| `policy.deny` | ACL deny | `policy_id`, `resource_type`, `resource_id` |
| `policy.allow` | ACL allow (明示マッチのみ) | `policy_id`, `resource_type`, `resource_id` |
| `user.create` | ユーザ作成 | `role`, `email` |
| `user.update` | ユーザ編集 | 変更フィールド |
| `user.role_grant` | ロール変更 | `old_role`, `new_role` |
| `user.rotate_key` | API キー再発行 | (なし) |
| `user.deactivate` | ユーザ無効化 | (なし) |
| `user.delete` | ユーザ削除 | (なし) |
| `policy.add` | ACL ポリシー追加 | `effect`, `resource_pattern` |
| `policy.remove` | ACL ポリシー削除 | `policy_id` |
| `flow.run` | フロー実行 | `flow_name`, `inputs_hash` |
| `skill.run` | スキル実行 | `skill_name` |
| `skill.promote` | 個人 → 組織昇格 | `skill_name`, `verdict_score` |
| `skill.distribute` | 配信 | `skill_name`, `target_roles` |
| `prompt.create` | プロンプト作成 | `name`, `scope` |
| `prompt.distribute` | 配信 | `name`, `target_roles` |
| `memory.consolidate` | バッチ統合 | `auto_promoted`, `review_queued` |
| `memory.freeze` | 凍結 | `block_label`, `path` |
| `memory.policy_set` | 管理者ポリシー変更 | 変更フィールド |
| `memory.mode_change` | ユーザモード変更 | `user_id`, `old_mode`, `new_mode` |
| `connector.pull` | Pull 実行 | `connector`, `path`, `item_count` |
| `connector.push` | Push 実行 | `connector`, `path` |
| `oauth.start` | OAuth 開始 | `provider` |
| `oauth.complete` | トークン取得成功 | `provider` |
| `oauth.fail` | OAuth 失敗 | `provider`, `reason` |
| `oauth.revoke` | トークン削除 | `provider` |
| `export.audit` | 監査ログエクスポート | `format`, `since`, `actor_filter` |
| `export.users` | ユーザエクスポート | `format` |
| `export.memory` | メモリエクスポート | `target_user`, `format` |
| `export.policies` | ポリシーエクスポート | `format` |
| `export.shared_memory` | 共有メモリエクスポート | `format` |

### 5.3 エクスポート

```bash
# CSV (SIEM 連携想定)
praxia admin export-audit audit.csv --format csv --since-days 30

# JSON (バックアップ用)
praxia admin export-audit audit.json --format json

# 特定ユーザの操作のみ
praxia admin export-audit alice.csv --actor alice --since-days 90
```

エクスポート操作自体も `export.audit` で監査記録される (chain-of-custody)。

### 5.4 改ざん防止

`AuditLog.write()` は:
1. 既存ファイルへの append のみ (truncate / overwrite なし)
2. 各書込で `fsync()` (クラッシュ耐性)
3. ファイル権限を 0600 に維持 (admin 以外読み取り不可)

ハッシュチェーン化 / 外部 SIEM への即時転送は v1.0 では未対応 (Phase 6 で計画)。

---

## 6. データフロー

### 6.1 フロー実行のシーケンス

```
[Caller]
   │
   ├─ Praxia.run_flow("sales_agent_flow", inputs={...})
   │
   ▼
[認証]
   │ AuthManager.authenticate(api_key | token)
   │   └─ 失敗時 PermissionError
   ▼
[RBAC 認可]
   │ AuthManager.authorize(user, "run_flows")
   │   └─ 拒否時 PermissionError + auth.deny 監査
   ▼
[メモリ設定解決]
   │ resolve_memory_config(user_id, user_role)
   │   └─ admin policy ∪ user pref → ResolvedMemoryConfig
   ▼
[PersonalMemory 生成]
   │ PersonalMemory(backend=cfg.backend, mode=cfg.mode)
   ▼
[フロー実行]
   │ flow.run(inputs)
   │   └─ for step in flow.steps:
   │        │
   │        ├─ ACL チェック (resource アクセス想定なら)
   │        │
   │        ├─ コンテキスト検索
   │        │   └─ pm.search(query, limit=5)
   │        │      └─ backend.search()
   │        │
   │        ├─ LLM 呼出
   │        │   └─ litellm.completion(messages, ...)
   │        │
   │        └─ 中間結果保存
   ▼
[エピソード記録]
   │ if cfg.mode == "accumulate":
   │   pm.record_episode(flow_name, inputs, output)
   │     └─ backend.add()
   │ else:  # read_only
   │   no-op (drop)
   ▼
[監査記録]
   │ audit.write("flow.run", success=True, metadata=...)
   ▼
[FlowResult 返却]
```

### 6.2 メモリ検索のシーケンス (Composite + Routed)

#### 6.2.1 単一バックエンド

```
pm.search(query, limit=5)
  → backend.search(user_id, query, limit)
  → list[MemoryRecord]
```

#### 6.2.2 CompositeBackend (融合)

```
pm.search(query, limit=5)
  → CompositeBackend.search()
      │
      ├─ ThreadPoolExecutor で N バックエンド並列実行
      │   ├─ thread 1: backend_A.search()
      │   ├─ thread 2: backend_B.search()
      │   └─ thread 3: backend_C.search()
      │   (1 個失敗しても継続、空結果として扱う)
      │
      ├─ 結果集約: per_backend = {"A": [...], "B": [...], "C": [...]}
      │
      ├─ 融合戦略適用 (rrf / union / intersection / weighted / llm_rerank)
      │   └─ RRF 例: score(d) = Σ_b weight_b / (k + rank_b(d))
      │
      └─ ソート + limit カット → list[MemoryRecord]
```

#### 6.2.3 RoutedBackend (動的選択)

```
pm.search(query, limit=5)
  → RoutedBackend.search()
      │
      ├─ Router.route(query, available_backends)
      │   └─ RouteDecision(backends=[...], fusion="rrf", reason="...")
      │
      ├─ if len(decision.backends) == 1:
      │     └─ 直接呼出 (Composite オーバヘッドなし)
      │ else:
      │     └─ CompositeBackend を on-the-fly 構築 → search
      │
      └─ list[MemoryRecord]
```

### 6.3 メモリ書込のシーケンス

```
pm.record_episode(flow_name, inputs, output)
  │
  ├─ if self._mode == "read_only":
  │     return MemoryEntry(metadata={"read_only_dropped": True})
  │     # 永続化なし
  │
  ├─ text を整形: "[flow_name] inputs=... output=..."
  │
  ├─ backend.add(user_id, text, kind="episode", metadata)
  │   │
  │   ├─ JsonBackend → JSONL 追記
  │   ├─ Mem0Backend → mem0.add() → 内部で entity 抽出 + vector 化
  │   ├─ ZepBackend → graphiti.add_episode() → KG ノード生成
  │   └─ ...
  │
  └─ MemoryEntry 返却
```

### 6.4 メモリ統合 (Sleep-time Consolidation)

```
praxia consolidate
  │
  ▼
SleepTimeConsolidator.run()
  │
  ├─ 全ユーザの個人メモリを集約
  │   for user in all_users:
  │       entries.extend(user.personal_memory.all_entries())
  │
  ├─ 候補クラスタリング
  │   _cluster_candidates(entries) → list[Cluster]
  │
  └─ for cluster in clusters:
        verdict = PromotionEngine.evaluate(cluster)
          │
          ├─ ① 頻度スコア (unique_users / total_users)
          ├─ ② 成果スコア (相関 outcome.success と pattern)
          └─ ③ 自己評価 (LLM judge: "is this org-knowledge?")
        │
        ├─ if verdict.score >= auto_threshold (0.75):
        │     └─ shared_memory.upsert(label, value)
        │     └─ audit: skill.promote / memory.consolidate
        │
        ├─ elif verdict.score >= review_threshold (0.5):
        │     └─ review queue に追加 (UI で人手承認待ち)
        │
        └─ else:
              └─ 棄却 (PII 検出時を含む)
```

---

## 7. メモリ機能

### 7.1 5 層スタック詳細

#### 7.1.1 Layer 1: Personal Memory

| 操作 | API | 内部動作 |
|---|---|---|
| episode 記録 | `pm.record_episode(flow_name, inputs, output)` | JSON 整形 → `backend.add(kind="episode")` |
| fact 記録 | `pm.record_fact(text)` | `backend.add(kind="fact")` |
| preference 記録 | `pm.record_preference(text)` | `backend.add(kind="preference")` |
| outcome 記録 | `pm.record_outcome(episode_id, success, score, notes)` | `backend.add(kind="outcome", metadata={episode_id, ...})` |
| 検索 | `pm.search(query, limit=5)` | `backend.search()` |
| 全件 | `pm.all_entries()` | `backend.all()` |
| クリア | `pm.clear()` | `backend.clear(user_id)` |
| outcome 紐付け取得 | `pm.outcomes_for(episode_id)` | metadata フィルタ |

**namespace**: `user_id` で完全分離 (他ユーザの書込は他ユーザの検索に含まれない)。

#### 7.1.2 Layer 2: Sleep-time Consolidation

実行頻度の推奨: **夜間 1 回 (cron / GitHub Actions / Kubernetes CronJob)**

```bash
# 夜間バッチで実行
0 2 * * * praxia consolidate --threshold 0.75
```

**事前確認 (dry-run):**
```bash
praxia consolidate --dry-run
# 出力:
# Would auto-promote: 3 clusters
# Would queue for review: 5 clusters
# Would skip: 12 clusters (low confidence)
```

#### 7.1.3 Layer 3: Shared Memory

組織共通の "ライブ" 知識ベース:

```python
from praxia import SharedMemory
sm = SharedMemory(org_id="acme")

# 作成 / 更新
sm.upsert(label="manufacturing_pain_hypotheses",
          description="製造業向け課題抽出テンプレート",
          value="...",
          read_only=False)

# 読込
block = sm.get_by_label("manufacturing_pain_hypotheses")
print(block.value)

# 一覧
for b in sm.list():
    print(b.label, b.read_only)
```

`read_only=True` のブロックは consolidator からの自動更新を受け付けません (人手キュレーション専用)。

#### 7.1.4 Layer 4: Frozen Markdown

```bash
# 共有ブロックを git 管理 Markdown へ凍結
praxia freeze --block manufacturing_pain_hypotheses

# 出力例:
# ✅ Frozen → .praxia/frozen/instructions/manufacturing_pain_hypotheses.md
```

ファイル形式 (Claude Skills / Cursor Rules / Copilot Instructions 互換):
```markdown
---
title: manufacturing_pain_hypotheses
description: 製造業向け課題抽出テンプレート
tags: [frozen, auto-promoted]
frozen_at: 2026-05-05T12:00:00
---

(本文)
```

#### 7.1.5 Layer 5: Graph Layer (任意)

関係性が業務価値の中核な領域 (決定履歴 / 顧客 360 / 障害因果) で `zep` バックエンドを利用:

```python
PersonalMemory(user_id="alice", backend="zep",
               api_url="https://zep.example",
               api_key="...")
```

時系列クエリ (`先月の Acme との会話を追って`) で KG が活きます。

### 7.2 6 LTM バックエンド比較

| バックエンド | 自動抽出 | ベクトル検索 | エンティティ連結 | 関係性 | 推奨用途 |
|---|---|---|---|---|---|
| **json** | ❌ | BM25 風 | ❌ | ❌ | 開発 / SMB / 監査ログ的 |
| **mem0** | ✅ | ✅ ハイブリッド | ✅ | ❌ (2026-04 廃止) | 本番推奨 |
| **langmem** | ✅ | ✅ | ✅ | ❌ | LangChain 既存 |
| **letta** | ✅ | ✅ | ❌ | ❌ | Letta 共有ブロック |
| **zep** | ✅ | ✅ | ✅ | ✅ 時系列 KG | Layer 5 関係性領域 |
| **hindsight** | ✅ | ✅ | ❌ | ❌ | vectorize-io インテグ |

### 7.3 複数 LTM 同時利用

#### 7.3.1 CompositeBackend — 5 融合戦略

```python
from praxia.memory.composite import CompositeBackend, WeightedBackend
from praxia.memory.backends import load_backend

composite = CompositeBackend(
    backends=[
        WeightedBackend("mem0", load_backend("mem0"), weight=1.5),
        WeightedBackend("zep", load_backend("zep"), weight=1.0),
        WeightedBackend("hindsight", load_backend("hindsight"), weight=1.0),
        WeightedBackend("json", load_backend("json"), weight=0.5),
    ],
    fusion="rrf",       # rrf | union | intersection | weighted | llm_rerank
    write_to="mem0",    # 書込先 (指定なしは backends[0])
    rrf_k=60,           # RRF 定数
    min_agreement=2,    # intersection 用
    max_workers=6,      # 並列スレッド数
)
PersonalMemory(user_id="alice", backend=composite)
```

| 戦略 | 動作 | 向いているケース |
|---|---|---|
| `rrf` | RRF スコアで再ランク (k=60 既定) | 既定 / 堅実なベースライン |
| `union` | 重複除去のみ、最初出現順 | 再現率最大化 |
| `intersection` | N 個以上に登場した結果のみ | 適合率最大化 |
| `weighted` | 正規化ランクを重み合算 | 重み手動調整したい場合 |
| `llm_rerank` | LLM-as-judge | 最高精度 / 最遅 |

#### 7.3.2 RoutedBackend — 動的ルーティング

```python
from praxia.memory.router import RoutedBackend, RuleRouter, LLMRouter

# A. ルールベース (高速・決定論的)
routed = RoutedBackend(
    backends={
        "mem0": load_backend("mem0"),
        "zep": load_backend("zep"),
        "hindsight": load_backend("hindsight"),
        "json": load_backend("json"),
    },
    router=RuleRouter(),  # 既定ルール 4 種 + フォールバック
    write_to="mem0",
)

# B. LLM ベース (高精度・1 LLM 呼出コスト)
routed_llm = RoutedBackend(
    backends={...},
    router=LLMRouter(llm=praxia.llm),
    write_to="mem0",
)
```

`RuleRouter` の既定ルール (順序通り):

| ルール | 正規表現 | バックエンド優先順 |
|---|---|---|
| 監査 | `audit\|changelog\|history\|履歴\|変更履歴\|監査` | `[json, mem0]` |
| 時系列 | `last week\|since\|先月\|昨日\|過去\|時系列` | `[zep, mem0, hindsight]` |
| エンティティ | `who\|what is\|tell me about\|誰\|について` | `[mem0, hindsight, json]` |
| 類似 | `similar\|like\|same as\|類似\|似た` | `[hindsight, mem0, letta]` |
| (フォールバック) | (なし) | `[mem0, hindsight, json]` |

カスタムルール:
```python
import re
custom_rules = [
    (re.compile(r"\b(financial|決算|EPS)\b"), ["zep", "mem0"], "財務系 → 時系列 KG"),
    *RuleRouter.DEFAULT_RULES,
]
RuleRouter(rules=custom_rules)
```

### 7.4 メモリモード (accumulate / read_only)

#### 7.4.1 ユーザ毎切替

```bash
praxia memory mode --user-id alice read_only
# alice の record_episode / record_fact / record_outcome / record_preference は no-op
# search / all_entries は通常動作

praxia memory mode --user-id alice accumulate
# 通常動作に戻す

praxia memory show --user-id alice
# 解決済み設定を表示 (理由付き)
```

#### 7.4.2 read_only モードの内部挙動

```python
def record_fact(self, text, *, metadata=None):
    if self._mode == "read_only":
        # ダミーのエントリを返却 (永続化なし)
        return MemoryEntry(
            id=f"readonly:fact",
            text="",
            kind="fact",
            metadata={"read_only_dropped": True},
            ...
        )
    # accumulate 時の通常処理
    ...
```

呼出側は戻り値の `metadata["read_only_dropped"]` で判別可能。

#### 7.4.3 用途

- 法務文書レビュー (機微情報をメモリ化したくない)
- 社外ゲスト用ユーザ
- 診断 / トラブルシュート用の使い捨てセッション
- A/B テスト中の対照群

### 7.5 管理者ポリシー

#### 7.5.1 ポリシーフィールド

```python
@dataclass
class MemoryAdminPolicy:
    # --- バックエンド戦略 ---
    backend_strategy: Literal["single", "composite", "routed"] = "single"
    backend: str = "json"                     # 'single' で使う backend

    # 'composite' モード (CompositeBackend)
    composite_backends: list[str] = []        # 例: ["mem0", "zep"]
    composite_fusion: Literal["rrf", "union", "intersection",
                              "weighted", "llm_rerank"] = "rrf"
    composite_write_to: str = ""

    # 'routed' モード (RoutedBackend)
    routed_backends: list[str] = []
    routed_router: Literal["rule", "llm"] = "rule"
    routed_write_to: str = ""

    # --- 蓄積モード ---
    default_mode: Literal["accumulate", "read_only"] = "accumulate"

    # --- レガシー (旧 policy.json 互換のため残置、UI では非表示) ---
    enforced_backend: str | None = None
    default_backend: str = "json"
    allowed_backends: list[str] = []
    mode_locked: bool = False
    accumulate_locked_to: list[str] = []
```

ユーザ毎の `MemoryUserPreference` の UI 経路は廃止 — admin policy
が単一の真実。policy は `.praxia/admin/memory_policy.json` に永続化、
旧 `enforced_backend` / `default_backend` は `__post_init__` が
`backend` フィールドへ自動移行する。

#### 7.5.2 設定例

```bash
# 例 1: 全社 mem0 固定
praxia admin memory-policy-set \
    --strategy single --backend mem0 \
    --default-mode accumulate

# 例 2: composite — Mem0 + Zep の並列検索 + RRF 融合、書込は Mem0
praxia admin memory-policy-set \
    --strategy composite \
    --composite-backends mem0,zep \
    --composite-fusion rrf \
    --composite-write-to mem0

# 例 3: routed — クエリ内容で動的選択 (時系列 → Zep, エンティティ → Mem0+HindSight)
praxia admin memory-policy-set \
    --strategy routed \
    --routed-backends mem0,zep,hindsight,json \
    --routed-router rule \
    --routed-write-to mem0

# 例 4: 監査要件 — 全ユーザ accumulate 固定
praxia admin memory-policy-set \
    --default-mode accumulate
```

#### 7.5.3 解決ロジック (再掲)

```
backend 解決:
  admin.enforced_backend > 呼出時引数 > user_pref > admin.default_backend > "json"

mode 解決:
  admin.mode_locked       → admin.default_mode (lock)
  user_role ∈ accumulate_locked_to → "accumulate" (lock)
  呼出時引数              → 引数値
  user_pref.mode          → user_pref
  default                 → admin.default_mode
```

`praxia memory show --user-id alice --role member` で結果と理由を確認可能:

```
Memory config for alice:
  backend       : mem0
  mode          : accumulate
  locked_by_admin: True
  reason        : admin enforced backend=mem0 | role member locked to accumulate
```

---

## 8. プロンプト管理

### 8.1 3 スコープモデル

```
[個人プロンプト]      ─── ユーザが自身用に保存
       │
       │ (ユーザの promote 操作 + admin 承認)
       ▼
[組織プロンプト]      ─── 全社で共有 (read-only)
       │
       │ (admin が distribute)
       ▼
[配信プロンプト]      ─── 特定ロール / ユーザに push
```

### 8.2 マージ優先順位

`PromptStore.list_for_user(user_id, role)` の結果は:

```
個人プロンプト   >   配信プロンプト   >   組織プロンプト
(personal)         (distributed)         (org)
```

同名プロンプトは**スコープが上位のもの 1 つのみ**返却 (個人 > 配信 > 組織)。

### 8.3 操作

```bash
# 個人プロンプト保存
praxia prompt create my_qualifier prompt_body.txt
# .praxia/prompts/personal/<user_id>.json に追加

# 一覧 (3 スコープのマージ結果)
praxia prompt list

# 個人 → 組織昇格 (admin/operator のみ)
praxia prompt promote my_qualifier
# 承認後、組織プロンプトに移動

# 配信 (admin/operator のみ)
praxia prompt distribute curated_qualifier body.md \
    --target-roles member,operator
# .praxia/prompts/distributed.json に追加

# 削除
praxia prompt delete --user-id alice --name my_qualifier
```

### 8.4 利用

```python
from praxia.skills.prompts import PromptStore

store = PromptStore()
prompts = store.list_for_user(user_id="alice", role="member")
for p in prompts:
    print(p.name, p.scope, p.body[:50])
```

UI **📝 Prompts** ビューで GUI 操作可能。3 サブタブ構成:

- **✨ Generate** — `PromptDesignerSkill` をラップ。1 行のタスク記述から system プロンプト + `${variable}` 入り user テンプレ + Few-Shot 例 + 5 観点ルーブリックを生成、保存可能
- **📚 Browse & edit** — 自分の personal scope のプロンプトを CRUD、org / distributed scope は read-only 表示
- **📤 Distribute** — admin role 限定。特定ユーザ / ロールへ配信

---

## 9. スキル (Skills)

### 9.1 スキル構成

```python
class Skill:
    manifest: SkillManifest        # 必須
    system_prompt: str = ""        # 必須
    tools: list[Callable] = []     # 任意
    reference_files: list[Path] = []  # 任意

@dataclass
class SkillManifest:
    name: str           # 一意
    description: str    # 1 行
    version: str = "0.1.0"
    domain: str         # "investment" | "sales" | ... | "utility"
    tags: list[str] = []
    author: str | None = None
```

### 9.2 6 業務スキルの詳細

#### 9.2.1 InvestmentSkill (投資判断)

| 項目 | 内容 |
|---|---|
| `name` | `investment_analyst` |
| `domain` | `investment` |
| **フレームワーク** | 5 セクション (Profile / Quant / Qual / Risk / Decision) |
| **想定用途** | 株式調査、デューデリジェンス、ポートフォリオ判断 |
| **ガードレール** | 「最終判断は投資家自身」明記 / 個別銘柄推奨はテンプレートとして fictional |
| **入出力例** | 入: "中堅電機メーカーの 3 年中期投資判断" / 出: 5 セクション分析メモ |

```bash
praxia skill run investment "中堅電機 (架空) の中期投資判断、ESG リスク重視"
```

#### 9.2.2 SalesSkill (営業)

| 項目 | 内容 |
|---|---|
| `name` | `sales_strategist` |
| `domain` | `sales` |
| **フレームワーク** | 仮説 → FAQ → 提案概要 |
| **想定用途** | 商談前リサーチ、提案ストーリーボード、想定 Q&A |
| **ガードレール** | 顧客実名利用時は社内承認確認を促す |

#### 9.2.3 DesignSkill (設計レビュー)

| 項目 | 内容 |
|---|---|
| `name` | `design_reviewer` |
| `domain` | `design` |
| **フレームワーク** | DRAGON (Data flow / Requirements / Architectural fit / Gaps / Operation / NFRs) |
| **想定用途** | 仕様書レビュー、要件定義の網羅性チェック |

#### 9.2.4 PurchasingSkill (購買)

| 項目 | 内容 |
|---|---|
| `name` | `purchasing_analyst` |
| `domain` | `purchasing` |
| **フレームワーク** | QCD+S (Quality / Cost / Delivery / Sustainability) + TCO |
| **想定用途** | サプライヤ評価、RFQ 比較、BCP リスク分析 |
| **ガードレール** | 下請法 / 独占禁止法の注意喚起内蔵 |

#### 9.2.5 PatentSkill (特許)

| 項目 | 内容 |
|---|---|
| `name` | `patent_researcher` |
| `domain` | `patent` |
| **フレームワーク** | 5 ステップ (要素分解 → IPC/FI/F-term 検索式 → ヒット分析 → 新規性 → 進歩性) |
| **想定用途** | 先行技術調査、クレーム作成支援、特許マップ |
| **ガードレール** | 「最終判断は弁理士に」明記 |

#### 9.2.6 LegalSkill (法務)

| 項目 | 内容 |
|---|---|
| `name` | `legal_reviewer` |
| `domain` | `legal` |
| **フレームワーク** | RACE (Risk / Allocation / Compliance / Exit) + 🔴/🟡/🟢 |
| **想定用途** | 契約レビュー、コンプライアンスチェック、M&A デューデリ |
| **ガードレール** | 「弁護士の確認を」明記、特定法域限定の注意 |

### 9.3 OutputFormatSkill (utility)

ユーザの自然言語ヒントから出力形式を判定し、適切なエクスポータでレンダリング。

```python
from praxia.skills.output_format import OutputFormatSkill

fs = OutputFormatSkill()

# パターン A: ヒント → 形式判定のみ
req = fs.detect("レポートをパワポで")
# req.format == "pptx", req.confidence == 0.85, req.reason == "PowerPoint / slide-deck request"

# パターン B: deliver で完結 (judge + render)
result = fs.deliver(
    md_content,
    user_request="このレポートをパワポで",
    title="Q3 レビュー",
)
# result.bytes → write_bytes() / HTTP body / connector push
```

#### 9.3.1 検出キーワード一覧

| 形式 | キーワード (英語) | キーワード (日本語) |
|---|---|---|
| `pptx` | pptx, powerpoint, slides, deck | スライド, パワポ, プレゼン |
| `docx` | docx, word, document, doc | ワード, 文書, ドキュメント |
| `html` | html, web | ブラウザ |
| `json` | json, api | (なし) |
| `md` | md, markdown | マークダウン |
| `pdf` | pdf | (なし) |

検出失敗時は既定 `md` (Markdown) を返却。

#### 9.3.2 LLM 判定モード

```python
req = fs.detect_with_llm("いつもの形式で出力して")
# 高信頼の正規表現マッチがあればそれを返却
# なければ LLM に問い合わせ → "md" 等を抽出
```

### 9.4 スキル昇格 (個人 → 組織)

#### 9.4.1 経路

ユーザが繰り返し使った personal scope のスキルを `SkillRegistry.promote()` が判定 → 組織 scope へ。

```bash
# 候補一覧
praxia skill promote --candidates
# [
#   {"name": "my_qualifier", "score": 0.82, "verdict": "auto"},
#   {"name": "ad_hoc_helper", "score": 0.61, "verdict": "review"},
# ]

# 昇格実行
praxia skill promote my_qualifier
```

#### 9.4.2 配信

```bash
praxia skill distribute investment_analyst --target-roles member,operator
# member, operator に対して investment_analyst が必ず list_for_user に含まれる
```

### 9.5 スキルの利用パターン

| パターン | API |
|---|---|
| 単一実行 | `skill.run("...")` |
| Agent 化 (フロー組込) | `skill.as_agent()` |
| Claude Skills 形式エクスポート | `skill.to_skill_md()` |
| LLM 切替 | `Skill(llm=LLM("gemini-flash"))` |

### 9.6 カスタムスキル開発

```python
# my_pkg/hr_recruiting.py
from praxia.skills.skill import Skill, SkillManifest

class HRRecruitingSkill(Skill):
    manifest = SkillManifest(
        name="hr_recruiting",
        description="履歴書スクリーニング + 面接質問生成",
        domain="hr",
        tags=["recruiting", "screening"],
    )
    system_prompt = """\
あなたは熟練のリクルーターです。
入力された履歴書 / 職務経歴書に対し:
1. 求めるスキルとの適合度をスコアリング (0-10)
2. 深堀り質問 5 つを生成
3. 懸念点 / 追加確認事項を 3 つ列挙
"""
```

```toml
# pyproject.toml
[project.entry-points."praxia.skills"]
hr_recruiting = "my_pkg.hr_recruiting:HRRecruitingSkill"
```

`pip install my_pkg` で自動検出 → `praxia skill run hr_recruiting "..."` で利用可能。

---

## 10. フロー (Multi-Agent Flows)

### 10.1 SalesAgentFlow

| ステップ | エージェント役割 | 出力 |
|---|---|---|
| 1. `gather_context` | RAG: IR / 過去議事録から検索 | コンテキスト要約 |
| 2. `hypothesize_pains` | 仮説生成 | 上位 3 課題仮説 |
| 3. `generate_faq` | 想定 Q&A 5 行 | FAQ + 引用元 |
| 4. `draft_proposal` | 提案概要 | 提案ストーリー |

```bash
praxia run sales --customer-name "Acme" --product "BizFlow" \
    --additional-context "中期計画で 30 億円の DX 投資を予定"
```

### 10.2 LogicCheckerFlow

3 エージェント並列レビュー:

| エージェント | 観点 |
|---|---|
| `structure_reviewer` | 章立て・段落構成・接続詞 |
| `contradiction_detector` | 主張の矛盾・前提崩れ |
| `reader_simulator` | 想定読者目線で疑問点を列挙 |

```bash
praxia run logic --document spec.md
# .pdf / .docx / .pptx / .xlsx 自動パース対応
```

### 10.3 RAGOptimizationFlow

自己修復ループ:

```
[クエリ拡張] → [検索] → [関連性評価] → [ハルシネーション検査]
                          │                     │
                  関連性低い → 拡張やり直し  hallucination 検出 → 再検索
                          │                     │
                          └─── 合格 → 最終回答
```

```bash
praxia run rag --question "Praxia のライセンスは何ですか?"
```

### 10.4 カスタムフロー開発

```python
from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM

class IncidentResponseFlow(Flow):
    name = "incident_response"
    description = "On-call SRE incident triage + RCA + mitigation"

    def __init__(self, llm: LLM | None = None):
        llm = llm or LLM()
        self.steps = [
            FlowStep("triage", Agent(name="triage", llm=llm,
                     system_prompt="あなたは SRE トリアージです..."),
                     inputs={"alert": "${input.alert_text}"}),
            FlowStep("hypothesis", Agent(name="hypothesis", llm=llm,
                     system_prompt="トリアージ結果から原因仮説を 3 つ..."),
                     inputs={"triage_result": "${triage.output}"}),
            FlowStep("mitigation", Agent(name="mitigation", llm=llm,
                     system_prompt="緩和策を即時 / 短期 / 恒久に分けて提案..."),
                     inputs={"hypotheses": "${hypothesis.output}"}),
        ]
```

エントリポイント:
```toml
[project.entry-points."praxia.flows"]
incident_response = "my_pkg.flows:IncidentResponseFlow"
```

---

## 11. LLM プロバイダ

### 11.1 全エイリアス一覧

| エイリアス | LiteLLM 解決 | 認証 | 推奨用途 |
|---|---|---|---|
| `claude` | `anthropic/claude-opus-4-7` | `ANTHROPIC_API_KEY` | 推論・長文 |
| `claude-sonnet` | `anthropic/claude-sonnet-4-6` | 同上 | バランス型 |
| `claude-haiku` | `anthropic/claude-haiku-4-5-20251001` | 同上 | 高速 |
| `chatgpt` | `openai/gpt-4o` | `OPENAI_API_KEY` | ツール利用幅広 |
| `gpt-4o` | `openai/gpt-4o` | 同上 | 同上 |
| `o1` | `openai/o1` | 同上 | 高度推論 |
| `gemini` | `gemini/gemini-2.0-pro` | `GEMINI_API_KEY` | 長コンテキスト |
| `gemini-flash` | `gemini/gemini-2.0-flash` | 同上 | 高速 |
| `qwen` | `dashscope/qwen-max` | `DASHSCOPE_API_KEY` | コスト / 中国語 |
| `qwen-72b` | `dashscope/qwen2.5-72b-instruct` | 同上 | 同上 |
| `qwen-local` | `ollama/qwen2.5:14b` | (なし) | オンプレ |
| **`gemma`** | `ollama/gemma2:9b` | (なし) | オンプレ既定 |
| **`gemma-2b`** | `ollama/gemma2:2b` | (なし) | エッジ / 開発 |
| **`gemma-9b`** | `ollama/gemma2:9b` | (なし) | バランス型 |
| **`gemma-27b`** | `ollama/gemma2:27b` | (なし) | 最大ローカル |
| **`gemma-cloud`** | `vertex_ai/google/gemma-2-27b-it` | Vertex AI 認証 | クラウド Gemma |

任意のフルパス (`provider/model`) は LiteLLM が直接解釈。

### 11.2 auto_detect ロジック

```python
@staticmethod
def auto_detect() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):  return "claude"
    if os.getenv("OPENAI_API_KEY"):     return "chatgpt"
    if os.getenv("GEMINI_API_KEY"):     return "gemini"
    if os.getenv("DASHSCOPE_API_KEY"):  return "qwen"
    # 全部不在 → ローカル候補
    local = os.getenv("PRAXIA_LOCAL_MODEL", "qwen-local")
    return local if local in DEFAULT_ALIASES else "qwen-local"
```

`PRAXIA_LOCAL_MODEL=gemma` を設定すれば、クラウドキー不在時に Gemma にフォールバックします。

### 11.3 オフライン運用パターン

```bash
# Ollama に Gemma をダウンロード
ollama pull gemma2:9b

# Praxia 設定: ローカル Gemma + JSON memory
export PRAXIA_LOCAL_MODEL=gemma
export PRAXIA_MEMORY_BACKEND=json

# 完全オフラインで動作
praxia run sales --customer-name "Acme" --product "BizFlow"
```

---

## 12. 外部連携 (Connectors)

### 12.1 6 既定コネクタ

| コネクタ | name | Pull (path 形式) | Push (path 形式) |
|---|---|---|---|
| Box | `box` | フォルダ ID (例: `0`) | アップロード先フォルダ ID |
| SharePoint / OneDrive | `sharepoint` | site/drive/folder | 同上 |
| Dropbox | `dropbox` | パス (`/foo/bar`) | パス |
| Google Drive | `gdrive` | 親フォルダ ID | 親フォルダ ID |
| kintone | `kintone` | アプリ ID + クエリ (`42?status='open'`) | アプリ ID (record 作成) |
| Salesforce | `salesforce` | SOQL (`SELECT Id, Name FROM Account`) | sObject 名 + payload JSON |

### 12.2 認証経路

| 経路 | 用途 | 設定 |
|---|---|---|
| **per-user OAuth** (推奨) | ユーザ毎に外部 ACL を尊重 | `PRAXIA_OAUTH_<PROVIDER>_*` + `praxia oauth start` |
| **共有資格情報** | サービスアカウント運用 | `PRAXIA_CONN_<NAME>_*` |
| **API トークン** | kintone 等 OAuth 不在 | `PRAXIA_CONN_KINTONE_API_TOKEN` |

### 12.3 ユーザ委譲 OAuth フロー

```bash
# 1. 一度だけ: OAuth アプリの client_id / client_secret を設定
praxia config set PRAXIA_OAUTH_BOX_CLIENT_ID "..."
praxia config set PRAXIA_OAUTH_BOX_CLIENT_SECRET "..."

# 2. ユーザ毎: 認可
praxia oauth start box --user-id alice
# → 認可 URL が表示される
# → ブラウザで開く → Box にログイン → 同意
# → リダイレクト URL (callback) で code を受け取る
# → トークン取得 → 暗号化保存 (.praxia/oauth/alice/box.json)

# 3. 以降のコネクタ呼出: alice のトークンで認証
praxia connector pull box 0 --user-id alice --limit 20
# alice が見える Box フォルダのみ取得 (Box ACL 適用)
```

### 12.4 PKCE フロー詳細

```
[CLI/UI]              [Praxia OAuthFlow]              [Provider]
   │                         │                            │
   │ oauth start box         │                            │
   ├────────────────────────►│                            │
   │                         │ generate code_verifier     │
   │                         │ code_challenge = SHA256(verifier)
   │                         │ state = secrets.token_urlsafe(32)
   │                         │ store {state: verifier, user_id} in memory cache
   │                         │
   │ authorize URL           │                            │
   │◄────────────────────────┤                            │
   │  https://account.box.com/api/oauth2/authorize?
   │  response_type=code&client_id=...&redirect_uri=...
   │  &state=<state>&code_challenge=<challenge>
   │  &code_challenge_method=S256&scope=root_readwrite
   │                         │                            │
   │ (browser opens URL)     │                            │
   │                         │                            │
   ├──────────────────────────────────────────────────────►│
   │                         │                            │ login + consent
   │                         │                            │
   │◄──────────────────────────────────────────────────────┤
   │ callback?code=<code>&state=<state>
   │                         │                            │
   │ exchange_code(code, state)                           │
   ├────────────────────────►│                            │
   │                         │ verify state matches cache │
   │                         │ POST /token with code +    │
   │                         │   code_verifier            │
   │                         ├──────────────────────────►│
   │                         │ {access_token, refresh_token, expires_in}
   │                         │◄──────────────────────────┤
   │                         │                            │
   │                         │ encrypt + save token       │
   │                         │ (.praxia/oauth/alice/box.json)
   │                         │                            │
   │ ✅ saved                │                            │
   │◄────────────────────────┤                            │
```

### 12.5 トークン暗号化

`OAuthTokenStore` は `PRAXIA_TOKEN_ENC_KEY` から導出した対称鍵で AES-GCM 暗号化:

```
[平文トークン]
   ├─ derived_key = HKDF(PRAXIA_TOKEN_ENC_KEY, salt="", info=user_id+provider)
   ├─ nonce = secrets.token_bytes(12)
   ├─ ciphertext = AES-GCM(derived_key, nonce, plaintext)
   └─ ファイル形式: {"nonce": base64, "ciphertext": base64, "expires_at": ...}
```

ファイル権限 0600 + ユーザディレクトリ分離 (`.praxia/oauth/<user_id>/<provider>.json`)。

### 12.6 トークンリフレッシュ

```python
def get(self, user_id, provider) -> OAuthToken | None:
    token = self._load(user_id, provider)
    if token and token.is_expired() and token.refresh_token:
        # リフレッシュ
        new_token = self._refresh(token)
        self.save(new_token)
        return new_token
    return token
```

リフレッシュ失敗時は `None` 返却 → コネクタ初期化で `PermissionError("re-authorize")` 発生。

---

## 13. ファイル I/O

### 13.1 入力 (パーサ) — 13 拡張子

| 拡張子 | パーサ | 任意依存 |
|---|---|---|
| `.txt`, `.md`, `.markdown`, `.rst`, `.py`, `.ts`, `.js` 等 | `TextParser` | なし |
| `.csv`, `.tsv` | `CsvParser` | なし (stdlib) |
| `.json`, `.yaml`, `.yml`, `.xml` | `StructuredParser` | (PyYAML for yaml) |
| `.html`, `.htm` | `HtmlParser` | なし (stdlib) |
| `.pdf` | `PdfParser` | `pypdf` (`praxia[office]`) |
| `.docx` | `DocxParser` | `python-docx` (`praxia[office]`) |
| `.pptx` | `PptxParser` | `python-pptx` (`praxia[office]`) |
| `.xlsx`, `.xlsm` | `XlsxParser` | `openpyxl` (`praxia[office]`) |

```python
from praxia.io.parsers import parse_file

# 拡張子から自動ディスパッチ
doc = parse_file(file_bytes, filename="contract.pdf")
# doc.content: str (LLM 投入可能なテキスト)
# doc.metadata: dict (ページ数 / シート数 / 著者 等)
```

#### 13.1.1 各パーサの特徴

| パーサ | 特徴 |
|---|---|
| `TextParser` | UTF-8 → Shift-JIS → CP1252 → latin-1 自動フォールバック |
| `CsvParser` | 出力は Markdown table (LLM 可読性最大化) |
| `StructuredParser` | JSON / YAML を pretty-print、`is_valid` メタデータ |
| `HtmlParser` | script / style を除去、title 抽出 |
| `PdfParser` | ページ毎にテキスト抽出、ページ番号メタデータ付与 |
| `DocxParser` | 見出しレベル保持、Markdown 風変換 |
| `PptxParser` | スライド毎タイトル + 本文 + speaker notes |
| `XlsxParser` | シート毎 Markdown table 化 |

### 13.2 出力 (エクスポータ) — 5 形式

| 形式 | エクスポータ | 任意依存 |
|---|---|---|
| `md`, `markdown` | `MarkdownExporter` | なし (passthrough + frontmatter) |
| `html` | `HtmlExporter` | なし (組込 MD → HTML レンダラ) |
| `pptx` | `PptxExporter` | `python-pptx` (`praxia[office]`) |
| `docx` | `DocxExporter` | `python-docx` (`praxia[office]`) |
| `json` | `JsonExporter` | なし |

#### 13.2.1 各エクスポータの引数

| エクスポータ | コンストラクタ kwargs |
|---|---|
| `MarkdownExporter` | `title`, `author`, `frontmatter` |
| `HtmlExporter` | `title`, `css`, `wrap_in_document`, `lang` |
| `PptxExporter` | `title`, `subtitle`, `author` |
| `DocxExporter` | `title`, `author` |
| `JsonExporter` | `indent`, `ensure_ascii` |

#### 13.2.2 PPTX 自動セグメンテーション

```markdown
# ドキュメントタイトル        ← タイトルスライドになる
## セクション 1               ← 新規スライド
- bullet
- bullet
## セクション 2               ← 新規スライド
- bullet
```

`# Heading` がドキュメントタイトル → タイトルスライド + 各 `## Heading` がコンテンツスライド。

#### 13.2.3 HTML エクスポータの内蔵 CSS

`wrap_in_document=True` (既定) で:
- フォント: -apple-system / Segoe UI / system-ui
- 最大幅 760px、中央寄せ
- コードブロック: 背景灰色 + 等幅フォント
- リンク: `#0066cc`
- カスタム CSS は `css=...` で差し替え可能

### 13.3 カスタムパーサ / エクスポータ

```python
# パーサ
from praxia.io.parsers import PARSERS
@PARSERS.register_decorator("rtf")
class RtfParser:
    extensions = ("rtf",)
    def parse(self, content: bytes, *, filename: str) -> ParsedFile: ...

# エクスポータ
from praxia.io.exporters import EXPORTERS
@EXPORTERS.register_decorator("latex")
class LatexExporter:
    format = "latex"
    extensions = ("tex",)
    def export(self, content) -> bytes: ...
```

または entry-point:
```toml
[project.entry-points."praxia.parsers"]
rtf = "my_pkg.rtf_parser:RtfParser"

[project.entry-points."praxia.exporters"]
latex = "my_pkg.latex_exporter:LatexExporter"
```

---

## 14. 音声 I/O

### 14.1 STT (音声 → テキスト)

```python
from praxia.io.audio import STT

stt = STT(provider="openai")  # "openai" | "openai-local"
text = stt.transcribe(audio_bytes, filename="meeting.wav", language="ja")
```

| プロバイダ | エンジン | 必要 |
|---|---|---|
| `openai` | OpenAI Whisper API | `OPENAI_API_KEY` |
| `openai-local` | ローカル Whisper | `praxia[audio-local]` (whisper-cpp) |

対応ファイル形式: wav, mp3, m4a, ogg, webm。

### 14.2 TTS (テキスト → 音声)

```python
from praxia.io.audio import TTS

tts = TTS(provider="openai")  # "openai" | "elevenlabs" | "piper-local"
audio = tts.synthesize("こんにちは", voice="alloy", format="mp3")
# audio: bytes
```

| プロバイダ | エンジン | 必要 |
|---|---|---|
| `openai` | OpenAI TTS | `OPENAI_API_KEY` |
| `elevenlabs` | ElevenLabs (高品質) | `ELEVENLABS_API_KEY` (`praxia[audio]`) |
| `piper-local` | Piper (ローカル) | `praxia[audio-local]` |

OpenAI 音声: alloy / echo / fable / onyx / nova / shimmer。

### 14.3 UI 統合

Streamlit UI **🎬 Run Flow** / **🛠 Skill** タブ:
- **🎙 Audio input** トグル → 録音 → STT 自動変換 → 入力欄に挿入
- **🔊 Read response aloud** トグル → 出力結果を TTS 再生

---

## 15. ダッシュボード

### 15.1 個人ダッシュボード

```python
from praxia.analytics import Dashboard
d = Dashboard(memory_dir=".praxia")
ps = d.personal_summary("alice")
```

| メトリクス | 説明 |
|---|---|
| `flow_runs` | 実行されたフロー数 |
| `skill_runs` | 実行されたスキル数 |
| `memory_entries` | 個人メモリエントリ数 |
| `outcomes_recorded` | outcome 記録数 |
| `success_rate` | success=True の比率 |
| `total_input_tokens` | 累積入力トークン |
| `total_output_tokens` | 累積出力トークン |
| `top_skills` | 利用頻度上位スキル |
| `recent_episodes` | 最近のエピソード (5 件) |

### 15.2 組織ダッシュボード

```python
os = d.org_summary()
```

| メトリクス | 説明 |
|---|---|
| `active_users` | 過去 30 日間にアクティブだったユーザ数 |
| `total_flow_runs` | 全フロー実行数 |
| `org_success_rate` | 全 outcome の成功率 |
| `promoted_blocks` | 共有メモリブロック数 |
| `frozen_files` | 凍結 Markdown 数 |
| `distributed_skills` | 配信済みスキル数 |
| `distributed_prompts` | 配信済みプロンプト数 |
| `top_users` | 利用頻度上位ユーザ |
| `top_skills` | 全社利用頻度上位スキル |

### 15.3 UI 表示

**📊 Dashboard** タブで両方を切替表示。Plotly チャート + Rich Table 形式。

---

## 16. CLI コマンドリファレンス (網羅版)

### 16.1 ライフサイクル系

| コマンド | 概要 |
|---|---|
| `praxia init [--user-id ID] [--backend B] [--model M]` | 初期化、bootstrap admin 作成 |
| `praxia run sales --customer-name N --product P [--additional-context C]` | SalesAgentFlow 実行 |
| `praxia run logic --document FILE` | LogicCheckerFlow 実行 |
| `praxia run rag --question Q` | RAGOptimizationFlow 実行 |
| `praxia consolidate [--threshold 0.75] [--dry-run]` | sleep-time 統合 |
| `praxia freeze --block LABEL` | 共有 → Markdown 凍結 |
| `praxia ui [--port 8501]` | Streamlit UI 起動 |
| `praxia serve [--host] [--port] [--cors-origin]` | FastAPI HTTP 起動 |

### 16.2 検索 / 一覧

| コマンド | 概要 |
|---|---|
| `praxia list flows\|skills\|models\|backends` | リソース一覧 |
| `praxia connector list` | コネクタ一覧 |
| `praxia config show\|path\|init` | 設定表示 / 解決順 / 対話設定 |
| `praxia config get KEY` | 単一キー取得 |
| `praxia config set KEY VALUE` | 永続化 |

### 16.3 スキル / フロー

| コマンド | 概要 |
|---|---|
| `praxia skill run <name> "<input>"` | 単発実行 |
| `praxia skill promote <name>` | 個人 → 組織昇格 |
| `praxia skill distribute <name> --target-roles ...` | ロール配信 |

### 16.4 ユーザ管理

| コマンド | 概要 |
|---|---|
| `praxia user create <name> --role ROLE [--email]` | 作成 |
| `praxia user list` | 一覧 |
| `praxia user grant <name> ROLE` | ロール変更 |
| `praxia user update <name> [--email] [--role]` | フィールド更新 |
| `praxia user deactivate <name>` | 無効化 |
| `praxia user delete <name>` | 削除 |
| `praxia user rotate-key <name>` | API キー再発行 |
| `praxia user audit [--limit N]` | 監査ログ閲覧 |

### 16.5 プロンプト

| コマンド | 概要 |
|---|---|
| `praxia prompt create --user-id --name --body` | 個人作成 |
| `praxia prompt list [--scope] [--user-id]` | 一覧 |
| `praxia prompt promote <name>` | 個人 → 組織昇格 |
| `praxia prompt distribute --name --target-roles` | 配信 |
| `praxia prompt delete --user-id --name` | 削除 |

### 16.6 コネクタ

| コマンド | 概要 |
|---|---|
| `praxia connector pull <name> <path> [--user-id] [--limit] [--save-to DIR]` | Pull |
| `praxia connector push <name> <path> --content-file FILE [--user-id]` | Push |

### 16.7 OAuth (ユーザ委譲)

| コマンド | 概要 |
|---|---|
| `praxia oauth start <provider> --user-id ID` | 認可開始 |
| `praxia oauth list --user-id ID` | 保有トークン一覧 |
| `praxia oauth revoke <provider> --user-id ID` | トークン削除 |

### 16.8 ポリシー (ACL)

| コマンド | 概要 |
|---|---|
| `praxia policy add ALLOW\|DENY RES_TYPE PATTERN --principals ... --description ...` | 追加 |
| `praxia policy list` | 一覧 |
| `praxia policy remove POLICY_ID` | 削除 |
| `praxia policy test USER ROLE RES_TYPE RES_ID ACTION` | 評価 |

### 16.9 メモリポリシー (新規)

| コマンド | 概要 |
|---|---|
| `praxia memory mode --user-id ID accumulate\|read_only` | ユーザモード切替 |
| `praxia memory backend --user-id ID BACKEND` | バックエンド希望設定 |
| `praxia memory show --user-id ID [--role]` | 解決済み設定表示 |
| `praxia admin memory-policy-show` | 管理者ポリシー表示 |
| `praxia admin memory-policy-set [...]` | 管理者ポリシー更新 |

### 16.10 エクスポート (admin)

| コマンド | 概要 |
|---|---|
| `praxia admin export-audit OUT --format csv\|json\|jsonl --since-days N` | 監査ログ |
| `praxia admin export-users OUT --format json\|csv` | ユーザ一覧 |
| `praxia admin export-memory DIR --user-id USER\|--all` | 個人メモリ |
| `praxia admin export-policies OUT --format json\|csv` | ACL ポリシー |
| `praxia admin export-shared-memory OUT --format jsonl\|json` | 共有メモリ |

### 16.11 出力エクスポータ

| コマンド | 概要 |
|---|---|
| `praxia export <input.md> <output.html\|.pptx\|.docx\|.json> [--format] [--title]` | 形式変換 |

---

## 17. UI (Streamlit) リファレンス

### 17.1 ログイン

```
ユーザ未登録 (auth.users.list_all() が空) ──→ 単一ユーザ開発モード
                                              User ID 入力のみ → "unknown" role 付与
ユーザ登録済                              ──→ User ID + Password (= API キー)
                                              auth.authenticate(api_key=...) で識別
                                              失敗 → サインイン拒否
```

> Streamlit UI は **信頼環境向け設計**。インターネット公開のマルチユーザ
> 運用では `praxia serve` (FastAPI + OIDC SSO) を併用。

ユーザ毎の永続設定 (言語・カラーテーマ・LLM 嗜好) は
`.praxia/preferences/<user_id>.json` に保存。サインイン時に
`session_state` へ復元。

### 17.2 レイアウト

3 ゾーン構成:

```
┌─ 固定 top-bar (sticky) ─────────────────────────────────────┐
│ [🎬 Run] [📝 Prompts] [📁 Data] [🧠 Knowledge] [📊 Dashboard] │
│                  [👤 Preferences] [⚙ Admin]*                 │   * admin/unknown のみ
├─ Sidebar ──────┬─ Main workspace ─────────────────────────┤
│ 🪡 Praxia       │                                          │
│ 👤 alice        │                                          │
│ [Sign out]      │   選択された view のワークスペース        │
│ ─────           │                                          │
│ 📁 Context      │                                          │
│  built-in 3 種  │                                          │
│  + tree of      │                                          │
│  local folders  │                                          │
│  + connector    │                                          │
│   folders       │                                          │
└─────────────────┴──────────────────────────────────────────┘
```

サイドバーは **Context picker 専用** — 個人/組織/凍結の built-in
スコープ + 多層ローカルフォルダ (parent_id で tree 構造) +
コネクタフォルダ (Box / SharePoint / Notion 等の登録パス) を
チェックボックス選択。Run 実行時に「読める範囲で grep フィルタ」
して LLM コンテキストへ注入。

### 17.3 ビュー仕様

| View | サブタブ | 主要機能 | 必要権限 (auth role) |
|------|---------|---------|---------|
| 🎬 Run | 🤖 Agent · 🛠 Skill | **Agent**: `st.chat_message` ベースの会話 UI、`AutonomousAgent.run(prompt, history=..., images=...)` を毎ターン呼出 (直近 3 ターン渡す)、tool-use trace 表示。**画像入力対応** (`st.chat_input(accept_file="multiple")`、PNG/JPG/GIF/WebP) — base64 化して LiteLLM 統一 `image_url` 形式で渡す。**会話履歴の永続化** = `praxia.data.threads.ThreadStore` が `.praxia/chats/<user>/<id>.json` に JSON 保存、UI は `st.popover` ベースの `💬 会話履歴` でスレッド一覧 / 再開 / 改名 / 削除。エフェメラル ON では in-memory のみ (no disk writes)。**Skill**: 6 業務スキル選択 + テキスト/ファイル/音声入力 | `run_skills` |
| 🧠 Knowledge | — | 個人メモリブラウズ + 共有ブロック + Skill registry (個人 + 組織昇格分) | `read_personal_memory` |
| 📁 Data | 📁 Local · 🔌 Connector · 🔍 Browse | データフォルダ CRUD。ローカルは parent_id で多層化、cascade 削除。コネクタは外部パス登録 (admin が env で連携先有効化) | (制限なし) |
| 📝 Prompts | ✨ Generate · 📚 Browse & edit · 📤 Distribute | PromptDesigner で生成 / 編集削除 / admin 配信 | `distribute` のみ admin |
| 📊 Stats | — | 3 KPI + plotly 横棒グラフ (Top skills 個人 / Top users + Top skills 組織) | (制限なし) |
| 👤 Preferences | — | 言語 / カラーテーマ (Auto / Light / Dark)、永続化 | (制限なし) |
| ⚙ Admin | 🔑 Settings · 👥 Users · 🔌 Connectors · 🛡 Policies · 🌙 Consolidate · 💾 Exports · ℹ About | テナント設定 (LLM/backend) + 永続 KNOWN_KEYS + ユーザ管理 + コネクタ + ACL + 統合 (sleep-time) + エクスポート | `admin` のみ |

**ナビゲーションの role-aware 制御**: `actor_role in ("admin", "unknown")`
だけが Admin top-bar item を見られる。`unknown` (= ユーザ未登録の
開発モード) はメンテナがアクセス可能になる安全弁。それ以外
(`member` / `operator` / `viewer`) には Admin が非表示。

### 17.4 Context 注入仕様

選択された custom scope のファイル群は `gather_scope_context(scope_ids, query, max_chars)` で:

1. 全合計が `max_chars` (デフォルト 20,000 文字) 以内 → そのまま全部 concat
2. 超過 + `query` 与えられている → 各ファイルを行単位で grep (キーワード長 ≥ 3)、マッチ周辺 ±2 行を抽出 + 重複範囲をマージ
3. 超過 + query 無し → 各ファイル先頭 5,000 文字を best-effort sample

Path 2 が「読める範囲で多段抽出」の基本動作。Skill mode は `user_input`、Agent mode は最新メッセージを query として渡す。
連続的な絞り込みが必要な場合は Agent mode を使用 (会話の都度 grep が走る)。

---

## 18. HTTP API (`praxia serve`)

### 18.1 エンドポイント詳細

#### 18.1.1 認証

```http
POST /api/v1/auth/login
Content-Type: application/json

{"api_key": "praxia_..."}
```
レスポンス:
```json
{"token": "eyJhbGciOi...", "user_id": "...", "role": "member"}
```

```http
GET /api/v1/me
Authorization: Bearer <jwt>

→ {"id": "...", "username": "alice", "role": "member"}
```

#### 18.1.2 スキル / フロー

```http
POST /api/v1/skills/{name}
X-API-Key: praxia_...
Content-Type: application/json

{"input": "Q3 review of Acme Mfg", "kwargs": {}}

→ {"output": "...", "skill": "investment_analyst"}
```

```http
POST /api/v1/flows/{name}
X-API-Key: praxia_...

{"inputs": {"customer_name": "Acme", "product": "BizFlow"}}

→ {"output": "...", "step_outputs": {"step1": "...", ...}, "usage": {...}}
```

#### 18.1.3 メモリ

```http
POST /api/v1/memory/search
X-API-Key: praxia_...

{"query": "manufacturing pain", "limit": 5}

→ {"results": ["...", "..."]}
```

```http
PUT /api/v1/memory/mode
X-API-Key: praxia_...

{"mode": "read_only"}

→ {"ok": true, "mode": "read_only"}
```

```http
GET /api/v1/memory/show
X-API-Key: praxia_...

→ {"backend": "mem0", "mode": "accumulate", "locked_by_admin": false, "reason": "..."}
```

#### 18.1.4 出力エクスポート

```http
POST /api/v1/export
X-API-Key: praxia_...

{"content": "# Title\n\n...", "format": "pptx", "title": "Q3 Review"}

→ Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation
   (binary bytes)
```

### 18.2 エラー応答

```json
{"detail": "Permission denied: action=manage_users"}
```

| HTTP | 状況 |
|---|---|
| 400 | リクエスト不正 (mode 値が不正等) |
| 401 | 認証失敗 |
| 403 | 認可拒否 |
| 404 | スキル / フロー / リソース不在 |
| 503 | 任意 SDK 不在 |
| 500 | 内部エラー |

### 18.3 CORS

```bash
praxia serve --cors-origin https://your-frontend.example \
             --cors-origin https://staging.your-frontend.example
```

各 `--cors-origin` は繰り返し可能。指定しない場合 CORS は無効。

---

## 19. 設定 (Configuration)

### 19.1 解決順序

```
1. プロセス環境変数  (最優先)
2. .env ファイル (作業ディレクトリ)
3. .praxia/config.toml
4. (各機能の hard-coded default)
```

### 19.2 全設定キー (カテゴリ別)

#### 19.2.1 LLM プロバイダ

| キー | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude |
| `OPENAI_API_KEY` | ChatGPT / Whisper / TTS |
| `GEMINI_API_KEY` | Gemini |
| `DASHSCOPE_API_KEY` | Qwen API |
| `OPENROUTER_API_KEY` | OpenRouter ゲートウェイ |
| `OLLAMA_API_BASE` | Ollama (既定 http://localhost:11434) |
| `PRAXIA_LOCAL_MODEL` | auto_detect ローカルフォールバック (既定 `qwen-local`) |

#### 19.2.2 メモリ

| キー | 用途 |
|---|---|
| `PRAXIA_MEMORY_BACKEND` | デフォルトバックエンド (`json` 等) |
| `PRAXIA_MEMORY_MODE` | デフォルトモード (`accumulate` \| `read_only`) |
| `QDRANT_URL` | Qdrant エンドポイント (mem0 で使用) |

#### 19.2.3 認証認可

| キー | 用途 |
|---|---|
| `PRAXIA_JWT_SECRET` | JWT 署名鍵 (本番必須) |
| `PRAXIA_JWT_TTL` | JWT 有効期限 (秒、既定 3600) |
| `PRAXIA_TOKEN_ENC_KEY` | OAuth トークン暗号化鍵 (本番必須) |

#### 19.2.4 SSO

| キー | 用途 |
|---|---|
| `PRAXIA_SSO_PROVIDER` | google / microsoft / okta / github / keycloak / custom_oidc |
| `PRAXIA_SSO_CLIENT_ID` | クライアント ID |
| `PRAXIA_SSO_CLIENT_SECRET` | クライアントシークレット |
| `PRAXIA_SSO_REDIRECT_URI` | コールバック URL |
| `PRAXIA_SSO_TENANT_ID` | Microsoft Entra |
| `PRAXIA_SSO_OKTA_DOMAIN` | Okta |
| `PRAXIA_SSO_KEYCLOAK_BASE_URL` | Keycloak |
| `PRAXIA_SSO_KEYCLOAK_REALM` | Keycloak realm |
| `PRAXIA_SSO_ISSUER_URL` | 汎用 OIDC issuer |
| `PRAXIA_SSO_AUTO_PROVISION` | 初回 SSO で member 自動作成 (true/false) |

#### 19.2.5 ユーザ委譲 OAuth (連携先別)

| プロバイダ | キー |
|---|---|
| Box | `PRAXIA_OAUTH_BOX_CLIENT_ID/SECRET` |
| Microsoft | `PRAXIA_OAUTH_MICROSOFT_CLIENT_ID/SECRET` |
| Dropbox | `PRAXIA_OAUTH_DROPBOX_CLIENT_ID/SECRET` |
| Google | `PRAXIA_OAUTH_GOOGLE_CLIENT_ID/SECRET` |
| Salesforce | `PRAXIA_OAUTH_SALESFORCE_CLIENT_ID/SECRET` |

#### 19.2.6 共有資格情報 (legacy / service account)

```
PRAXIA_CONN_<UPPERCASE_NAME>_<UPPERCASE_KEY>
```

例: `PRAXIA_CONN_BOX_ACCESS_TOKEN`, `PRAXIA_CONN_KINTONE_API_TOKEN`, `PRAXIA_CONN_SALESFORCE_USERNAME`.

#### 19.2.7 音声

| キー | 用途 |
|---|---|
| `ELEVENLABS_API_KEY` | ElevenLabs TTS |
| (OpenAI Whisper / TTS は `OPENAI_API_KEY` を流用) | |

### 19.3 config CLI

```bash
praxia config show           # 解決済み設定表示 (シークレットマスク)
praxia config path           # キーがどこから解決されたか
praxia config get KEY        # 単一キー取得
praxia config set KEY VALUE  # config.toml に永続化
praxia config init           # 対話ウィザード
```

### 19.4 シークレット出力ガード

`praxia config show` および admin export では以下キーがマスクされます:
- `*_SECRET`, `*_KEY`, `*_TOKEN`, `*_PASSWORD` 終端のキー
- API キーハッシュ全般 (`api_key_hash`)
- パスワードハッシュ (`password_hash`)
- 暗号化済 OAuth トークン

---

## 20. デプロイ / 拡張性 / 法的配慮

### 20.1 3 デプロイモード

| モード | 起動 | 適合 |
|---|---|---|
| A. フルスタック | `praxia ui --port 8501` | 内製チーム、最短ルート |
| B-1. SDK 埋込 | `import praxia` from your Python service | Python 既存基盤 |
| B-2. HTTP サービス | `praxia serve --port 8000` | Python 以外フロント、モバイル |

詳細: [`docs/deployment-modes.ja.md`](../deployment-modes.ja.md)

### 20.2 7 拡張ポイント

`praxia.extensions.Registry` 共通プリミティブを使用:

| 拡張 | エントリポイント | 規模 |
|---|---|---|
| Connector | `praxia.connectors` | ~50 行 |
| Memory backend | `praxia.memory_backends` | ~80 行 |
| File parser | `praxia.parsers` | ~30 行 |
| Output exporter | `praxia.exporters` | ~40 行 |
| OAuth provider | `praxia.oauth_providers` | ~10 行 |
| Skill | `praxia.skills` | ~20 行 |
| Flow | `praxia.flows` | ~30 行 |

詳細チュートリアル: [`docs/CUSTOM_CONNECTORS.ja.md`](../CUSTOM_CONNECTORS.ja.md), [`docs/PLUGINS.md`](../PLUGINS.md)

### 20.3 法的配慮

#### 20.3.1 同梱テンプレート

| ドキュメント | 用途 |
|---|---|
| `docs/legal/TERMS.md` | 利用規約 (template) |
| `docs/legal/PRIVACY.md` | プライバシーポリシー (template) |
| `docs/legal/ACCEPTABLE_USE.md` | 利用可能ポリシー (template) |
| `docs/legal/COOKIES.md` | Cookie ポリシー (template) |

**全テンプレート明示**: 「本テンプレートは弁護士の確認後に商用利用してください」。

#### 20.3.2 PII の取り扱い

- **個人メモリ**: ユーザ自身の入力以外の他者 PII は記録しない設計を推奨 (システム側強制ではない)
- **昇格パイプライン**: `PromotionEngine._self_eval` が PII 候補を低スコア化 (LLM judge による)
- **監査ログ**: PII を含む可能性があるため admin 以外読み取り不可 (ファイル権限 0600)
- **エクスポート時**: `api_key_hash` `password_hash` は自動除去

#### 20.3.3 業務スキルのガードレール

| スキル | ガードレール文言 |
|---|---|
| InvestmentSkill | 「最終投資判断は投資家自身の責任」 |
| LegalSkill | 「弁護士による確認を推奨」「特定法域限定」 |
| PatentSkill | 「最終判断は弁理士に」 |
| PurchasingSkill | 下請法 / 独占禁止法の注意喚起 |

各スキルの system_prompt 末尾に組込み済み。

---

## 20a. KMS / HSM ベースのトークン暗号化

ユーザ委譲 OAuth トークンは **envelope encryption** で保管:
1. 書込ごとに **256-bit のデータ暗号化鍵 (DEK)** を新規生成
2. DEK で本体を **AES-GCM** 暗号化
3. DEK を `KmsAdapter` で wrap (KMS / HSM 内のマスター鍵で暗号化)
4. ファイルには `{nonce, ciphertext, wrapped_dek, alg, kms}` を JSON で保存

**マスター鍵はアプリケーションホストに存在しません。**

### 20a.1 5 アダプタの選択

```bash
export PRAXIA_KMS_ADAPTER=aws  # local / aws / azure / gcp / vault
```

| アダプタ | パッケージ | 推奨用途 |
|---|---|---|
| `local` | (組込) | 開発 / 単一ホスト |
| `aws` | `praxia[kms-aws]` (boto3) | AWS 環境 |
| `azure` | `praxia[kms-azure]` | Azure 環境 (RSA-OAEP wrap) |
| `gcp` | `praxia[kms-gcp]` | GCP 環境 |
| `vault` | `praxia[kms-vault]` (hvac) | HashiCorp Vault Transit |

### 20a.2 アダプタ別設定例

```python
# AWS KMS
from praxia.connectors.oauth.kms import AwsKmsAdapter
from praxia.connectors.oauth import OAuthTokenStore

adapter = AwsKmsAdapter(
    key_id="arn:aws:kms:us-east-1:111122223333:key/...",
    region="us-east-1",
)
store = OAuthTokenStore(storage_dir=".praxia/auth", kms=adapter)

# HashiCorp Vault Transit
from praxia.connectors.oauth.kms import VaultTransitAdapter
adapter = VaultTransitAdapter(
    vault_url="https://vault.example.com:8200",
    key_name="praxia-tokens",
    token=os.environ["VAULT_TOKEN"],
)
```

### 20a.3 旧形式との互換性

v0.1 の HMAC keystream 形式トークンは `_decrypt_legacy()` で透過的に復号 → 再保存時に新 envelope 形式へ自動移行。ユーザの再認可不要。

### 20a.4 カスタムアダプタの追加

```python
class MyKmsAdapter:
    name = "my-kms"
    def wrap(self, dek: bytes) -> bytes: ...
    def unwrap(self, wrapped: bytes) -> bytes: ...

# entry-point で発見可能化
[project.entry-points."praxia.kms_adapters"]
my-kms = "my_pkg.kms:MyKmsAdapter"
```

---

## 20b. 本番 OAuth コールバック ハンドラ

CLI ベースの `praxia oauth start` は loopback 動作のため本番で使えません。本番では `praxia serve` (FastAPI) を起動し以下の endpoint を利用:

| エンドポイント | 概要 |
|---|---|
| `POST /api/v1/oauth/{provider}/start` | 現在ユーザの authorize URL を返却 |
| `GET /api/v1/oauth/{provider}/callback` | IdP redirect 受信、code 交換、トークン保存 |
| `GET /api/v1/oauth/{provider}/status` | トークン保有 + 有効期限 |
| `DELETE /api/v1/oauth/{provider}` | ローカル失効 |

### 20b.1 multi-worker 安全な state cache

`PersistentStateStore` は state を `.praxia/auth/oauth_states.json` に書出 (TTL 既定 600 秒)。複数ワーカ / 複数ホスト間で共有されるため、redirect がどの replica に届いても正しく処理される。

### 20b.2 必須環境変数

```bash
export PRAXIA_PUBLIC_URL=https://praxia.example.com  # redirect URI 固定化
export PRAXIA_OAUTH_BOX_CLIENT_ID=...
export PRAXIA_OAUTH_BOX_CLIENT_SECRET=...
export PRAXIA_KMS_ADAPTER=aws                         # 推奨
```

### 20b.3 成功時の動作

`PRAXIA_OAUTH_SUCCESS_REDIRECT` 設定時 → 当 URL へ 302。未設定時 → 「✅ Authorized」HTML を返却。

---

## 20c. A/B 実験フレーム (`praxia.experiments`)

プロンプト / スキル / LLM プロバイダ / メモリバックエンドのいずれも **opaque payload として** バリアント化可能。

### 20c.1 構成要素

| クラス | 役割 |
|---|---|
| `Experiment` | id / name / variants / traffic_split / target_audience / start_at / end_at / status |
| `Variant` | name + payload (任意 JSON) |
| `ExperimentStatus` | `draft` / `running` / `paused` / `finished` |
| `ExperimentRegistry` | CRUD + assign + record_outcome + results |
| `Assignment` / `ExperimentOutcome` / `ExperimentResults` | データクラス |

### 20c.2 アサインメントアルゴリズム

```python
# 純関数 — 同一 (experiment_id, user_id) は常に同 variant へマップ
hash = SHA256(f"{experiment.id}:{user_id}".encode())
bucket = int.from_bytes(hash[:8], "big") / 2**64    # [0.0, 1.0)
cumulative = 0.0
for name, share in traffic_split.items():
    cumulative += share
    if bucket < cumulative:
        return variants[name]
```

特性:
- **決定論的** — 実験 ID + user_id が同じなら結果も同じ
- **再現可能** — テストや障害解析で再現容易
- **新ユーザに即時適用** — 集計済テーブル不要
- **実験 ID を変えるとリシャッフル** — 意図的な再無作為化が可能

### 20c.3 オーディエンスフィルタ

```python
target_audience={
    "roles": ["operator", "member"],   # ロール限定
    "users": ["alice", "bob"],          # ユーザ限定
    # "*" でワイルドカード
}
# start_at / end_at で時間窓も指定可能
```

ロール / ユーザに該当しない、もしくは時間窓外、もしくは status != RUNNING の場合 `assign()` は `None` を返却。

### 20c.4 アウトカム計測

```python
# スキル / フロー実行結果から:
reg.record_outcome(
    "proposal_v2",
    user_id="alice",
    episode_id=ep.id,
    success=True,
    score=0.92,
    notes="closed-won",
    role="member",
)
```

variant 別に `.praxia/experiments/outcomes/<exp_id>.jsonl` へ追記。

### 20c.5 結果集計 + 暫定 winner 検出

```python
results = reg.results("proposal_v2")
# results.variants  : list[VariantSummary]
#   .name / .outcomes_recorded / .successes / .success_rate / .avg_score
# results.winner    : str | None (5pt 以上の差 + 30 outcome 以上で確定)
# results.confidence: float (margin × √n / 5、上限 1.0)
```

**注意**: 暫定 winner は本番投入判断には不十分。本格的検定 (proportion test / Bayesian) は別途実施推奨。

### 20c.6 利用パターン

```python
# 1. プロンプトの A/B
variant = reg.assign("prompt_v2", user_id=user.id, role=user.role)
prompt = variant.payload["prompt"] if variant else default_prompt

# 2. LLM プロバイダの A/B
model_alias = variant.payload.get("model", "claude") if variant else "claude"
llm = LLM(model_alias)

# 3. メモリバックエンドの A/B
backend_name = variant.payload["backend"] if variant else "json"
pm = PersonalMemory(user_id=user.id, backend=backend_name)
```

---

## 20d. LLM 出力品質評価フレーム (`tests/llm_eval/`)

決定論的な機能テスト (`tests/evaluation/`) とは別に、**実際に LLM を呼んで** 品質をルーブリック採点 → ベースラインと比較してデグレを検知。

### 20d.1 ルーブリック (組込)

| 名称 | 評価対象 |
|---|---|
| `EXACT_MATCH` | 完全一致 |
| `KEYWORDS` | 期待キーワードのカバー率 |
| `STRUCTURE` | Markdown 見出しの一致率 |
| `STRUCTURE_PLUS_KEYWORDS` | 上記 2 つの加重平均 |
| `LENGTH_BAND` | 長さが [min_length, max_length] 内か |
| `HALLUCINATION_LOW` | (将来拡張用) ハルシネーション率 |
| `LLM_JUDGE` | 別 LLM が 0-10 スコアリング (0..1 に正規化) |

### 20d.2 ベースライン管理

```bash
# 現状を採点
pytest tests/llm_eval -m llm_eval -v

# ベースライン更新 (既知良好状態で)
pytest tests/llm_eval --update-baselines

# 別モデルで採点
pytest tests/llm_eval --llm-eval-model gpt-4o
```

`tests/llm_eval/baselines.json` を git 管理。各 PR でスコアが **5pt 超低下** すると CI 失敗。モデル別に独立 (claude のベースラインと gpt-4o のベースラインは別行)。

### 20d.3 同梱ケース (各業務スキル 1 件)

| ケース ID | スキル | 主要ルーブリック |
|---|---|---|
| `investment_q3_review` | InvestmentSkill | STRUCTURE_PLUS_KEYWORDS (5 セクション) |
| `sales_b2b_prep` | SalesSkill | STRUCTURE_PLUS_KEYWORDS (3 セクション) |
| `design_review_dragon` | DesignSkill | STRUCTURE_PLUS_KEYWORDS (DRAGON 6 軸) |
| `purchasing_rfq_compare` | PurchasingSkill | STRUCTURE_PLUS_KEYWORDS (QCD+S) |
| `patent_prior_art` | PatentSkill | STRUCTURE_PLUS_KEYWORDS (5 ステップ) |
| `legal_contract_review` | LegalSkill | STRUCTURE_PLUS_KEYWORDS (RACE) |

加えて `must_not_contain` で「投資判断は投資家自身」「弁護士確認を」等のガードレール文言確認。

### 20d.4 LLM-as-judge の注意点

`LLM_JUDGE` ルーブリックを使う際、**評価対象 LLM と判定 LLM を別モデルにすべき** (self-preference bias 回避)。例: Claude を評価する判定は GPT-4o、GPT-4o を評価する判定は Claude。

```bash
pytest tests/llm_eval \
    --llm-eval-model claude \
    --llm-eval-judge gpt-4o
```

---

## 21. デモデータ免責

業務スキルのデモ・チュートリアル・サンプルコードに登場する企業名 (Acme Manufacturing, AcmeAuto Inc. 等)、財務数値、業務シナリオは **架空** であり実在の企業を指すものではありません。

実在企業を指して動作確認する場合:
- 投資デモ: 公開 IR 資料のみを入力
- 法務デモ: 自社契約のみを入力 (相手方契約は許諾必要)
- 特許デモ: 公開特許番号のみ

---

## 22. 用語集

| 用語 | 意味 |
|---|---|
| Flow | 宣言的に定義されたエージェントステップの DAG |
| Skill | Capability bundle: prompt + tools + reference docs (Claude Skills 互換) |
| LTM | Long-term memory backend |
| RRF | Reciprocal Rank Fusion |
| Promotion | 個人メモリ → 組織メモリへの昇格 |
| Consolidator | sleep-time に PromotionEngine を全ユーザに走らせるバッチ |
| Connector | 外部ストレージ / SaaS の pull/push プラグイン |
| Mode | accumulate (書込有効) / read_only (書込ドロップ) |
| RBAC | Role-Based Access Control |
| ACL | Access Control List (リソースレベル) |
| OIDC | OpenID Connect |
| PKCE | Proof Key for Code Exchange (OAuth 拡張) |
| Episode | フロー実行単位の記録 |
| Outcome | episode に紐付く成果 (success / score) |
| Block | 共有メモリの単位 (label + value + read_only) |
| Frozen layer | Markdown + git で凍結された安定版知識 |
| AutonomousAgent | LLM 駆動のツール使用ループを回す自律エージェント (`praxia.agent`) |

---

## AutonomousAgent (自律エージェント)

`praxia.agent.AutonomousAgent` は **LLM 駆動のツール使用ループ**
を Praxia の各レイヤ上で実行する。利用者がツールを明示的に呼び出さなくても、
LLM が自発的に「個人メモリ検索 → 組織メモリ検索 → 凍結層検索 → スキル一覧 →
スキル実行 → コネクタ pull → 最終回答」の流れを判断して進行する。

組込みツールは 11 種類:
`search_personal_memory` / `search_org_memory` / `search_frozen_layer` /
`list_skills` / `list_personal_skills` / `list_org_skills` / `run_skill` /
`list_connectors` / `pull_from_connector` / `record_fact` / `final_answer`。

ガバナンス:

- 全ツール呼び出しを `auth.audit.record(...)` で監査ログに記録
- `pull_from_connector` は `auth.policies.require(...)` で ACL チェック
  → 拒否時は `{"ok": false, "error": "access denied"}` を LLM に返す
  (例外を投げずにループは継続するが保護リソースは保護される)
- `record_fact` は `read_only` モード時に no-op (理由を LLM に通知)
- `enable_tools=[...]` でツール露出を絞れる (`final_answer` は常に保持)

CLI: `praxia agent run "<task>" --user-id alice --max-steps 10`
MCP: 単一メタツール `autonomous_agent` として `tools/list` に露出。

---

## 改訂履歴

| 版 | 日付 | 内容 |
|---|---|---|
| v1.0 | 2026-05 | 初版 |
| v1.1 | 2026-05 | AutonomousAgent (自律エージェント) を追加 |
