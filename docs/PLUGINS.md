# Plugin Development Guide

Praxia is built around a **single extensibility primitive** — `praxia.extensions.Registry`. All four extension points (connectors, memory backends, skills, flows) use it. Adding a plugin is the same pattern in each case:

1. Subclass the relevant base class.
2. Register it — either by decorator (in-tree) or via a Python entry-point (third-party package).

> Result: **adding a connector / backend / skill / flow does not require editing any core file**. The framework auto-discovers your plugin at startup.

---

## 1. Architecture overview

```
┌─────────────────────────────────────────────────────────┐
│  Application code (Praxia / your app)                   │
└────────────────────────┬────────────────────────────────┘
                         │ get / list / create
                         ▼
┌─────────────────────────────────────────────────────────┐
│  praxia.extensions.Registry[T]                          │
│  - direct registration (eager)                          │
│  - lazy("module:Class") (deferred import)               │
│  - @register_decorator("name")                          │
│  - entry-point auto-discovery                           │
└──────────┬─────────────┬─────────────┬─────────────┬────┘
           │             │             │             │
   ┌───────▼─┐    ┌──────▼────┐  ┌────▼─────┐  ┌────▼─────┐
   │CONNECT.│    │ BACKENDS  │  │  SKILLS  │  │  FLOWS   │
   └────────┘    └───────────┘  └──────────┘  └──────────┘
```

Each registry exposes:
- `register(name, cls_or_lazy_ref)` — manual registration
- `register_decorator(name)` — `@reg.register_decorator("foo")`
- `get(name)` — resolve to class (loads lazy refs on first call)
- `list()` — names (triggers entry-point discovery once)
- `has(name)`, `unregister(name)`, `create(name, **kwargs)` — convenience helpers

---

## 2. Adding a new connector

### Option A — In-tree (PR to praxia/connectors/)

```python
# praxia/connectors/notion.py
from praxia.connectors.base import ConnectorItem
from praxia.connectors.registry import CONNECTORS


@CONNECTORS.register_decorator("notion")
class NotionConnector:
    name = "notion"

    def __init__(self, *, token: str) -> None:
        # Lazy SDK import keeps the dep optional
        from notion_client import Client
        self._client = Client(auth=token)

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        # path = database_id
        rows = self._client.databases.query(database_id=path).get("results", [])[:limit]
        return [
            ConnectorItem(id=r["id"], name=r["id"], content=str(r), mime_type="application/json")
            for r in rows
        ]

    def push(self, path: str, data) -> dict:
        # path = parent page_id
        page = self._client.pages.create(parent={"page_id": path}, properties={...})
        return {"id": page["id"], "url": page["url"]}
```

That's it. `praxia connector list` now shows `notion`.

### Option B — Third-party package (no fork required)

In your separate package's `pyproject.toml`:

```toml
[project]
name = "praxia-connector-notion"
version = "0.1.0"
dependencies = ["praxia>=0.1", "notion-client>=2"]

[project.entry-points."praxia.connectors"]
notion = "praxia_connector_notion:NotionConnector"
```

After `pip install praxia-connector-notion`, Praxia automatically picks it up:

```bash
praxia connector list
# notion appears alongside the built-ins
praxia connector pull notion <database_id>
```

---

## 3. Adding a memory backend

Any class implementing the 4-method `MemoryBackend` protocol works:

```python
# my_pkg/pinecone_backend.py
from praxia.memory.backends.base import MemoryBackend, MemoryRecord
from praxia.memory.backends import BACKENDS

@BACKENDS.register_decorator("pinecone")
class PineconeBackend:
    def __init__(self, *, api_key: str, index_name: str) -> None:
        from pinecone import Pinecone
        self._client = Pinecone(api_key=api_key)
        self._index = self._client.Index(index_name)

    def add(self, *, user_id, text, kind, metadata) -> MemoryRecord: ...
    def search(self, *, user_id, query, limit) -> list[MemoryRecord]: ...
    def all(self, *, user_id=None) -> list[MemoryRecord]: ...
    def clear(self, *, user_id=None) -> None: ...
```

Or via entry-point:

```toml
[project.entry-points."praxia.memory_backends"]
pinecone = "my_pkg.pinecone_backend:PineconeBackend"
```

Use it:

```python
from praxia import PersonalMemory
pm = PersonalMemory(user_id="alice", backend="pinecone", api_key="...", index_name="praxia")
```

---

## 4. Adding a business skill

```python
# my_pkg/hr_recruiting.py
from praxia.skills import SKILLS
from praxia.skills.skill import Skill, SkillManifest


@SKILLS.register_decorator("hr_recruiting")
class HRRecruitingSkill(Skill):
    manifest = SkillManifest(
        name="hr_recruiting",
        description="Resume screening + interview question generation",
        domain="hr",
        tags=["recruiting", "screening"],
    )
    system_prompt = """You are an HR recruiting specialist..."""
```

