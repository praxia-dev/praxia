# Building a custom connector

> 🇯🇵 日本語版: [CUSTOM_CONNECTORS.ja.md](CUSTOM_CONNECTORS.ja.md)

Praxia ships connectors for Box, SharePoint/OneDrive, Dropbox, Google Drive, kintone, and Salesforce. When the system you need isn't on that list, you write a small Python class that satisfies the `Connector` protocol — Praxia does the rest (registry, OAuth, ACL enforcement, audit logging).

This guide walks through it end-to-end with a working example.

---

## 1. The contract

Every connector implements two methods:

```python
class Connector(Protocol):
    name: str

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """Read items from `path` (a folder ID, query, table name, etc.)."""

    def push(self, path: str, data: ConnectorItem | dict) -> dict:
        """Write `data` to `path`. Returns a provider-specific receipt."""
```

`ConnectorItem` is a tiny dataclass:

```python
@dataclass
class ConnectorItem:
    id: str
    name: str
    content: str | bytes
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = field(default_factory=dict)
```

Anything that can produce / consume those is a valid connector.

---

## 2. Walkthrough — a Notion connector

Suppose your team uses Notion and you want flow inputs (`pull`) and skill outputs (`push`).

### 2.1 Project layout

You can develop in-tree (inside a fork of Praxia) or as a separate package. **The separate-package path is recommended** because you can publish + update independently.

```
praxia-connector-notion/
├── pyproject.toml
└── src/
    └── praxia_connector_notion/
        ├── __init__.py
        └── notion_connector.py
```

### 2.2 Minimum-viable implementation

```python
# src/praxia_connector_notion/notion_connector.py
from __future__ import annotations

from typing import Any

from praxia.connectors.base import (
    Connector,           # Protocol — for type hints
    ConnectorItem,
    MissingDependencyError,
    _require,
)


class NotionConnector:
    name = "notion"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        user_id: str | None = None,
    ) -> None:
        # 1) Defer SDK import so users without notion-client can still
        #    `pip install` the package without errors.
        notion_client = _require("notion_client", "pip install notion-client")

        # 2) User-delegated OAuth path: pull the user's saved token if no
        #    explicit api_key is provided. This honors the same per-user
        #    encrypted token store that Praxia uses for Box / Google / etc.
        if user_id and not api_key:
            from praxia.connectors.oauth import oauth_token_for
            tok = oauth_token_for(user_id, "notion")
            api_key = tok.access_token

        if not api_key:
            raise ValueError(
                "Provide api_key or user_id (with a stored OAuth token)"
            )

        self._client = notion_client.Client(auth=api_key)

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is a Notion database ID."""
        results = self._client.databases.query(database_id=path, page_size=limit)
        out: list[ConnectorItem] = []
        for page in results.get("results", []):
            title = self._extract_title(page)
            content = self._page_to_markdown(page)
            out.append(
                ConnectorItem(
                    id=page["id"],
                    name=title,
                    content=content,
                    mime_type="text/markdown",
                    metadata={"notion_url": page.get("url"), "kind": "database_row"},
                )
            )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """`path` is a parent page or database ID."""
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        # Minimal: create a child page under `path`
        result = self._client.pages.create(
            parent={"page_id": path},
            properties={"title": [{"text": {"content": data.name}}]},
            children=self._markdown_to_blocks(str(data.content)),
        )
        return {"id": result["id"], "url": result.get("url")}

    # --- helpers (skeletons; real implementation is more involved) ---------

    @staticmethod
    def _extract_title(page: dict) -> str: ...
    @staticmethod
    def _page_to_markdown(page: dict) -> str: ...
    @staticmethod
    def _markdown_to_blocks(md: str) -> list[dict]: ...
```

That's the whole connector. **Roughly 50 lines** for the core; the helpers are where the actual translation work lives.

### 2.3 Register via entry-point (zero-edit to Praxia core)

```toml
# pyproject.toml
[project]
name = "praxia-connector-notion"
version = "0.1.0"
dependencies = [
    "praxia>=1.0",
    "notion-client>=2.0",
]

[project.entry-points."praxia.connectors"]
notion = "praxia_connector_notion.notion_connector:NotionConnector"
```

After `pip install praxia-connector-notion` (or `pip install -e .` for dev), Praxia auto-discovers it:

```bash
praxia connector list
# → notion appears alongside box / dropbox / ...
```

```python
from praxia.connectors import get_connector
notion = get_connector("notion", user_id="alice")
items = notion.pull("a1b2c3...notion-db-id...", limit=20)
```

### 2.4 Per-user OAuth integration (optional but recommended)

If your service supports OAuth 2.0, register a provider config so Praxia handles the authorize → callback → encrypted-token-store flow:

