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

Contribution は **Apache License 2.0** として配布されます。

---

## Developer Certificate of Origin (DCO) — 必須

Praxia は **DCO 方式** を採用しています (Linux カーネル / Docker と同方式)。
個別 CLA への署名は不要ですが、すべてのコミットに `Signed-off-by:` 行を含める必要があります。

### DCO とは

`Signed-off-by:` を付けることで、あなたは [Developer Certificate of Origin v1.1](https://developercertificate.org/) に同意したことになります。要約:

1. その contribution は **あなた自身の作成物** であるか、適切なライセンス下にあり貢献する権利がある
2. その contribution は **オープンソースライセンス下で配布される事を承知** している
3. その contribution は **公開記録に永続化** されることを承知している
4. 提出した情報 (氏名 / email など) は **公開** される

### Sign-off の方法

```bash
# 個別コミット時
git commit -s -m "feat: my contribution"

# 既存コミットを sign-off で書き直し
git commit --amend -s

# 既に複数コミットある場合
git rebase -i HEAD~N --signoff
```

`-s` フラグでコミットメッセージ末尾に以下が自動付与されます:

```
Signed-off-by: あなたの名前 <your@email.com>
```

`git config user.name` と `user.email` が **本人確認可能な名前 + email** であることを確認してください (匿名・偽名による sign-off は無効)。

### CI による検証

PR ごとに CI が `Signed-off-by:` の有無を確認します。未 sign-off コミットは PR がマージブロックされます。

### CLA ではなく DCO を採用する理由

| 観点 | DCO | CLA |
|---|---|---|
| 寄稿者の手続き負荷 | コミット毎の `-s` だけ | 別途 CLA 文書に署名 |
| 法的明確性 | 業界実績多数 (Linux, Docker, Node.js, Kubernetes 等) | 同等またはより詳細 |
| 著作権の帰属 | 寄稿者保持 | 通常はプロジェクト側へ譲渡または広範ライセンス |
| 将来のライセンス変更柔軟性 | 寄稿者全員の合意必要 (Apache 2.0 を維持する限り問題なし) | プロジェクトオーナー単独で可能 |
| 寄稿者からの信頼 | 高い (寄稿者主権) | やや低い (権利譲渡を要求) |

Praxia は **Apache 2.0 を恒久的に維持** する方針のため、DCO で十分です。将来的に open-core モデル (有償エンタープライズ機能を別ライセンスで配布) を採用する場合でも、Apache 2.0 のコア部分は維持されます。

### 署名済みコミット例

```
feat(memory): add CompositeBackend for multi-LTM fusion

CompositeBackend fans out queries across N backends in parallel and
merges results via Reciprocal Rank Fusion. One backend failing is
non-fatal.

Signed-off-by: Jane Smith <jane@example.com>
```

---

## 商標について

「Praxia」名称・ロゴは GenArch の商標です。プラグインの命名規則
(`praxia-connector-<name>` 等) とフォーク改名の方針は
[`docs/legal/TRADEMARK.ja.md`](docs/legal/TRADEMARK.ja.md) を参照してください。
コード自体の自由な fork / 改変 / 再配布は Apache 2.0 で保証されます。

## プライバシーについて

PR で扱うデータが個人情報を含む場合、[`docs/legal/GDPR_NOTES.ja.md`](docs/legal/GDPR_NOTES.ja.md)
の指針を参照してください。テストフィクスチャに実在の個人データ (実 email,
実顧客名等) を含めないでください — `tests/evaluation/` の架空データ規約を
踏襲します。
