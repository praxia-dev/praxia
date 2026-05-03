# Contributing to Praxia

ご興味ありがとうございます! Praxia は **業界別レシピ** のコミュニティ駆動の蓄積を目指しています。

## 受け入れる Contribution の種類

### 1. 新しい業務フロー (`praxia/flows/`)
特定の業務 (購買承認 / 障害対応 / コードレビュー …) に特化した
マルチエージェント・フローを `Flow` のサブクラスとして追加。

### 2. 新しいビジネススキル (`praxia/skills/business/`)
特定ドメインの専門知識を持つエージェントを `Skill` のサブクラスとして追加。
既存の 6 つ (投資/営業/設計/購買/特許/法務) を参考に。

### 3. 業界レシピ (`docs/recipes/`)
「製造業 / 電子部品 / 課題抽出」など、業種 × シナリオごとの
プロンプト・パイプライン構成・期待効果を Markdown で投稿。

### 4. LTM バックエンド (`praxia/memory/backends/`)
新しい LTM プロダクト (Pinecone / Weaviate / Vector DB等) のアダプタ。

### 5. バグ報告 / ドキュメント改善
GitHub Issues に。

## 開発手順

```bash
git clone https://github.com/your-org/praxia.git
cd praxia
pip install -e ".[all]"
pytest                          # テスト実行
ruff check . && mypy praxia  # 静的解析
```

## Pull Request チェックリスト

- [ ] `ruff check .` が通る
- [ ] `mypy praxia` が通る
- [ ] テストを追加 (`tests/`)
- [ ] ドキュメント更新 (`docs/` または該当モジュールの docstring)
- [ ] 主要な設計決定は ADR (`docs/adr/`) に追加

## 行動規範

- 建設的な議論のみ。Personal attack 禁止
- Contribution の機会を全員に開く
- 業界別レシピは PII / 機密情報を除去してから提出

## ライセンス

Contribution は Apache License 2.0 として配布されます。
