# Praxia Evaluation Suite

> 🇯🇵 [日本語版](EVALUATION.ja.md)

Regression-prevention test suite that runs on every code change.

## What it covers

364 deterministic regression tests + 6 LLM quality tests across 12 feature areas:

| File | Area | Tests |
|---|---|---|
| `tests/test_smoke.py` | High-level smoke (always run) | 60 |
| `tests/evaluation/test_eval_auth.py` | Authentication / RBAC / ACL / audit log | ~25 |
| `tests/evaluation/test_eval_memory.py` | Memory backends + mode + admin policy | ~30 |
| `tests/evaluation/test_eval_composite.py` | Multi-LTM fusion + routing | ~30 |
| `tests/evaluation/test_eval_skills.py` | Skill registry + flows | ~15 |
| `tests/evaluation/test_eval_exporters.py` | Output exporters (md/html/pptx/docx/json) | ~30 |
| `tests/evaluation/test_eval_oauth.py` | Per-user OAuth (token store + flow) | ~15 |
| `tests/evaluation/test_eval_parsers.py` | File parsers (PDF/Office/CSV/HTML/TXT) | ~20 |
| `tests/evaluation/test_eval_cli.py` | CLI command surface | ~50 |
| `tests/evaluation/test_eval_extensions.py` | Registry + entry-point discovery | ~15 |
| `tests/evaluation/test_eval_experiments.py` | A/B experiment lifecycle + assignment + outcomes | ~17 |
| `tests/evaluation/test_eval_i18n.py` | UI i18n: 8 languages, browser detection, key completeness | ~22 |
| `tests/llm_eval/test_framework.py` | LLM eval framework self-tests (no LLM call) | ~14 |
| `tests/llm_eval/test_skill_quality.py` | LLM output quality (real API; `-m llm_eval`) | 6 |

## How to run

```bash
# All tests (smoke + evaluation)
pytest

# Evaluation only (regression suite)
pytest -m evaluation

# Smoke only (faster)
pytest tests/test_smoke.py

# One feature area
pytest tests/evaluation/test_eval_auth.py -v

# One specific test
pytest tests/evaluation/test_eval_memory.py::TestReadOnlyMode::test_set_mode_toggles_behavior -v

# Skip slow tests
pytest -m "not slow"
```

## When to run

| Trigger | What to run |
|---|---|
| Local development (every save) | `pytest tests/test_smoke.py` (~1 sec) |
| Pre-commit / pre-push | `pytest -m evaluation` (~3 sec) |
| CI pull request | All of the above |
| Pre-release | All + `pytest -m integration` (real services, opt-in) |
| Nightly | All including `-m slow` |

Recommended pre-commit hook:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest evaluation suite
        entry: pytest -m evaluation -q
        language: system
        types: [python]
        pass_filenames: false
```

## What "passing" guarantees

- **Authentication paths work** — API key issuance + verification + rotation; JWT signing + tampering detection; deactivated users cannot log in.
- **RBAC is correctly enforced** — every (role, action) pair returns the documented decision. No silent permission drift.
- **ACL precedence is preserved** — first-match-wins; principal filtering by both user_id and role.
- **Audit log is append-only** — N writes → N records, in insertion order.
- **Memory backend invariants hold** — JSONL persistence; user namespace isolation; `clear()` removes only the owner's entries.
- **read_only mode drops every write** — `record_episode / record_fact / record_outcome / record_preference` all return a no-op entry.
- **Memory policy resolution matrix** — admin enforced > call-site arg > user pref > admin default > "json"; mode lock + role lock work.
- **Multi-LTM fusion** — RRF / union / intersection / weighted / llm_rerank each produce documented orderings; one backend failing doesn't break the query; write target selection works.
- **RuleRouter** — every default rule fires for both English and Japanese keywords (16 query → backend pairs verified).
- **Output exporters** — every heading level renders; XSS escaped; bold / italic / lists / code / blockquote / links work; format inference supports JA + EN hints.
- **Optional deps gracefully skip** — PPTX / DOCX exporters are import-or-skip.
- **OAuth tokens encrypted at rest** — plaintext does not appear in on-disk JSON.
- **CLI commands all importable + `--help` exits 0** — catches typer signature drift.
- **Plugin registries auto-discover built-ins** — every plugin type's built-in count is asserted.

## How to add a new test

When you add a feature, add a test in the appropriate `test_eval_*.py`:

```python
class TestMyNewFeature:
    def test_happy_path(self, tmp_storage):
        # use tmp_storage fixture for disposable .praxia/-style dirs
        ...

    @pytest.mark.parametrize("input,expected", [
        ("case1", "result1"),
        ("case2", "result2"),
    ])
    def test_boundary_conditions(self, input, expected):
        ...
```

Available fixtures (`tests/evaluation/conftest.py`):
- `tmp_storage` — disposable `.praxia/`-style directory
- `stub_backend_factory` — builds a stub `MemoryBackend` with controllable behavior
- `make_record` — builds a `MemoryRecord` with sensible defaults

## Markers

Defined in `pyproject.toml`:

| Marker | Meaning |
|---|---|
| `evaluation` | Regression-prevention scenario (run with `-m evaluation`) |
| `integration` | Hits real external services (skipped by default) |
| `slow` | > 5 seconds (skip with `-m "not slow"`) |

## CI integration

Praxia uses GitHub Actions. Recommended `.github/workflows/test.yml`:

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

## Reading test failures

When a test fails:

1. **Read the failure name** — it's structured `<file>::<class>::<test_method>[<param>]`.
2. **Look at the assertion** — the parametrized value points to the exact case.
3. **If a registry test fails** — a built-in plugin was probably renamed.
4. **If an auth test fails** — RBAC or ACL semantics changed; review intentionality.
5. **If an exporter test fails** — Markdown → HTML rendering may have changed; visual diff the output.
6. **If a CLI test fails** — typer signature drift; re-run with `-v` to see traceback.

## Known caveats

- **Memory backend integration tests** (mem0 / zep / hindsight) require API keys and are NOT in the evaluation suite. They run under `-m integration` only.
- **LLM call tests** are deliberately excluded — every test stubs the LLM. This keeps the suite hermetic and zero-cost. Evaluating LLM output quality requires a separate framework (planned: `tests/llm_eval/`).
- **OAuth flow tests** verify URL construction and token storage but do NOT call real IdPs. End-to-end OAuth happens in `-m integration`.
