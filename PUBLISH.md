# 公開チェックリスト

GitHub に公開する前後の確認事項です。順番に進めてください。

---

## ✅ Step 1: ローカル動作確認

```bash
cd OSS/agentloom

# 依存関係インストール (開発モード + 全エクストラ)
pip install -e ".[all]"

# テスト実行
pytest -q

# Lint / 型チェック
ruff check .
mypy praxia
```

**期待結果**: テスト全件 PASS、ruff/mypy 警告ゼロ。

---

## ✅ Step 2: API キー設定 (任意・実機テスト時)

```bash
cp .env.example .env
# 利用したいプロバイダのキーを設定:
#   ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / DASHSCOPE_API_KEY
```

ローカル Qwen を試したい場合:
```bash
ollama pull qwen2.5:14b
praxia run sales --model qwen-local --customer-name "Acme"
```

---

## ✅ Step 3: GitHub Org / リポジトリ作成

1. GitHub にログイン → 個人 / GenArch Organization のどちらに作るか決める
   - **推奨**: GenArch という Organization を新規作成 (https://github.com/organizations/new)
   - Org にすると後でメンテナを追加しやすい
2. README.md / CONTRIBUTING.md / docs/ 内の `your-org` を実 Org 名に置換:

```bash
grep -rl "your-org" .
# 一括置換 (Linux/macOS / Git Bash)
find . -type f \( -name "*.md" -o -name "*.toml" -o -name "*.html" -o -name "*.svg" \) \
  -exec sed -i 's|your-org|genarch|g' {} +
```

---

## ✅ Step 4: GitHub リポジトリ作成 + 初回 push

```bash
# gh CLI 使用 (推奨)
gh repo create genarch/praxia --public \
  --source=. \
  --description "Specialized multi-agent orchestrator with cyclic personal/organizational memory" \
  --push
```

または手動:
```bash
# GitHub.com で genarch/praxia リポジトリを作成 (空)
git remote add origin git@github.com:genarch/praxia.git
git push -u origin main
```

---

## ✅ Step 5: ブランチ保護とアクセス権限の設定 ⚠️ 最重要

> **目的**: 他人が main を勝手に書き換えできないようにする / 誤って force push しないようにする / 全変更が PR 経由になるようにする。

### 5-1. リポジトリ可視性とコラボレータ

GitHub web で `Settings → Collaborators and teams`:
- Default permission: **Read** (org member は読み取りのみ)
- 自分は当然 admin
- 後でメンテナ追加するときは `Maintain` ロール (push できるが org 設定変更は不可)

### 5-2. ブランチ保護ルール (main)

`Settings → Branches → Add branch protection rule`:

```
Branch name pattern: main

✅ Require a pull request before merging
   ✅ Require approvals: 1 (コラボレータが増えたら)
   ✅ Dismiss stale pull request approvals when new commits are pushed
   ✅ Require review from Code Owners (CODEOWNERS を有効化したら)

✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   ✅ Status checks (after CI runs once): test, lint, type-check

✅ Require conversation resolution before merging
✅ Require signed commits  ← gpg or sigstore で commit 署名要求
✅ Require linear history   ← squash/rebase merge を強制

✅ Do not allow bypassing the above settings  ← admin もこれに従う

❌ Allow force pushes        ← OFF (絶対)
❌ Allow deletions           ← OFF (絶対)
```

### 5-3. CODEOWNERS ファイル (推奨)

`.github/CODEOWNERS` を追加すると、そのファイル変更時に **必ず特定の人のレビューが必要** になります:

```
# .github/CODEOWNERS
*               @your-github-username
LICENSE         @your-github-username
NOTICE.md       @your-github-username
pyproject.toml  @your-github-username
praxia/auth/*   @your-github-username
.github/*       @your-github-username
```

Org の場合は `@genarch/maintainers` のようにチーム名でも指定可能。

### 5-4. リポジトリ設定の追加チェック

`Settings → General` で:

```
Features:
  ☑ Issues          ← ON
  ☑ Discussions     ← ON
  ☐ Wiki            ← OFF (docs/ で管理)

Pull Requests:
  ☑ Allow squash merging        ← ON (履歴クリーン)
  ☐ Allow merge commits          ← OFF (linear history)
  ☐ Allow rebase merging         ← OFF
  ☑ Always suggest updating PR branches
  ☑ Allow auto-merge
  ☑ Automatically delete head branches  ← PR マージ後ブランチ自動削除

Security:
  ☑ Private vulnerability reporting    ← ON (脆弱性の非公開報告)
  ☑ Dependabot alerts
  ☑ Dependabot security updates
  ☑ Secret scanning
  ☑ Push protection                    ← API キー誤コミット防止
```

### 5-5. Org レベル / ロール設計

Org の場合 `Org settings → Member privileges`:

```
Base permissions: Read         ← Org メンバーのデフォルト
Repository creation: Disabled   ← 一般メンバーは新規リポジトリ作成不可
Forking: Allowed                ← フォークは OK (OSS の趣旨)
Pages creation: Public          ← Pages 公開を許可
```

ロール設計の推奨:

| ロール | 誰 | 権限 |
|---|---|---|
| Owner | 自分 (GenArch 代表) | 全権 |
| Admin | 信頼コア・メンバー (将来) | リポジトリ設定変更可、Org 設定不可 |
| Maintain | アクティブ・コントリビュータ | push、PR 承認可、設定変更不可 |
| Triage | コミュニティ・モデレータ | Issue/PR ラベル管理のみ |
| Read (default) | 一般 Org メンバー | フォークと clone のみ |

### 5-6. CI 必須化

`.github/workflows/ci.yml` は既に存在 (test + lint + mypy)。
ブランチ保護で **`test`, `lint`, `type-check` が PASS しないとマージ不可** に設定すると、誰がコントリビュートしても品質が担保されます。

### 5-7. 2FA 必須化

`Org Settings → Authentication security`:
- ☑ **Require two-factor authentication for everyone in the organization**

これで Org に乱入したい人が 2FA を設定しないと参加できません。

---

## ✅ Step 6: 公開設定

| 項目 | 推奨設定 |
|------|----------|
| Description | `Specialized multi-agent orchestrator with cyclic personal/organizational memory` |
| Topics | `ai`, `llm`, `agent`, `multi-agent`, `rag`, `memory`, `python`, `mem0`, `claude`, `qwen` |
| License | Apache License 2.0 (GitHub UI で確認) |
| Issues / Discussions | Enabled |

---

## ✅ Step 7: 初回 Release を切る

```bash
git tag v0.1.0a0 -m "Alpha release"
git push origin v0.1.0a0
gh release create v0.1.0a0 --title "v0.1.0a0 — Alpha" \
  --notes "Initial alpha release. See README.md for features."
```

---

## ✅ Step 8: PyPI に公開 (任意)

```bash
pip install build twine
python -m build
twine upload dist/*
```

PyPI トークンは https://pypi.org/manage/account/token/ で発行。
`.pypirc` に保存または `TWINE_USERNAME=__token__` + `TWINE_PASSWORD=pypi-xxx` 環境変数で。

---

## ✅ Step 9: ランディングページの公開先 — 両方使う

GitHub Pages と Cloudflare Pages の **両方** にデプロイし、相互リンクで運用します。

- **Primary**: Cloudflare Pages (`https://praxia.pages.dev/`) — 国際的に最速、無制限帯域
- **Secondary**: GitHub Pages (`https://genarch.github.io/praxia/`) — リポジトリ統合、フォールバック

両方が main へのプッシュで自動デプロイされ、ランディングページは visitor のいるミラーを検知して相互リンクを表示します。

詳細手順: **[web-publish/DEPLOY.md](web-publish/DEPLOY.md)**

クイック概要:

### 9-A. GitHub Pages — 最も簡単 (5 分)

```
GitHub web → Settings → Pages
Source: Deploy from a branch
Branch: main
Folder: /web-publish
Save
```

URL: `https://genarch.github.io/praxia/`

メリット: 設定 5 分、無料、GitHub と完全統合
デメリット: GitHub の CDN は地域差あり (アジアからのアクセスは遅め、200-400ms)

### 9-B. Cloudflare Pages — 国際展開向け (15 分、推奨)

国際的に最速の CDN (320+ POP) で、**完全無料 + 無制限帯域**。

```
1. https://dash.cloudflare.com/sign-up でアカウント作成 (無料)
2. Workers & Pages → Create → Pages → Connect to Git
3. genarch/praxia リポジトリを選択
4. Build settings:
     Framework preset:    None
     Build command:       (空欄)
     Build output dir:    web-publish
5. Save and Deploy
```

URL: `https://praxia.pages.dev/`

カスタムドメイン (`praxia.dev` 等) を持っているなら、Cloudflare DNS で 1 クリック設定可能。

### 9-C. Vercel — 開発体験が最高 (10 分)

```
1. https://vercel.com/signup でアカウント作成
2. Add New → Project → Import Git Repository
3. genarch/praxia を選択
4. Framework Preset: Other
5. Root Directory: web-publish
6. Deploy
```

URL: `https://praxia.vercel.app/`

メリット: プレビューデプロイ (PR ごとに自動)、解析、Edge Functions
デメリット: 無料プラン帯域 100 GB/月

### カスタムドメイン (国際展開時)

ドメインを持っているなら:
- **`praxia.dev`** (Google Domains で年 $12 程度) — 推奨
- **`praxia.ai`** (年 $80 程度)
- **`praxia.app`** (中庸)

DNS は Cloudflare に集約するのがベスト (無料 + DDoS 対策付き)。

### 推奨デプロイ戦略

| Phase | 公開先 | コスト | 国際レイテンシ |
|---|---|---|---|
| Day 1 (即時) | GitHub Pages | $0 | 中 (アジアは 200-400ms) |
| Day 7 〜 (本気で発信) | Cloudflare Pages | $0 | 低 (世界どこからでも 50ms 以下) |
| Day 30 〜 (専用ドメイン) | `praxia.dev` (CF DNS) | 年 $12 | 低 |
| Phase 3 (商業運用) | Vercel Pro / 自前 CDN | 月 $20+ | 低 |

最小工数で最大効果なら、**GitHub Pages で即時公開 → 1〜2 週間後に Cloudflare Pages 移行** が王道。

---

## ✅ Step 10: コミュニティ運営の初期セットアップ

- [ ] GitHub Discussions を有効化、`Recipe` カテゴリを作成
- [ ] Issue Template (Bug / Feature / Recipe) を `.github/ISSUE_TEMPLATE/` に追加
- [ ] PR Template を `.github/PULL_REQUEST_TEMPLATE.md` に追加
- [ ] `CODE_OF_CONDUCT.md` (Contributor Covenant 標準テキスト) を追加
- [ ] `SECURITY.md` を追加 (脆弱性報告窓口)

---

## ✅ Step 11: 発信・告知

- [ ] **Zenn** 全 7 記事を順次公開 (週 1 本ペース推奨)
- [ ] **dev.to / Medium** に英訳版を順次投稿
- [ ] **X (Twitter)** で告知
- [ ] **LinkedIn** で経営層向け投稿
- [ ] **HN Show HN** タイミング厳守 (火 8:00 AM PST)
- [ ] **Reddit** r/Python / r/MachineLearning に投稿

---

## 🚦 公開後 30 日のフォローアップ

| 期間 | やること |
|------|----------|
| Day 1〜3 | バグ報告対応、Quickstart の磨き込み |
| Week 2 | コミュニティ初期メンバーへの 1on1 |
| Week 4 | 1つ目のコミュニティ・レシピ採用 (PR マージ + 紹介ポスト) |

---

## ❌ 公開してはいけないもの

- API キー / 認証情報 (`.env` は `.gitignore` に既に含まれています)
- 顧客の機密データ・社内固有データ
- 業界特有の RAG ナレッジ (これは将来の SaaS / コンサルの切り札)
- 内部資料 (`OSS/_internal/` 配下のビジネス計画 / 戦略文書)

> 内部資料 (`business-plan.ja.md`, `adoption-strategy.ja.md`) は OSS リポジトリの外 (`OSS/_internal/`) に分離済み。git 管理する場合も別の **private** リポジトリで。