Or entry-point:

```toml
[project.entry-points."praxia.skills"]
hr_recruiting = "my_pkg.hr_recruiting:HRRecruitingSkill"
```

Use it:

```bash
praxia skill run hr_recruiting "screen this resume: ..."
```

---

## 5. Adding a flow

```python
# my_pkg/incident_response.py
from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM
from praxia.flows import FLOWS


@FLOWS.register_decorator("incident_response_flow")
class IncidentResponseFlow(Flow):
    name = "incident_response_flow"
    description = "Triage → root cause → mitigation"

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()
        self.steps = [
            FlowStep(name="triage", agent=Agent("triage", llm=llm,
                     system_prompt="..."), inputs={"alert": "${alert}"}),
            FlowStep(name="hypothesis", agent=Agent("hypothesis", llm=llm,
                     system_prompt="..."), inputs={"triage": "${triage}"}),
            FlowStep(name="mitigation", agent=Agent("mitigation", llm=llm,
                     system_prompt="..."), inputs={"hypothesis": "${hypothesis}"}),
        ]
```

Or entry-point:

```toml
[project.entry-points."praxia.flows"]
incident_response = "my_pkg.incident_response:IncidentResponseFlow"
```

Use it:

```bash
praxia run incident_response --alert "..."
```

---

## 6. The full extension-point matrix

| Plugin type | Base class / protocol | Registry | Entry-point group |
|---|---|---|---|
| **Connector** | `praxia.connectors.base.Connector` (Protocol) | `CONNECTORS` | `praxia.connectors` |
| **Memory backend** | `praxia.memory.backends.base.MemoryBackend` (Protocol) | `BACKENDS` | `praxia.memory_backends` |
| **Skill** | `praxia.skills.skill.Skill` | `SKILLS` | `praxia.skills` |
| **Flow** | `praxia.core.flow.Flow` | `FLOWS` | `praxia.flows` |

---

## 7. Distribution

The standard way to ship a Praxia plugin is a **separate Python package** (e.g. `praxia-connector-notion`). This:

- Lets users install only the integrations they need
- Keeps optional SDKs out of Praxia core dependencies
- Allows independent versioning + release cadence

Example minimum `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "praxia-connector-notion"
version = "0.1.0"
description = "Notion connector for Praxia"
requires-python = ">=3.11"
dependencies = ["praxia>=0.1", "notion-client>=2"]

[project.entry-points."praxia.connectors"]
notion = "praxia_connector_notion:NotionConnector"

[tool.hatch.build.targets.wheel]
packages = ["praxia_connector_notion"]
```

Publish to PyPI, then anyone can:

```bash
pip install praxia-connector-notion
```

…and use `notion` from the CLI / SDK / UI immediately.

---

## 8. Testing your plugin

```python
def test_my_connector_registers() -> None:
    from praxia.connectors.registry import CONNECTORS
    # Forces entry-point discovery
    assert "notion" in CONNECTORS.list()


def test_my_connector_works() -> None:
    from praxia.connectors import get_connector
    conn = get_connector("notion", token="test-token")
    items = conn.pull("test-database-id", limit=5)
    assert isinstance(items, list)
```

---

## 9. FAQ

**Q: Do I need to fork Praxia to ship a plugin?**
No. Use a separate package + entry-points.

**Q: Will my plugin work in the Streamlit UI?**
Yes. The UI iterates registries dynamically; your plugin shows up alongside built-ins.

**Q: Can a plugin have its own configuration / env vars?**
Yes. The connector CLI passes through any `PRAXIA_CONN_<NAME>_<KEY>` env vars
to the constructor.

**Q: How do I unregister a plugin (e.g. for testing)?**
`CONNECTORS.unregister("name")` — handy in test cleanup. To force entry-point
re-discovery, call `CONNECTORS.reset_discovery()`.

**Q: What if two plugins register under the same name?**
The later registration wins, with a warning. In-code registrations precede
entry-point discovery.

**Q: How are policies (ACL) applied to my custom connector?**
Automatically — `praxia connector pull/push` routes through
`AuthManager.policies.require()` regardless of which connector you registered.

---

## 10. Officially supported plugins (planned)

These will live in separate repos and be installable as separate PyPI packages:

| Plugin | Status |
|---|---|
| `praxia-connector-notion` | 📋 Planned |
| `praxia-connector-confluence` | 📋 Planned |
| `praxia-connector-slack` | 📋 Planned |
| `praxia-connector-jira` | 📋 Planned |
| `praxia-connector-gmail` | 📋 Planned |
| `praxia-backend-pinecone` | 📋 Planned |
| `praxia-backend-weaviate` | 📋 Planned |
| `praxia-backend-qdrant` | 📋 Planned |
| `praxia-skills-medical` | 📋 Planned |
| `praxia-skills-construction` | 📋 Planned |

Community contributions welcome.
