# 今後の対応 — 公開・運用に必要な作業の網羅リスト

このドキュメントは Praxia を公開して運用するために **アカウント取得・登録作業** を時系列で並べたものです。技術的な TODO は [TODO.md](TODO.md) を参照。

> **📌 表記**:
> 🔴 = 公開前に必須 / 🟡 = 公開後早期に必要 / 🟢 = 後回し可
> ⏱ = 推定所要時間 / 💴 = 想定コスト

---

## 0. 重要な前提 — 「OSS 公開」と「Hosted alpha 運営」は別作業

このドキュメントは 2 つのフェーズの作業が混在しています。混同しないように注意:

| フェーズ | 作業範囲 | 例 |
|---|---|---|
| **A: OSS 公開** | コード / landing / Zenn を世に出す。**全 OSS 利用者がそのまま恩恵を受ける** | § 1〜6 (ドメイン / GitHub / PyPI / landing / メール / X) + § 9 (Tally) + § 10 (Zenn) + § 12 (拡散) |
| **B: Hosted alpha 運営** | praxia.dev 自身でホスティングサービスを提供。**Genki さん側だけが必要** | § 7 (SSO 登録) + § 8 (OAuth コネクタ登録) + § 11 (hosted 基盤) + § 13 (法務) |

### 0.1 SSO / OAuth の代理登録は **できない**

「Genki さんが OAuth アプリを 1 セット登録すれば OSS 利用者全員が使える」は **不可能** です。理由:

1. **redirect_uri ドメイン縛り**: 各 OAuth アプリの redirect_uri は単一ドメインに固定。Acme 社が自社内で Praxia を立てても、Genki さんの praxia.dev 用アプリには接続不能。
2. **プロバイダ ToS 違反**: Box / Google / Slack / Salesforce / Microsoft 等は client_secret の第三者共有を**明示的に禁止**。OSS 配布物に同梱したら即アプリ suspend。
3. **suspend のブラスト半径**: 1 人の利用者の悪用で全 OSS 利用者の OAuth が止まる。
4. **レート制限共有**: 1000 利用者が同じアプリを使うと API 制限を全員で奪い合う。
5. **SSO は IdP の話**: Acme 社の社員は Acme 社の Google Workspace / Okta でしか認証できない。Genki さんの IdP では別組織の社員を認証不可。

→ **OSS 利用者は自社で各プロバイダにアプリ登録する必要があります。** これは Praxia の責任ではなく OAuth プロトコルの設計上の制約です。

OSS 利用者向けの per-provider 登録手順は [`docs/OAUTH_SCOPES.ja.md`](docs/OAUTH_SCOPES.ja.md) に整備済 (Genki さんは整備状況だけ確認)。

### 0.2 § 7 / § 8 / § 11 / § 13 は Hosted alpha が動き始めるまで保留可

waitlist (§ 9) で 10 件程度溜まってから着手で十分。それまでに着手しても、登録した OAuth アプリの本番審査 (Google / Slack の年次レビュー等) を毎年通す手間 だけ増えます。

---

## 1. 🔴 ドメイン取得 (最優先 — 他作業の前提)

ほぼ全ての他作業がドメインに依存します。**最初に確定** させてください。

### 1.1 ドメイン候補 + 取得

候補:
- `praxia.dev` (推奨。`.dev` は Google Domains が安価、HTTPS 強制で SEO に有利)
- `praxia.ai` (現行 landing で部分的に使用。ただし `.ai` は年 $80–100 と高め)
- `praxia.io` ($30/年程度、開発者向けに馴染みやすい)
- `praxia.tools`, `praxia.app` 等の代替

### 1.2 作業手順

1. <https://domains.google> または <https://www.namecheap.com> でドメイン在庫確認
2. **`praxia.dev` を取得** (`.dev` 推奨。⏱ 5 分 / 💴 約 1,500 円/年)
3. WHOIS Privacy を有効化
4. DNS は **Cloudflare に NS 委任** (1.4 で利用)

### 1.3 取得後に置換が必要な箇所

ドメイン確定後、以下を一括置換:

```powershell
# PowerShell — agentloom/ から実行
Get-ChildItem -Recurse -Include *.html,*.md,*.js,*.py |
  ForEach-Object {
    (Get-Content $_ -Raw) -replace 'praxia\.pages\.dev', '<NEW-DOMAIN>' |
                          Set-Content $_
  }
```

影響箇所 (placeholder として残っている):
- `web-publish/index.html` の canonical / alternate links (10 件)
- `web-publish/portal/index.html` の canonical
- `web-publish/sitemap.xml` / `robots.txt`
- `web-publish/404.html`
- README.md のバッジ

---

## 2. 🔴 GitHub Organization + Repository 公開

### 2.0 GitHub に「**何を**」公開するか

`c:\Users\r00507718\ClaudeCode\OSS\agentloom\` 配下を **そのまま全部** GitHub に push します。3 つの公開先 (GitHub / Web / Zenn) を分かり易くするため、トップレベルディレクトリで分離済 (B 案):

```
agentloom/                   ← この階層がリポジトリのルート
├── praxia/                  ← OSS 本体 (Python パッケージ)
├── tests/                   ← 全テスト
├── docs/                    ← 技術ドキュメント (FEATURES.md, architecture.md, specs/, legal/, …)
├── examples/                ← サンプルコード
├── pyproject.toml
├── README.md                ← GitHub 上の TOP 表示
├── LICENSE                  ← Apache 2.0
├── NOTICE.md                ← 第三者ライセンス一覧
├── SECURITY.md              ← 脆弱性報告窓口
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── PUBLISH.md               ← 各種公開手順 (this file の元ネタ)
├── NEXT_ACTIONS.ja.md       ← (本ドキュメント) 公開・運用作業ロードマップ
├── web-publish/             ← Cloudflare / GitHub Pages にデプロイ (GitHub にも置いておく)
└── zenn-publish/            ← zenn-cli で投稿 (GitHub にも置いておく)
```

`web-publish/` と `zenn-publish/` も **GitHub に含める** (deploy 元になるため)。ただし、ユーザの目から見える主な入口は `README.md` + `praxia/` + `docs/`。

`.gitignore` で除外: `__pycache__/` / `.praxia/` / `.env` / `*.pyc` / `.venv/` 等 (既存 `.gitignore` を確認)

### 2.1 Organization 名の決定

現在 `genarch/praxia` がプレースホルダ。候補:
- `genarch` (現プレースホルダのまま採用)
- `praxia-dev` / `praxia-ai`
- 個人アカウント (alpha 期間中はこれでも可)

### 2.2 Repository 作成 (⏱ 30 分)

1. <https://github.com/organizations/new> で Organization 作成 (無料)
2. **Public** リポジトリを作成 (名前: `praxia`)
3. ローカルリポジトリを push:
   ```powershell
   cd c:\Users\r00507718\ClaudeCode\OSS\agentloom
   git remote add origin https://github.com/<NEW-ORG>/praxia.git
   git push -u origin main
   ```

### 2.2.1 Repository Settings の **具体的設定値** (チェックリスト)

push 後、Settings タブで以下を順に設定:

**General**:
- [ ] Description: `Multi-agent orchestrator with cyclic personal-to-org memory · Apache 2.0 · Python 3.11+`
- [ ] Website: `https://praxia.dev`
- [ ] Topics: `ai-agents`, `multi-agent`, `llm`, `mem0`, `mcp`, `autonomous-agent`, `rag`, `knowledge-management`, `oauth`, `rbac`, `python`, `apache-2-0`
- [ ] Default branch: `main`
- [ ] Features:
  - [x] Issues
  - [x] Discussions
  - [x] Projects (任意)
  - [ ] Wikis (使わない / Discussions に集約)
  - [ ] Sponsorships (Hosted alpha 開始後に有効化)