```python
# src/praxia_connector_notion/oauth.py
from praxia.connectors.oauth import OAuthProviderConfig

NOTION_OAUTH = OAuthProviderConfig(
    name="notion",
    authorize_url="https://api.notion.com/v1/oauth/authorize",
    token_url="https://api.notion.com/v1/oauth/token",
    default_scopes=[],         # Notion uses scopeless OAuth
    response_type="code",
    auth_method="basic",       # client_id:client_secret in HTTP Basic
)
```

Then expose the registration:

```python
# src/praxia_connector_notion/__init__.py
from praxia.connectors.oauth import register_provider
from praxia_connector_notion.oauth import NOTION_OAUTH

register_provider(NOTION_OAUTH)
```

Add to your `pyproject.toml`:

```toml
[project.entry-points."praxia.oauth_providers"]
notion = "praxia_connector_notion:NOTION_OAUTH"
```

Users now get the full flow:

```bash
praxia oauth start notion --user-id alice
# opens https://api.notion.com/v1/oauth/authorize?... → user authorizes →
# token saved encrypted under .praxia/oauth/alice/notion.json
```

When `NotionConnector(..., user_id="alice")` runs, the saved token is loaded automatically. Token refresh is handled by the OAuth core if the provider returns a `refresh_token`.

---

## 3. ACL & audit log integration

The connector itself doesn't need to know about ACL — Praxia's `PolicyManager` evaluates `connector:<name>:<path>` resources before any pull / push. To respect that:

1. **Use stable, predictable resource IDs.** `box:0/Confidential/q3.pdf` is good; `box:abcd1234random` is harder for admins to write policies against.
2. **Audit log entries are emitted automatically** by the orchestrator when the connector is invoked through `Praxia.run_flow()`. If you call `connector.pull()` directly, log it yourself:

```python
from praxia.auth import AuthManager
auth = AuthManager()
auth.audit.write(
    actor_id="alice",
    action="connector.pull",
    resource=f"notion:{path}",
    success=True,
    metadata={"item_count": len(items)},
)
```

---

## 4. Error handling — what to raise

| Situation | What to raise | Why |
|---|---|---|
| SDK not installed | `MissingDependencyError` (use `_require()`) | Clean install hint for the user |
| Wrong / missing credentials | `ValueError` with explicit fix | Surfaced to the CLI / UI as a 400 |
| External API rate-limited | Standard exception, let it bubble | The orchestrator may retry |
| Bad input (e.g. empty path) | `ValueError` | Distinguishes user error from infra error |
| Permission denied at provider | `PermissionError` | Mapped to HTTP 403 by the server module |

---

## 5. Testing your connector

The test pattern Praxia uses (from `tests/test_smoke.py`):

```python
def test_notion_connector_missing_dep_raises_clear_error():
    """If notion-client isn't installed, the error message tells you how to fix it."""
    from praxia_connector_notion.notion_connector import NotionConnector
    from praxia.connectors.base import MissingDependencyError

    try:
        NotionConnector(api_key="dummy")
    except (MissingDependencyError, ImportError) as e:
        assert "notion-client" in str(e).lower()
```

For integration tests against the real provider:

1. Use a sandbox / test workspace.
2. Store credentials in `~/.praxia-test-secrets.env` (never commit).
3. Mark tests with `@pytest.mark.integration` so CI skips them by default.

---

## 6. Publishing checklist

Before pushing your package to PyPI:

- [ ] `name` field in `pyproject.toml` follows `praxia-connector-<service>` convention.
- [ ] Entry-point declared in `[project.entry-points."praxia.connectors"]`.
- [ ] License is compatible with Apache 2.0 (e.g., MIT, BSD, Apache).
- [ ] `pull()` and `push()` both implemented (push can `raise NotImplementedError("read-only connector")` if appropriate).
- [ ] User-delegated OAuth path works, **OR** README explains why a service-account-style auth is required.
- [ ] Unit test for the missing-SDK path (so users without the dep get a clear error).
- [ ] README points back to this guide and documents the `pull()` / `push()` `path` semantics for your service.
- [ ] Versioned & tagged in git.

To get listed on the [praxia.dev/plugins] page:
1. Tag the GitHub repo with topic `praxia-connector`.
2. Open a PR against the main Praxia repo adding your package to `docs/PLUGINS.md`.

---

## 7. Pattern recap

| Step | What you write | What Praxia gives you |
|---|---|---|
| 1 | A class with `name`, `pull()`, `push()` | Connector protocol + `ConnectorItem` |
| 2 | `_require(...)` in `__init__` for the SDK | Clean install hints |
| 3 | Optional: `OAuthProviderConfig` | Per-user encrypted token store + refresh |
| 4 | `pyproject.toml` entry-points | Auto-discovery (no edit to Praxia core) |
| 5 | Unit + integration tests | The test pattern above |
| 6 | `pip install` from PyPI | Praxia handles registry, ACL, audit logging |

The same pattern works for **any** plugin point in Praxia — connectors, memory backends, file parsers, output exporters, OAuth providers, skills, flows. The single primitive is `praxia.extensions.Registry`. See [PLUGINS.md](PLUGINS.md) for the full extension architecture.
