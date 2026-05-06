# Praxia 評価スイート

> 🇬🇧 [English](EVALUATION.md)

コード変更ごとに実行する **デグレ防止テストスイート**。

## カバー範囲

13 機能領域、431 テスト + 6 LLM 品質テスト:

| ファイル | 領域 | テスト数 |
|---|---|---|
| `tests/test_smoke.py` | 高水準スモーク (常時実行) — LLM alias 解決 / auto_detect 優先順位 含む | 65 |
| `tests/evaluation/test_eval_auth.py` | 認証 / RBAC / ACL / 監査ログ | ~25 |
| `tests/evaluation/test_eval_memory.py` | メモリバックエンド + モード + 管理者ポリシー | ~30 |
| `tests/evaluation/test_eval_composite.py` | 複数 LTM 融合 + ルーティング | ~30 |
| `tests/evaluation/test_eval_skills.py` | スキルレジストリ + フロー | ~15 |
| `tests/evaluation/test_eval_agent.py` | **AutonomousAgent** ループ + ツール ACL + 監査 + max_steps | 13 |
| `tests/evaluation/test_eval_exporters.py` | 出力エクスポータ (md/html/pptx/docx/json) | ~30 |
| `tests/evaluation/test_eval_oauth.py` | ユーザ委譲 OAuth (トークンストア + フロー) | ~15 |
| `tests/evaluation/test_eval_parsers.py` | ファイルパーサ (PDF/Office/CSV/HTML/TXT) | ~20 |
| `tests/evaluation/test_eval_cli.py` | CLI コマンド表面 | ~50 |
| `tests/evaluation/test_eval_extensions.py` | Registry + entry-point 検出 | ~15 |
| `tests/evaluation/test_eval_experiments.py` | A/B 実験 ライフサイクル + 割当 + 結果 | ~17 |
| `tests/evaluation/test_eval_i18n.py` | UI i18n: 8 言語 / ブラウザ検出 / キー網羅 | ~22 |
| `tests/llm_eval/test_skill_quality.py` | LLM 出力品質 (実 API、`-m llm_eval`) | 6 |

## 実行方法

```bash
# 全テスト (smoke + evaluation)
pytest

# 評価のみ (デグレ防止)
pytest -m evaluation

# スモークのみ (高速)
pytest tests/test_smoke.py

# 1 機能領域のみ
pytest tests/evaluation/test_eval_auth.py -v

# 特定テストのみ
pytest tests/evaluation/test_eval_memory.py::TestReadOnlyMode::test_set_mode_toggles_behavior -v

# 遅いテストをスキップ
pytest -m "not slow"
```

## 実行タイミング

| トリガ | 推奨実行 |
|---|---|
| ローカル開発 (保存毎) | `pytest tests/test_smoke.py` (~1 秒) |
| pre-commit / pre-push | `pytest -m evaluation` (~3 秒) |
| CI プルリクエスト | 上記全て |
| リリース前 | 上記 + `pytest -m integration` (実サービス、opt-in) |
| 夜間 | 全て (`-m slow` 含む) |

推奨 pre-commit hook:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest 評価スイート
        entry: pytest -m evaluation -q
        language: system
        types: [python]
        pass_filenames: false
```

## 「合格」が保証する事項

- **認証経路が動作する** — API キー発行 + 検証 + ローテート / JWT 署名 + 改ざん検出 / 無効化済ユーザはログイン不可
- **RBAC が正しく強制される** — (role, action) の全ペアが文書通りの判定を返す。サイレントな権限ドリフト無し
- **ACL の優先順位が保たれる** — first-match-wins / user_id と role 両方で principal フィルタ
- **監査ログは append-only** — N 件書込 → N 件記録、挿入順を維持
- **メモリバックエンドの不変条件** — JSONL 永続化 / ユーザネームスペース分離 / `clear()` は所有者のみ削除
- **read_only モードは全 write を drop** — `record_episode / record_fact / record_outcome / record_preference` 全て no-op エントリを返却
- **メモリポリシー解決マトリクス** — admin enforced > 呼出引数 > user pref > admin default > "json" / mode lock + role lock も動作
- **複数 LTM 融合** — RRF / union / intersection / weighted / llm_rerank の各々が文書通りの順序を返す / 1 backend 失敗で全体が止まらない / 書込先選択も動作
- **RuleRouter** — 既定ルール全てが英語と日本語両方のキーワードに反応 (16 クエリ → backend 組合せ検証済)
- **出力エクスポータ** — 全見出しレベルがレンダリング / XSS エスケープ / bold / italic / list / code / blockquote / link 動作 / 形式判定が日英両対応
- **任意依存の優雅なスキップ** — PPTX / DOCX エクスポータは import-or-skip
- **OAuth トークン暗号化保管** — 平文がディスク上 JSON に現れない
- **CLI コマンドが全て import 可能 + `--help` exit 0** — typer シグネチャドリフト捕捉
- **プラグインレジストリの自動検出** — 各プラグインタイプの組込数を assert

## テスト追加手順

機能追加時、対応する `test_eval_*.py` にテストを追加:

```python
class TestMyNewFeature:
    def test_happy_path(self, tmp_storage):
        # tmp_storage fixture で使い捨て .praxia/ 風ディレクトリ取得
        ...

    @pytest.mark.parametrize("input,expected", [
        ("case1", "result1"),
        ("case2", "result2"),
    ])
    def test_boundary_conditions(self, input, expected):
        ...
```

利用可能 fixture (`tests/evaluation/conftest.py`):
- `tmp_storage` — 使い捨て `.praxia/` 風ディレクトリ
- `stub_backend_factory` — 制御可能挙動の `MemoryBackend` スタブ
- `make_record` — 妥当なデフォルト付き `MemoryRecord` 生成

## マーカー

`pyproject.toml` 定義:

| マーカー | 意味 |
|---|---|
| `evaluation` | デグレ防止シナリオ (`-m evaluation` で実行) |
| `integration` | 実外部サービスに接続 (既定スキップ) |
| `slow` | 5 秒超 (`-m "not slow"` でスキップ) |

## CI 統合

Praxia は GitHub Actions を利用。推奨 `.github/workflows/test.yml`:

```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: pip install -e ".[dev,office,connectors,server]"
      - run: pytest -q --tb=short
```

## テスト失敗の読み方

失敗時の手順:

1. **失敗名を読む** — 構造は `<file>::<class>::<test_method>[<param>]`
2. **assertion を確認** — parametrize 値が具体的なケースを指す
3. **registry テスト失敗** — 組込プラグイン名が変更された可能性
4. **auth テスト失敗** — RBAC / ACL の意味論変更 / 意図性をレビュー
5. **exporter テスト失敗** — Markdown → HTML レンダリング変更 / 出力を visual diff
6. **CLI テスト失敗** — typer シグネチャドリフト / `-v` で trace 確認

## 既知の制約

- **メモリバックエンド統合テスト** (mem0 / zep / hindsight) は API キーが必要なため評価スイートに**含めない**。`-m integration` でのみ実行
- **LLM 呼出テスト**は意図的に除外 — 全テストが LLM をスタブ化。これによりスイートは hermetic + ゼロコスト。LLM 出力品質評価は別フレームワーク必要 (計画: `tests/llm_eval/`)
- **OAuth フローテスト**は URL 構築 + トークン保管を検証するが**実 IdP には呼出さない**。E2E は `-m integration` で実行