- [ ] Pull Requests:
  - [x] Allow squash merging (推奨デフォルト)
  - [ ] Allow merge commits (オフ)
  - [ ] Allow rebase merging (オフ)
  - [x] Always suggest updating pull request branches
  - [x] Automatically delete head branches

**Branches → Branch protection rule for `main`** (alpha 段階は緩めで OK):
- [x] Require a pull request before merging
  - [ ] Required approvals: 0 (ソロ開発中) → 1+ (コラボレータが増えたら)
  - [x] Dismiss stale pull request approvals when new commits are pushed
- [x] Require status checks to pass before merging (CI workflow 設定後)
  - [x] Require branches to be up to date before merging
- [x] Require conversation resolution before merging
- [ ] Require signed commits (任意 — GPG キー運用が前提)
- [x] Do not allow bypassing the above settings (適用範囲: Repository administrators)

**Pages**:
- [x] Source: Deploy from a branch
  - [x] Branch: `main` / Folder: `/web-publish`
  - URL: `https://<NEW-ORG>.github.io/praxia/`
  > Cloudflare Pages を主、GitHub Pages を副ミラーとして併用 (§ 4 参照)

**Secrets and variables → Actions → New repository secret**:
- [ ] `PYPI_API_TOKEN` (PyPI 公開時に作成。Trusted Publishing を使う場合は不要)
- [ ] `CLOUDFLARE_API_TOKEN` (CF Pages 自動デプロイ用、任意)
- [ ] `CLOUDFLARE_ACCOUNT_ID` (同上)

**Code security**:
- [x] Private vulnerability reporting → 有効化 (security@ を確認)
- [x] Dependabot alerts → 有効化
- [x] Dependabot security updates → 有効化
- [x] Code scanning (CodeQL) → 自動セットアップで PR

### 2.2.2 必須ファイルの追加 (現状リポジトリに **ないもの**)

push 前または直後に以下を作成:

**`.github/ISSUE_TEMPLATE/bug_report.yml`**:
```yaml
name: Bug report
description: Praxia がうまく動かない場合
labels: ["bug"]
body:
  - type: textarea
    attributes: {label: 何が起きたか, description: 期待値と実際の挙動}
  - type: input
    attributes: {label: Praxia version, placeholder: "0.1.0a1"}
  - type: input
    attributes: {label: Python version, placeholder: "3.11.7"}
  - type: dropdown
    attributes:
      label: LLM provider
      options: [claude, chatgpt, gemini, deepseek, mistral, grok, qwen, llama, gemma, phi, qwen-local, other]
  - type: textarea
    attributes: {label: 再現手順, render: bash}
  - type: textarea
    attributes: {label: 関連ログ, render: shell}
```

**`.github/ISSUE_TEMPLATE/feature_request.yml`**:
```yaml
name: Feature request
description: 新機能の提案
labels: ["enhancement"]
body:
  - type: textarea
    attributes: {label: 何を解決したいか}
  - type: textarea
    attributes: {label: 提案する解法}
  - type: textarea
    attributes: {label: 代替案}
```

**`.github/PULL_REQUEST_TEMPLATE.md`**:
```markdown
## What
<!-- 変更内容 1 行 -->

## Why
<!-- 動機 / 関連 issue -->

## Tests
- [ ] `pytest tests/ --ignore=tests/llm_eval` が通る
- [ ] 必要なら `tests/llm_eval/` も実行 (`-m llm_eval`)

## Docs
- [ ] README / FEATURES / specs を更新した (該当する場合)
```

**`.github/workflows/test.yml`** (CI):
```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '${{ matrix.python }}' }
      - run: pip install -e '.[dev]'
      - run: pytest tests/ -q --ignore=tests/llm_eval
```

