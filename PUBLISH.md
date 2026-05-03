# 公開チェックリスト

GitHub に公開する前の確認事項です。順番に進めてください。

## ✅ Step 1: ローカル動作確認

```bash
cd OSS/agentloom

# 依存関係インストール (開発モード + 全エクストラ)
pip install -e ".[all]"

# テスト実行
pytest -q

# Lint / 型チェック
ruff check .
mypy agentloom
```

**期待結果**: テスト全件 PASS、ruff/mypy 警告ゼロ。

---

## ✅ Step 2: API キー設定 (任意・実機テスト時)

```bash
cp .env.example .env
# .env を編集して、利用したいプロバイダのキーをひとつ設定:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
#   GEMINI_API_KEY=...
#   DASHSCOPE_API_KEY=...      (Qwen)
```

ローカル Qwen を試したい場合:
```bash
ollama pull qwen2.5:14b
agentloom run sales --model qwen-local --customer-name "Acme" --product "BizFlow"
```

---

## ✅ Step 3: README の組織名置換

[README.md](README.md), [docs/zenn_article_draft.md](docs/zenn_article_draft.md), [pyproject.toml](pyproject.toml) 内の `your-org` を実際の GitHub 組織名 / ユーザ名に置換:

```bash
# 例: your-org → genki-watanabe
grep -rl "your-org" .
# 表示されたファイルを順に編集
```

---

## ✅ Step 4: GitHub リポジトリ作成

```bash
# このディレクトリで git 履歴は初期化済み (PUBLISH.md の最終行参照)

# GitHub 上にリポジトリ作成 (gh CLI 使用)
gh repo create agentloom --public --source=. --description "Specialized multi-agent orchestrator with cyclic personal/organizational memory" --push

# または手動で:
#   1. GitHub.com で agentloom リポジトリを作成 (空)
#   2. git remote add origin git@github.com:<your-org>/agentloom.git
#   3. git push -u origin main
```

---

## ✅ Step 5: 公開設定

| 項目 | 推奨設定 |
|------|----------|
| Description | `Specialized multi-agent orchestrator with cyclic personal/organizational memory` |
| Topics | `ai`, `llm`, `agent`, `multi-agent`, `rag`, `memory`, `python`, `mem0`, `claude`, `qwen` |
| License | Apache License 2.0 (GitHub UI で確認) |
| Issues | Enabled |
| Discussions | Enabled (コミュニティ・レシピ募集用) |

---

## ✅ Step 6: 初回 Release を切る

```bash
git tag v0.1.0a0 -m "Alpha release"
git push origin v0.1.0a0
gh release create v0.1.0a0 --title "v0.1.0a0 — Alpha" --notes "Initial alpha release. See README.md for features."
```

---

## ✅ Step 7: PyPI に公開 (任意)

PyPI トークンを設定済みの場合:
```bash
pip install build twine
python -m build
twine upload dist/*
```

---

## ✅ Step 8: Zenn / X / note で発信

[docs/zenn_article_draft.md](docs/zenn_article_draft.md) をベースに記事を投稿:

- **Zenn**: `published: false` を `published: true` に変更してから push
- **X (Twitter)**: 「特化型マルチエージェント・オーケストレーター + 個人→組織メモリ自動循環」を訴求
- **note**: ビジネス読者向けに、課題解決ストーリーと収益モデル（オープンコア）を強調

訴求のキーフレーズ案:
- 「ベテランの暗黙知が組織知になる OSS」
- 「Reasoning Engineer のための Multi-Agent OSS」
- 「Mem0 × Sleep-time × Shared Blocks の決定版」

---

## ✅ Step 9: コミュニティ運営の初期セットアップ

- [ ] GitHub Discussions を有効化、`Recipe` カテゴリを作成
- [ ] Issue Template (Bug / Feature / Recipe) を `.github/ISSUE_TEMPLATE/` に追加
- [ ] PR Template を `.github/PULL_REQUEST_TEMPLATE.md` に追加
- [ ] `CODE_OF_CONDUCT.md` (Contributor Covenant 標準テキスト) を追加

---

## 🚦 公開後 30 日のフォローアップ

| 期間 | やること |
|------|----------|
| Day 1〜3 | バグ報告対応、Quickstart の磨き込み |
| Week 2 | RAG-1 グランプリ実績と紐づけて X / Zenn で再発信 |
| Week 4 | 1つ目のコミュニティ・レシピ採用 (PR マージ + 紹介ポスト) |

---

## ❌ 公開してはいけないもの

- API キー / 認証情報 (`.env` は `.gitignore` に既に含まれています)
- 顧客の機密データ・社内固有データ
- ご自身が苦労して集めた業界特有の RAG ナレッジ (これは将来の SaaS / コンサルの切り札)
- 超高精度なプロンプトの最終版 (汎用ロジックのみ公開)

詳細は OSS 検討メモの「公開時の注意点」を参照。