**`.github/workflows/publish.yml`** (PyPI 自動公開、§ 3.5):
```yaml
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions: { id-token: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install build && python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

**`FUNDING.yml`** (Sponsorships タブを有効化したいなら):
```yaml
github: [<NEW-ORG>]
custom: ["https://praxia.dev/sponsor"]
```

### 2.2.3 README badges を repo に合わせて更新

push 後、README 冒頭のバッジ URL を実 ORG/REPO に更新:
```markdown
[![CI](https://github.com/<ORG>/<REPO>/actions/workflows/test.yml/badge.svg)](https://github.com/<ORG>/<REPO>/actions/workflows/test.yml)
```

### 2.3 ハンドル/URL 一括置換

```powershell
# `genarch/praxia` を実 ORG/REPO に置換 (約 22 箇所)
Get-ChildItem -Recurse -Include *.html,*.md,*.js,*.py |
  ForEach-Object {
    (Get-Content $_ -Raw) -replace 'github\.com/genarch/praxia',
                                    'github.com/<NEW-ORG>/<NEW-REPO>' |
                          Set-Content $_
  }
```

### 2.4 GitHub Topics 推奨

```
ai-agents, multi-agent, llm, mem0, langmem, mcp, autonomous-agent,
rag, knowledge-management, organizational-memory, business-skills,
oauth, rbac, audit-log, apache-2-0, python
```

---

## 3. 🔴 PyPI パッケージ公開 (`praxia`)

### 3.1 PyPI アカウント取得

1. <https://pypi.org/account/register/> でアカウント作成
2. 2FA を有効化 (TOTP / WebAuthn 必須)
3. API トークンを発行 (Account settings → API tokens → "Add API token")
4. トークンを GitHub Secrets に保存 (`PYPI_API_TOKEN`)

### 3.2 名前確保 (⏱ 10 分)

> ⚠️ `praxia` がすでに別パッケージとして登録されていないか確認。

```powershell
pip index versions praxia 2>&1
# Found: ... または ERROR: No matching distribution
```

**取られていれば代替名候補**: `praxia-os` / `praxia-loom` / `agentloom` (現リポ名のフォールバック)

### 3.3 Test PyPI で検証 (⏱ 30 分)

```powershell
# 1. Test PyPI アカウントも作成: https://test.pypi.org
pip install build twine
python -m build
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ praxia
```

### 3.4 本番 PyPI 公開 (alpha タグ推奨)

```powershell
# pyproject.toml の version を "0.1.0a1" などに
twine upload dist/*
```

### 3.5 GitHub Actions で自動公開

`.github/workflows/publish.yml` を作成し、tag push で自動公開。テンプレ:

```yaml
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions: { id-token: write }   # Trusted Publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install build && python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

> Trusted Publishing (OIDC) を PyPI 側で構成しておくと API トークン保存不要。

---

## 4. 🔴 ランディングページ公開 (Cloudflare Pages + GitHub Pages)

### 4.1 Cloudflare アカウント (主ミラー)

1. <https://dash.cloudflare.com/sign-up> でアカウント作成 (無料・カード不要)
2. Workers & Pages → Pages → "Connect to Git"
3. GitHub OAuth 連携 → 公開 repo を選択
4. ビルド設定:
   ```
   Production branch:    main
   Framework preset:     None
   Build command:        (空)
   Build output dir:     web-publish
   ```
5. Save and Deploy → 約 30 秒で `https://praxia.pages.dev` が稼働
6. Custom domain → ドメイン (`praxia.dev`) を接続 → SSL 自動発行 (約 5 分)

### 4.2 GitHub Pages (副ミラー)

1. リポジトリ → Settings → Pages
2. Source: `Deploy from a branch` → branch `main` / folder `web-publish/` (`docs/landing` から既に移動済)
3. URL: `https://<NEW-ORG>.github.io/praxia/`

### 4.3 「**何を**」アップする — ファイル配置の具体

ドメイン取得後、Cloudflare Pages / GitHub Pages いずれもデプロイ元は **GitHub repo の `web-publish/` ディレクトリ** です。**手動でファイルをアップロードする必要はありません**。Git push が即デプロイになります。

#### 4.3.1 デプロイ単位 (Cloudflare Pages の場合)

```
GitHub repo (main ブランチ)
   │
   └─ web-publish/                  ← Cloudflare Pages の build output dir
       ├── index.html              ← https://praxia.dev/
       ├── styles.css              ← https://praxia.dev/styles.css
       ├── i18n.js                 ← https://praxia.dev/i18n.js
       ├── consent.js              ← https://praxia.dev/consent.js
       ├── images/                 ← https://praxia.dev/images/*
       │   ├── hero-banner.svg
       │   ├── architecture.svg
       │   └── ui-*.svg (12 件)
       ├── portal/
       │   ├── index.html          ← https://praxia.dev/portal/
       │   └── portal.css          ← https://praxia.dev/portal/portal.css
       ├── 404.html                ← 404 時に表示
       ├── robots.txt              ← クローラ向け
       ├── sitemap.xml             ← 検索エンジン向け
       ├── _redirects              ← Cloudflare Pages 用 alias (例: /github → GitHub)
       ├── _headers                ← Cloudflare Pages 用セキュリティヘッダ + キャッシュ
       └── .nojekyll               ← GitHub Pages 用 (Jekyll 処理を無効化)
```

#### 4.3.2 デプロイ手順 (Cloudflare Pages の最初の 1 回)

1. <https://dash.cloudflare.com> → Workers & Pages → Create → Pages → Connect to Git
2. GitHub OAuth 連携 → repo を選択
3. **Build settings** に以下を入力 (1 回だけ):
   ```
   Production branch:    main
   Framework preset:     None
   Build command:        (空欄)
   Build output dir:     web-publish
   Root directory:       (空欄、デフォルトのまま)
   ```
4. **Save and Deploy** → 約 30 秒で `https://<PROJECT>.pages.dev` 稼働
5. Custom domains → ドメイン (`praxia.dev`) を接続 → SSL 自動 (約 5 分)

**以降の更新**: `git push origin main` するだけで自動デプロイ。手動アップロード不要。

#### 4.3.3 デプロイ手順 (GitHub Pages 副ミラー、最初の 1 回)

1. repo Settings → Pages
2. Source: Deploy from a branch
3. Branch: `main` / Folder: `/web-publish` を選択
4. Save → 約 1 分で `https://<NEW-ORG>.github.io/praxia/` 稼働

**ミラー間の SEO 整合性**: `web-publish/index.html` の `<link rel="canonical">` が Cloudflare 側を指しているので、検索エンジンは Cloudflare を主と認識します。

### 4.4 詳細手順は `web-publish/DEPLOY.md` を参照

---

## 5. 🔴 メールアドレス取得

### 5.1 必要なエイリアス (最低 3 件)

| エイリアス | 用途 | 現在の HP 表記 |
|---|---|---|
| `hello@praxia.dev` | 一般問合せ・ポータルからのフォールバック | landing line 1442 / portal line 95 |
| `privacy@praxia.dev` | プライバシー関連 (GDPR/個人情報問合せ) | docs/legal/PRIVACY.md |
| `security@praxia.dev` | 脆弱性報告 | SECURITY.md |
| (任意) `noreply@praxia.dev` | システム送信 (将来 Stripe / SCIM / 通知) | — |

### 5.2 取得方法 (3 案)

| 案 | 月額 | メリット | デメリット |
|---|---|---|---|
| **Cloudflare Email Routing** (推奨) | **無料** | ドメイン取得後すぐ。エイリアス → 既存 Gmail へ転送 | 送信は Gmail 経由 ("via gmail.com" が出る) |
| Google Workspace | $6 / アカウント | 「@praxia.dev」で送信、信頼性高 | 月額発生 |
| Zoho Mail Lite | $1 / アカウント | 安価で「@praxia.dev」送信可 | 機能少 |

**推奨: Cloudflare Email Routing からスタート**。Hosted alpha が動き始めたら Workspace に移行。

### 5.3 セットアップ (Cloudflare Email Routing 例)

1. Cloudflare ダッシュボード → ドメイン → Email → Email Routing
2. "Enable Email Routing" → MX/TXT レコード自動追加
3. Routes:
   - `hello@praxia.dev` → `<your-personal-email>`
   - `privacy@praxia.dev` → `<your-personal-email>`
   - `security@praxia.dev` → `<your-personal-email>`
4. ⚠️ ドメイン不整合修正: 現状 landing line 1442 が `hello@praxia.ai` (`.ai`)、他は `.dev` 混在。**`.dev` に統一** (取得済前提):

```powershell
Get-ChildItem -Recurse -Include *.html,*.md |
  ForEach-Object {
    (Get-Content $_ -Raw) -replace 'praxia\.ai', 'praxia.dev' |
                          Set-Content $_
  }
```

---

## 6. 🟡 X (旧 Twitter) アカウント取得

### 6.1 ハンドル取得 (⏱ 15 分)

1. <https://x.com/i/flow/signup> でアカウント作成
2. ハンドル候補: `@praxia_dev` / `@praxia_ai` / `@praxia_loom`
3. プロフィール:
   - 名前: `Praxia`
   - bio: `Open-source multi-agent orchestrator with cyclic personal/org memory · Apache 2.0`
   - URL: `https://praxia.dev`
   - ロゴ: `web-publish/images/hero-banner.svg` を 400×400 にトリム
4. **電話番号確認** が必要 (アカウントスパム対策)

### 6.2 ローンチスレッドのドラフト (公開直前まで保留)

下書き保管場所: `marketing/x-launch-thread.md` (作業項目として作成推奨)

骨子例:
```
1/8 🪡 We just open-sourced Praxia: a multi-agent orchestrator that
turns one expert's drawer into everyone's playbook. Apache 2.0.
GitHub: <URL> · landing: praxia.dev

2/8 The headline mechanism: personal memory → org memory.
Senior staff's "magic prompts" auto-promote into shared knowledge
via 3 independent paths (frequency / outcome / LLM self-eval).

3/8 ... (フィーチャ × 5 + CTA)
```

### 6.3 HP 反映

X ハンドル取得後:
- footer Community 列に `<li><a href="https://x.com/<HANDLE>">𝕏</a></li>` を追加
- `web-publish/i18n.js` に `footer.com.x` キーを 8 言語で追加

---

## 7. 🟡 SSO プロバイダ登録 (OIDC アプリ作成) — **Hosted alpha 専用**

> ## ⚠️ ここは **Hosted alpha (praxia.dev でホストする運営者向け)** の作業です
>
> **OSS 利用者向けには不要** です。OSS で self-host する組織 (Acme 社など) は、自社の IdP (Acme 社の Google Workspace / Okta) に **自分で** Praxia アプリを登録します。第三者 (Genki さん等) が代理登録しても、redirect_uri ドメイン不一致 + プロバイダ ToS 違反のため動きません。
>
> このセクションは **`praxia.dev` で hosted alpha を運営する場合の自分の作業** を意味します。waitlist で 10 件程度溜まってから着手で十分です。

### 7.1 各プロバイダの作業

#### Google Workspace OIDC
1. <https://console.cloud.google.com/apis/credentials> → Create Credentials → OAuth 2.0 Client ID
2. Application type: Web application
3. Authorized redirect URIs:
   ```
   https://praxia.dev/api/v1/auth/sso/google/callback
   http://localhost:8000/api/v1/auth/sso/google/callback   # 開発用
   ```
4. Client ID + Secret を `PRAXIA_OAUTH_GOOGLE_CLIENT_ID` / `_CLIENT_SECRET` に設定

> 同じ Client ID を「OAuth ログイン」と「Google Drive コネクタ」両方に使い回せる (scope を別々に要求するだけ)

#### Microsoft Entra ID (旧 Azure AD)
1. <https://portal.azure.com> → Microsoft Entra ID → App registrations → New registration
2. Redirect URI:
   ```
   https://praxia.dev/api/v1/auth/sso/microsoft/callback
   ```
3. Certificates & secrets → New client secret → 値を `PRAXIA_OAUTH_MICROSOFT_CLIENT_SECRET` へ
4. API permissions → Microsoft Graph → 必要な scope を追加:
   - `openid` `profile` `email` (SSO ログイン用)
   - `Files.ReadWrite.All` `Sites.Read.All` (SharePoint コネクタ用)
   - `ChannelMessage.Read.All` `ChannelMessage.Send` (Teams コネクタ用)
5. Tenant ID を `PRAXIA_SSO_TENANT_ID` に設定

#### Okta
1. <https://developer.okta.com/signup/> で開発者アカウント作成 (無料 dev tenant)
2. Applications → Create App Integration → OIDC - Web Application
3. Sign-in redirect URIs:
   ```
   https://praxia.dev/api/v1/auth/sso/okta/callback
   ```
4. `PRAXIA_SSO_OKTA_DOMAIN=<your-tenant>.okta.com` を設定

#### GitHub OAuth App
1. <https://github.com/settings/developers> → OAuth Apps → New OAuth App
2. Authorization callback URL:
   ```
   https://praxia.dev/api/v1/auth/sso/github/callback
   ```
3. Client ID + Secret を environment に

#### Keycloak (self-hosted)
- 顧客側 Keycloak に「Praxia」クライアントを作る作業ガイド を `docs/auth.md` に書く (作業項目)

### 7.2 取得した認証情報の保管

- **本番**: AWS Secrets Manager / Azure Key Vault / GCP Secret Manager (KMS と同じ場所)
- **alpha 期間中**: Cloudflare Workers Secret store (Cloudflare Pages からアクセス可)
- **開発**: `.env` に書く + `.gitignore` で除外確認

---

## 8. 🟡 OAuth コネクタ用プロバイダ登録 — **Hosted alpha 専用**

> ## ⚠️ ここも **Hosted alpha 専用** の作業です
>
> **OSS 利用者向けには登録不要** です。OSS で self-host する組織は、各プロバイダ (Box / Salesforce / Slack / 等) に **自分で** OAuth アプリを登録し、`PRAXIA_OAUTH_<PROVIDER>_CLIENT_ID` / `_CLIENT_SECRET` を自社環境変数に設定します。Genki さんが praxia.dev 用に登録した client_id を OSS 配布物に含めることは **プロバイダ ToS 違反** + redirect_uri ドメイン不一致のため不可能 + アプリ suspend のブラスト半径が大きすぎるため絶対にやってはいけません。
>
> OSS 利用者向けの per-provider 登録手順は [`docs/OAUTH_SCOPES.ja.md`](docs/OAUTH_SCOPES.ja.md) に既に整備済。
>
> このセクションは **praxia.dev (hosted alpha 自身) で利用する OAuth アプリ** の登録手順です。SSO 登録 (§ 7) は「ログイン」用、これは「外部システムからのデータ取得」用。Microsoft / Google は § 7 の SSO 登録と兼用可能だが、他は専用アプリが必要。

### 8.1 必要なプロバイダ別アプリ

| プロバイダ | 開発者ポータル | 手順 | コスト |
|---|---|---|---|
| **Box** | <https://app.box.com/developers/console> | New App → Custom App → OAuth 2.0 with JWT/User auth | 無料 |
| **Microsoft 365** | (§ 7.1 の Azure AD と兼用) | API permissions に Files.* / Sites.* / ChannelMessage.* を追加 | 無料 |
| **Dropbox** | <https://www.dropbox.com/developers/apps> | Create app → Scoped access → App folder か Full Dropbox | 無料 |
| **Google Drive** | (§ 7.1 の Google Cloud と兼用) | OAuth client に `drive.readonly` `drive.file` scope を追加 | 無料 |
| **Salesforce** | Setup → Apps → App Manager → New Connected App | OAuth Settings: API (`api`) + `refresh_token` scope | 無料 (Developer Edition) |
| **kintone** | Cybozu developer portal | Custom app + OAuth client | サブスク要 |
| **Slack** | <https://api.slack.com/apps> | Create New App → From scratch → Bot & User Token Scopes | 無料 |
| **Notion** | <https://www.notion.so/my-integrations> | New integration → Public integration (OAuth) | 無料 |
| **HubSpot** | <https://developers.hubspot.com/> | Create app → Auth → OAuth | 無料 |
| **Zendesk** | Admin Center → Apps and integrations → APIs → Zendesk API → OAuth Clients | Confidential client → redirect URI | 無料 |
| **Linear** | Settings → API → OAuth applications | New OAuth app | 無料 |
| **GitHub** | (§ 7.1 と兼用) | repo / read:user / read:org scope を追加 | 無料 |
| **Confluence/Jira** | <https://developer.atlassian.com/console/myapps/> | Create → OAuth 2.0 (3LO) integration | 無料 |
| **Teams** | (§ 7.1 の Microsoft と兼用) | API permissions に Teams 系 scope 追加 (詳細は praxia/connectors/teams.py) | 無料 |

### 8.2 各アプリの redirect URI 共通

```
https://praxia.dev/api/v1/oauth/<provider>/callback
http://localhost:8000/api/v1/oauth/<provider>/callback   # 開発用
```

### 8.3 Zendesk 固有: subdomain

Zendesk は subdomain ごとに OAuth エンドポイントが異なるため、`PRAXIA_OAUTH_ZENDESK_SUBDOMAIN` の設定が **必須**。`praxia oauth start zendesk` は subdomain 未設定時にエラーで止まる (実装済)。

---

## 9. 🟡 Tally Waitlist フォーム作成

### 9.1 アカウント + フォーム作成 (⏱ 30 分)

1. <https://tally.so> でサインアップ (無料プランで OK)
2. New form → Layout: "Forms"、Template: "Waitlist" を選択
3. **必須フィールド** を追加:
   - Work email (必須)
   - Organization (text)
   - Use case (single-select):
     - 法務 (Legal)
     - 営業 (Sales)
     - 情シス (IT / Platform)
     - R&D / 技術
     - 設計 (Engineering Design)
     - 購買 (Procurement)
     - その他
   - Headcount (single-select): 1-10 / 11-100 / 101-1000 / 1000+
   - Notes (long-text、任意)
4. Settings → Notifications → Email / Slack / Notion 連携
5. Publish → Embed → form ID をコピー (`https://tally.so/r/<form-id>`)

### 9.2 HP 反映

`web-publish/portal/index.html` line 83 の `REPLACE_WITH_TALLY_FORM_ID` を実 ID に置換:

```html
<iframe data-tally-src="https://tally.so/embed/<ACTUAL-FORM-ID>?alignLeft=1&hideTitle=1&transparentBackground=1&dynamicHeight=1" ... />
```

### 9.3 通知の自動化 (任意)

- Tally → Slack incoming webhook → 専用チャンネルに通知
- Tally → Notion DB に自動追加 (フォロー漏れ防止)

---

## 10. 🟡 Zenn 公開 (技術記事 7 本)

> `zenn-publish/` 配下の 7 記事 (`00_overview.md` + 業務別 6 本) を Zenn に投稿。

### 10.1 アカウント + GitHub 連携

1. <https://zenn.dev/signup> で GitHub OAuth サインアップ (無料)
2. ダッシュボード → 設定 → GitHub からのデプロイ → 連携
3. Zenn-CLI をローカルに導入:
   ```powershell
   npm install -g zenn-cli
   cd zenn-publish
   npx zenn init      # 初回のみ — `articles/` `books/` ディレクトリ生成
   ```
4. 既存の `zenn-publish/00_overview.md` 〜 `06_legal.md` を `articles/` 配下に移動 or symlink

### 10.2 公開順 (推奨)

1. **Day 0**: GitHub repo 公開 + landing 公開 + X ハンドル取得
2. **Day 1**: Zenn `00_overview.md` を published: true に変更 → push
3. **Day 3**: 各業務記事を 1 日 1 本ずつ (営業 → 設計 → 法務 → 投資 → 購買 → 特許)
   - 1 日 1 本のペースで「Praxia 関連の記事が定期的に流れる」状態を作る
4. **Day 10**: ハッカーニュース / Reddit / X 拡散 (§ 12)

### 10.3 各記事 frontmatter 設定

```yaml
---
title: "..."
emoji: "🪡"
type: "tech"
topics: ["AI", "LLM", "agent", "Python"]
published: true        # ← false から true に変更
publication_name: ""   # 個人 publication または法人 publication 名
---
```

---

## 11. 🟢 (将来) Hosted Alpha 基盤

> Tally waitlist が 10〜20 件溜まったら hosted alpha を立てる前提。

### 11.1 hosting 候補

| サービス | 月額目安 | 推奨理由 |
|---|---|---|
| **Cloudflare Workers + R2 + D1** | $5 | landing と同じ Cloudflare で完結、KMS 連携も可 |
| **Render** | $7+ | 学習コスト低、Postgres 付き |
| **Fly.io** | $5+ | グローバル分散、Tigris (S3 互換) と連携 |
| **AWS App Runner / Lightsail** | $10+ | エンタープライズ顧客向け |

### 11.2 Stripe (将来 — 有料化のタイミングで)

1. <https://dashboard.stripe.com/register> でアカウント作成
2. **business verification 必須** (個人事業主含む / 数日かかる)
3. テスト環境で `praxia` 用の Product / Price を作成
4. Webhook → Praxia の billing endpoint へ
5. 日本円対応のため Stripe Japan 統合 (法人化が必要なケースあり)

### 11.3 KMS (本番 OAuth トークン暗号化)

| プロバイダ | 月額 | 設定 |
|---|---|---|
| AWS KMS | ~$1/key + 使用量 | `PRAXIA_KMS_ADAPTER=aws` + `PRAXIA_KMS_KEY_ID=arn:...` |
| Azure Key Vault | ~$1/key + 操作 | `PRAXIA_KMS_ADAPTER=azure` |
| GCP Cloud KMS | ~$0.06/key | `PRAXIA_KMS_ADAPTER=gcp` |
| HashiCorp Vault | self-host | `PRAXIA_KMS_ADAPTER=vault` + Vault Transit |

> 開発・alpha 期間は `PRAXIA_KMS_ADAPTER=local` (HKDF-based) で十分。production hosted の前に切替。

---

## 12. 🟡 利用ユーザ拡散施策 (User Acquisition)

### 12.1 公開直後 (Day 0–7) — "ローンチ波"

| 媒体 | 担当 | 工数 | 備考 |
|---|---|---|---|
| **GitHub README polish** | 必須 | 半日 | star 獲得の起点 |
| **X 公式アカウント** + ローンチスレッド | 必須 | 1h | フォロワー 0 → 100 が初日目標 |
| **Hacker News** "Show HN: Praxia" | 推奨 | 30 min | 投稿時刻は **平日 8〜10 AM PT** が最適。タイトル例: `Show HN: Praxia – Open-source multi-agent orchestrator that auto-promotes personal memory to org memory` |
| **Reddit /r/LocalLLaMA** | 推奨 | 30 min | self-host 派にリーチ。タイトル例: `Praxia: open-source agent framework with built-in personal→org memory cycling, supports Ollama / Gemma / Qwen / Phi locally` |
| **Reddit /r/MachineLearning** | 任意 | 30 min | 学術寄り、本気の批判が来るので心構え必要 |
| **Reddit /r/Python** | 推奨 | 15 min | パッケージ拡散 |
| **Zenn `00_overview` 記事公開** | 必須 | (already drafted) | 日本語圏での本流 |
| **Qiita 横展開** (任意) | 任意 | 1 day | Zenn 記事を Qiita 用にリライト + 投稿 |
| **dev.to 横展開** (任意) | 任意 | 半日 | 英語版 overview を投稿 |
| **Producthunt** (Day 7 以降) | 推奨 | 1h 設定 + 1 day 投票期間 | hosted alpha が動き出してから推奨 (登録ユーザがいないと評価が悪い) |

### 12.2 継続施策 (Week 2+)

| 施策 | 頻度 | 工数/回 |
|---|---|---|
| Zenn 業務別記事の連載 (営業 / 設計 / 法務 / 投資 / 購買 / 特許) | 週 1 | 既存ドラフト → 数時間 |
| X での Tip スレッド (「個人 → 組織メモリの cycle はこう動く」等) | 週 2 | 30 min |
| GitHub Discussions に Q&A スレッドを開設 + 自分で seed | 月 1 | 1h |
| Cloudflare Pages の Web Analytics で流入元を分析 → 効く媒体に集中 | 月 1 | 1h |

### 12.3 ターゲットコミュニティ (深く掘ると良い場所)

| コミュニティ | URL | 注目度 |
|---|---|---|
| **MCP Discord** | <https://discord.gg/anthropic> (Anthropic 公式) | MCP 互換が刺さる |
| **LangChain Discord** | <https://discord.gg/langchain> | LangGraph 補完位置 |
| **Mem0 Discord** | <https://discord.com/invite/mem0> | バックエンドとして使ってる前提を強み化 |
| **Hugging Face Forums** | <https://discuss.huggingface.co/> | OSS LLM ユーザ層 |
| **r/LangChain** | reddit | 競合 / 補完 |
| **DEV Community** | dev.to | 記事マルチポスト |

### 12.4 SEO 最適化

- Zenn / Qiita / dev.to は **同記事複数公開 OK** (canonical タグ設定)
- `web-publish/index.html` の SEO 強化:
  - meta description (現在仮): `praxia config show` 画面で説明 → 検索結果での CTR 影響大
  - JSON-LD で Organization + SoftwareApplication schema を追加 (作業項目)
  - sitemap.xml は既に最小構成。記事 URL を追加

### 12.5 AI インフルエンサー / メディアアウトリーチ

> **基本方針**: 押し売りはしない。「OSS で公開した、こういう特徴があります」と **客観情報** を渡し、**取り上げるかは相手判断** という姿勢。スパム化すると逆効果。

#### 12.5.1 X (旧 Twitter) — 国内 AI 系インフルエンサー

| ハンドル候補 (例) | 専門 | コンタクト方法 |
|---|---|---|
| `@karaage0703` | Python / 個人 OSS / 機械学習 | X DM 解放、Zenn フォロワー多数 |
| `@umiyuki_ai` | LLM / AI ニュース | X DM 解放、note 連動 |
| `@kun1emon` (グッドラック) | LLM 国内動向 | X 公開リプ歓迎風 |
| `@npaka123` | LLM ハンズオン (note: 「npaka」) | note メッセージ + X |
| `@chu___mtu` (ちゅみとう) | エンジニア向け生成 AI | X DM |
| `@hatena_chips` | AI ツール紹介 | X DM |
| `@ai_database` | AI 関連 OSS まとめ | X 公開リプ |
| `@KanHatakeyama` (畠山さん) | AI 学術 / OSS | X DM |
| `@daiki15036604` | LangChain / RAG 専門 | X DM |

#### 12.5.2 X — 海外 AI 系インフルエンサー

| ハンドル | 専門 |
|---|---|
| `@simonw` (Simon Willison) | OSS LLM ツール紹介の総本山 (LWN.net 級の影響力) |
| `@LangChainAI` (公式) | LangChain 補完位置として紹介してもらえる可能性 |
| `@hwchase17` (LangChain CEO) | フォロワー多 |
| `@svpino` (Santiago) | 生成 AI 教育系 |
| `@swyx` (latent space) | 「latent.space」podcast / AI engineer |
| `@dotey` (宝玉) | 中国 AI 界隈の翻訳ハブ (DeepSeek 訴求にハマる) |

#### 12.5.3 アプローチ手順 (各インフルエンサー共通)

1. **公開を待つ** (GitHub repo / landing / Tally form 全部稼働してから)
2. **DM 例 (英語)**:
   ```
   Hi <name>, I just open-sourced Praxia — an Apache-2.0 multi-agent
   orchestrator with built-in personal→org memory cycling and an MCP
   meta-tool. Thought it might fit your "OSS LLM tools" coverage:
       https://praxia.dev
       https://github.com/<org>/praxia (~431 deterministic tests, 27 LLM aliases)

   Happy to answer questions or send a quick demo if useful. No
   expectation either way — just sharing because I think the
   personal→org loop is novel.
   ```
3. **DM 例 (日本語)**:
   ```
   <相手のハンドル> さん、Praxia という OSS を公開しました。
   個人メモリを自動的に組織知に昇格させる仕組みを持つマルチエージェント
   オーケストレータです (Apache 2.0)。

       https://praxia.dev
       https://github.com/<org>/praxia

   `自律エージェント (LLM 駆動ツール使用ループ)` も同梱しており、
   ChatGPT / Claude / DeepSeek / Mistral / Llama / Gemma / Phi
   などをエイリアス 1 行で切替可能です。

   ご紹介に値するか判断いただけますと幸いです。具体的なデモも
   ご希望あれば。返信不要です。
   ```
4. **タイミング**: 平日 10:00-11:00 JST / 14:00-16:00 JST が反応率高
5. **追跡**: 1 週間以内に既読 / 反応がなければ深追いしない

#### 12.5.4 ニュースレター / ブログ媒体

| 媒体 | URL | 寄稿可能性 |
|---|---|---|
| **Pivotal: AI Tinkerers** (Substack) | <https://tinkerers.substack.com> | 投稿フォームあり |
| **TLDR AI** | <https://tldr.tech/ai> | tip 送信フォーム |
| **The Rundown AI** | <https://therundown.ai> | tip 送信フォーム |
| **Towards Data Science** (Medium) | medium 寄稿 | 自記事を投稿 |
| **AI Weekly** | <https://aiweekly.co/issues> | tip 送信 |
| **AINOW (国内)** | <https://ainow.ai/> | プレスリリース送信 |
| **MarkeZine** (国内) | プレスリリース | 営業 / マーケ事例として訴求 |

#### 12.5.5 ポッドキャスト / YouTube

| 番組 | 言語 | 切り口 |
|---|---|---|
| **Latent Space** (swyx) | 英語 | 「OSS フレームワーク」枠 |
| **MLOps Community Podcast** | 英語 | 運用面 (auth / audit / KMS) を訴求 |
| **AI Engineer World's Fair** プレゼン応募 | 英語 | 大型カンファレンス |
| **しゅーまっち** (`@chu___mtu` 主催) | 日本語 | YouTube + Twitter Live |
| **生成 AI なんでも相談所** 系 (Discord 等) | 日本語 | LT 機会 |

#### 12.5.6 紹介してもらう際に渡すアセット (事前準備)

公開時に以下を **`web-publish/press-kit/`** にまとめておくと便利 (作業項目):
- ロゴ (SVG / PNG / 透過背景 / 4 サイズ)
- スクリーンショット 5-7 枚 (UI / CLI / Architecture)
- 50 字 / 140 字 / 500 字の説明文 (日英)
- ファクトシート (Apache 2.0 / Python 3.11+ / 27 LLM alias 等)
- 1-pager PDF (`docs/use-cases.md` を整形)
- creator の bio + 顔写真 (任意)

これがあると「メディアキット URL」を渡すだけで掲載が早い。

### 12.6 アンバサダー / 早期採用者向け施策

- **早期 Hosted alpha 招待** = 待機リストの最初の 10〜20 組織には無料で招待
- **Contributor T-shirt 配布** (Apache 2.0 OSS の伝統的施策、コスト ~$30/枚)
- **「Praxia adopter」バッジ** (README に記載される企業ロゴ枠) — 採用企業から自社サイトに「Powered by Praxia」を出してもらう代わりに目立つ場所に掲示

### 12.7 enterprise outreach (5 人以下のフォーカスチーム時)

下記 5 業界に **直接コンタクト** すると hit が早い (alpha invitation):
- 中堅 SaaS の **CTO / VP Eng** (DesignSkill 訴求)
- 法律事務所の **マネージング・パートナー / IT 担当** (LegalSkill 訴求)
- 製造業の **購買部長** (PurchasingSkill 訴求 — 30 社評価デモ)
- 特許事務所の **CIO** (PatentSkill 訴求 — 弁理士費用削減訴求)
- 商社の **DX 推進部** (汎用スキル + メモリ循環の話)

LinkedIn → Sales Navigator で対象を絞り、初回コンタクトは 200 字以下で。

---

## 13. 🟢 法務関連 (将来 — 本格商用化のタイミング)

### 13.1 レビュー必要な書類

`docs/legal/` 内のテンプレは **すべて未レビュー**:
- `TERMS.md` (利用規約)
- `PRIVACY.md` (プライバシーポリシー)
- `ACCEPTABLE_USE.md` (利用規定)
- `COOKIES.md` (クッキーポリシー)

→ alpha 期間中は「draft, not legally reviewed」を明示。Hosted alpha がペイ顧客を持つ前に **弁護士レビュー必須**。

### 13.2 認証取得の検討タイミング

- **SOC 2 Type II**: 顧客 5 社 / MRR $10k 以降に検討。費用 $40k+
- **ISO 27001**: 国際展開時に。費用 ~$20k
- **GDPR DPO**: EU 顧客が出始めたら必要

→ いずれも `docs/COMPLIANCE.md` に roadmap として隔離。landing には書かない (未取得を晒すデメリットの方が大きい)。

---

## 14. 必要アカウント・登録のチェックリスト (まとめ)

### 14.1 公開前 (Day 0 までに)

- [ ] ドメイン取得 (`praxia.dev` 等)
- [ ] Cloudflare アカウント (DNS + Pages + Email Routing)
- [ ] メールエイリアス 3 件 (hello / privacy / security)
- [ ] GitHub Organization + repo
- [ ] PyPI アカウント + パッケージ予約 (`praxia` または代替)

### 14.2 公開直後 (Week 1 以内)

- [ ] X / Twitter ハンドル
- [ ] Zenn アカウント + GitHub 連携
- [ ] Tally アカウント + waitlist フォーム
- [ ] Hacker News / Reddit / dev.to / Qiita アカウント (拡散用)

### 14.3 hosted alpha 開始時 (waitlist 10 件溜まったら) — **Genki さん側だけ必要**

> ここから下は **praxia.dev で hosting する自分の作業**。OSS 利用者は別途自社で同等の登録を行います (これは利用者の責任)。

- [ ] hosting 先アカウント (Cloudflare Workers / Render / Fly.io いずれか)
- [ ] Google Cloud / Azure / GitHub OAuth Apps (**praxia.dev 用** SSO ログイン)
- [ ] OAuth コネクタ用アプリ (**praxia.dev 用** Box / Salesforce / Notion / Slack 等 — 必要なものだけ)
- [ ] KMS プロバイダ (本番トークン暗号化用、`PRAXIA_KMS_ADAPTER=aws/azure/gcp/vault`)
- [ ] エラー監視 (Sentry / DataDog / Cloudflare Logpush)
- [ ] DPA (Data Processing Agreement) ドラフト + プライバシーポリシー hosted 専用節追加
- [ ] hosted 利用規約に "禁止行為 (スパム / スクレイピング)" 明記 (アプリ suspend のリスク回避)
- [ ] per-user rate limit + 異常アクセス検知の実装 (1 人の悪用で全員停止を防ぐ)

### 14.4 商用化時 (有料顧客が出始めたら)

- [ ] Stripe アカウント (法人化 + business verification)
- [ ] 弁護士レビュー (legal templates)
- [ ] 法人化 (Praxia 株式会社 / 合同会社)
- [ ] (海外展開) Stripe Atlas / DUNS Number

---

## 15. 推奨タイムライン (1 ヶ月で公開する場合)

| 週 | 必須タスク |
|---|---|
| **Week 1** | ドメイン + Cloudflare + メール + GitHub repo 公開 (private) + PyPI 名前確保 |
| **Week 2** | landing デプロイ (Cloudflare Pages) + GitHub repo を public に + Tally form 作成 |
| **Week 3** | Zenn `00_overview` を published に + X ハンドル取得 + ローンチスレッド準備 |
| **Week 4 (Day 0)** | HN / Reddit / X 同時投下 → 翌日以降 Zenn 業務別記事を 1 日 1 本 |

---

## 16. 細かい技術 TODO (旧 TODO.md からマージ)

### 16.1 確定後に一括置換が必要なプレースホルダ

#### 16.1.1 GitHub URL (約 22 箇所)
- `https://github.com/genarch/praxia` → 実 ORG/REPO に置換
- 影響ファイル:
  - `web-publish/index.html` (10+ 箇所)
  - `web-publish/portal/index.html`
  - `README.md`
  - `PUBLISH.md`
  - `zenn-publish/0[0-6]*.md`
  - `docs/*.md` (blob/main へのリンク多数)
- PowerShell 一括置換コマンド:
  ```powershell
  Get-ChildItem -Recurse -Include *.html,*.md,*.js,*.py |
    ForEach-Object {
      (Get-Content $_ -Raw) -replace 'github\.com/genarch/praxia',
                                      'github.com/<NEW-ORG>/<NEW-REPO>' |
                            Set-Content $_
    }
  ```

#### 16.1.2 Web ドメイン (約 12 箇所)
- `praxia.pages.dev` → 実ドメイン (例: `praxia.dev`) に置換
- 影響ファイル: `web-publish/index.html` の canonical / alternate (line 12-20) / `404.html` / `_redirects` / `sitemap.xml` / `portal/index.html` / `web-publish/DEPLOY.md` / `web-publish/README.md`
- `genarch.github.io/praxia` も同様に確認

#### 16.1.3 メールドメイン
- 現状 landing line 1442 が `hello@praxia.ai`、portal が `hello@praxia.dev` で **不整合**
- 取得済ドメインに **統一** (推奨は `.dev`)
- 影響: `web-publish/portal/index.html`、`web-publish/index.html`、`docs/legal/*`、`SECURITY.md`

#### 16.1.4 X / Twitter ハンドル (取得後の追加作業)
1. `web-publish/index.html` の footer "Community" 列に追加:
   ```html
   <li><a href="https://x.com/<HANDLE>" data-i18n="footer.com.x">𝕏</a></li>
   ```
2. `web-publish/i18n.js` に `footer.com.x` キーを 8 言語で追加
3. `README.md` のバッジ近辺に X リンクを追記

### 16.2 Tally Waitlist フォーム (§ 9 のフォロー作業)

- [ ] Tally でフォーム作成 (フィールド一覧は `web-publish/portal/index.html` の HTML コメント参照)
- [ ] `web-publish/portal/index.html` line 83 の `REPLACE_WITH_TALLY_FORM_ID` を実 ID に差し替え
- [ ] Tally → Slack / email / Notion へ通知 webhook 設定 (フォロー漏れ防止)

### 16.3 Editions / 価格メッセージング (将来)

- [ ] Hosted バックエンドが実稼働したら 3 つ目の Editions ティアを復活 + Stripe リンクを導入。それまでは OSS + Hosted-alpha の 2 ティア構成を意図的に維持。
- [ ] SOC 2 / ISO 27001 着手時は 進行状況 (取得予定日付き) を **landing ではなく** `docs/COMPLIANCE.md` に隔離して記述。

### 16.4 Hosted alpha 基盤 (§ 11 の詳細)

- [ ] hosting 先決定: Cloudflare Workers + KV + Durable Objects か、Render / Fly.io + Postgres か。(DO の方が安価、Render の方が一般的)
- [ ] `praxia serve` を実カスタムドメインで TLS 配下に
- [ ] portal の SSO redirect ハンドラの実装 (Google / Microsoft / GitHub / Okta) — `praxia/auth/sso.py` のコードは既に存在
- [ ] Stripe 連携 (最初は invoice-only で開始しても可)

### 16.5 Compliance / 法務 (§ 13 の詳細)

- [ ] `docs/legal/` (TERMS / PRIVACY / AUP / COOKIES) の弁護士レビュー — テンプレ状態のまま商用利用しないこと
- [ ] SOC 2 Type II / ISO 27001 — roadmap 段階。本気で取りに行くタイミングが決まってから landing に書く

### 16.6 マーケティング / コミュニティ (§ 12 の詳細)

- [ ] 7 本の Zenn 記事 (`00_overview` + `01..06` 業務別) を順次公開。frontmatter の `published: false` を `true` に
- [ ] HN / r/MachineLearning / r/LocalLLaMA への投稿は GitHub repo URL が確定してから (リンク 404 を避ける)
- [ ] X ローンチスレッド を ハンドル取得後に投下

### 16.7 残存技術負債 (最近の機能追加で生じたもの)

- [ ] `web-publish/i18n.js` のドイツ語訳でネスト Unicode 引用符を剥がした箇所が数箇所ある — 意味は通るが文体としては劣化。余裕ができたら言い換え。
- [ ] Examples panel (10 業界 × 5 文字列ずつ ≈ 50 文字列) が英語のまま。優先度低だが、翻訳の余地あり。

### 16.8 残った OSS ストレッチ項目 (低優先)

- [ ] 4 experimental backends (langmem / letta / zep / hindsight) の **実 SDK 検証 + バージョン pin**。完了したら `praxia list backends` で 🟡 → ✅ に上げる。
- [ ] Notion コネクタの Markdown→ブロック変換 (現状はパラグラフ平坦化で見出し / リスト / コードが反映されない)
- [ ] Confluence コネクタの On-prem (DC) サポート — 現状 Cloud 版のみ
- [ ] Eval framework の Phase 2 (MRR / NDCG / faithfulness 等のメトリクス追加)
- [ ] `praxia.extensions.Registry._discover()` の失敗 entry-point を CLI から可視化 (`connector list --diagnose` 等)

---

## 17. 完了済 (changelog 候補)

| 日付 | 内容 |
|---|---|
| 2026-05-06 | `praxia.agent.AutonomousAgent` 実装 — 組込ツール 11 種 + ACL/audit + CLI + MCP メタツール + 13 deterministic test |
| 2026-05-06 | LLM プロバイダ拡張: 11 alias 追加 (DeepSeek / Mistral / xAI / Llama / Cohere / Perplexity / Phi)、`auto_detect()` 3 ティア優先順位、テスト 5 件追加 |
| 2026-05-06 | ディレクトリ整理: `docs/landing` → `web-publish/`, `docs/zenn` → `zenn-publish/` |
| 2026-05-06 | Portal: スタブ認証フォームを self-host CTA + Tally waitlist embed に置換 |
| 2026-05-06 | Pricing → Editions: 3 ティアから 2 ティア (OSS + Hosted-alpha) に簡素化 |
| 2026-05-06 | Landing 翻訳: 18 hero chips + 36 feature card body + architecture + flows + skills + how-it-works + fit lists + 19 FAQ + footer + contact CTA を 8 言語化 |
| 2026-05-06 | Zenn 業務別 6 記事すべてに自律エージェント節を追加 |
| 2026-05-06 | 「触れるけど動かない」を除去 — `praxia oauth callback` CLI 削除 / SAMLProvider 撤去 / RAG UI スタブリトリーバ → PersonalMemory.search / MCP HTTP CLI flag docstring 修正 / Zendesk subdomain templating 実装 / SCIM PUT reactivation 実装 / KNOWN_KEYS 大幅拡張 / hallucination eval JSON parse failure 適切に surface |
| 2026-05-06 | Persona p1-p7 本文 + OSS edge c1-c9 本文 + scenario picker default の 8 言語翻訳追加 |
| 2026-05-06 | 「ClaudeCode 同等」「Claude-Code-style」表記を全 23 ファイルからニュートラル表現に統一 |
| 2026-05-06 | landing の "431 件のリグレッションテスト" → "Hermetic test harness — stubs & drivers" に表現改善 |
| 2026-05-06 | landing から "Formal design specs (EN+JA)" カードと "Preview runs locally" 説明文を削除 |

---

## 更新ルール

完了したら頭に `✅ 完了日` を付与:
```
- [x] ✅ 2026-05-10 ドメイン取得 (`praxia.dev`)
```

進捗が見えるとモチベ維持に効きます。新しい作業項目が発生したら該当セクションに追記。

