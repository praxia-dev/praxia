# Praxia — Detailed Design Specification

> Status: **v1.0** · 🇯🇵 [日本語版](detailed-design.ja.md)

This document covers module-level class designs, sequence diagrams for cross-cutting flows, data structures, error handling, and concurrency. Read this when extending Praxia or debugging cross-module behavior.

---

## 1. Package layout

```
praxia/
├── __init__.py          # Re-exports the public API (Praxia, LLM, PersonalMemory, ...)
├── config.py            # PraxiaConfig — unified key resolution
├── core/
│   ├── llm.py           # LLM, ProviderConfig, LLMResponse (with tool_calls), DEFAULT_ALIASES (27 entries)
│   ├── agent.py         # Agent (single-turn LLM invocation)
│   └── orchestrator.py  # Praxia (top-level facade)
├── agent/               # AutonomousAgent — LLM-driven tool-use loop
│   ├── __init__.py
│   ├── autonomous.py    # AutonomousAgent
│   ├── result.py        # AgentResult, ToolCallTrace
│   └── tools.py         # AgentTool + 11 built-in tools (memory/skills/connectors/frozen)
├── flows/               # FlowResult, Flow, built-in flows
├── skills/
│   ├── skill.py             # Skill, SkillManifest
│   ├── registry.py          # SkillRegistry (personal / org / distributed scopes)
│   ├── prompts.py           # PromptStore (3 scopes)
│   ├── output_format.py     # OutputFormatSkill
│   ├── prompt_designer.py   # PromptDesignerSkill
│   ├── document_designer/   # Code-gen designers (Claude-Skills-style)
│   │   ├── sandbox.py       # AST allowlist + subprocess sandbox
│   │   ├── theme.py         # DocumentTheme, ThemeStore (.praxia/themes/)
│   │   ├── codegen.py       # shared meta-prompt + retry loop
│   │   ├── pptx_designer.py # PptxDesignerSkill
│   │   └── docx_designer.py # DocxDesignerSkill
│   └── business/            # 6 default domain skills
├── memory/
│   ├── personal.py      # PersonalMemory + MemoryEntry + MemoryMode
│   ├── shared.py        # SharedMemory (Letta-style blocks)
│   ├── markdown_store.py # Layer-4 frozen Markdown
│   ├── consolidator.py  # SleepTimeConsolidator
│   ├── promoter.py      # PromotionEngine, PromotionVerdict
│   ├── policy.py        # MemoryAdminPolicy, MemoryUserPreference, resolve_memory_config
│   ├── composite.py     # CompositeBackend, WeightedBackend (multi-LTM fusion)
│   ├── router.py        # RuleRouter, LLMRouter, RoutedBackend, RouteDecision
│   └── backends/
│       ├── base.py      # MemoryBackend protocol, MemoryRecord
│       ├── json_backend.py
│       ├── mem0_backend.py        (lazy)
│       ├── langmem_backend.py     (lazy)
│       ├── letta_backend.py       (lazy)
│       ├── zep_backend.py         (lazy)
│       └── hindsight_backend.py   (lazy)
├── auth/
│   ├── manager.py       # AuthManager
│   ├── audit.py         # AuditLog (append-only JSONL)
│   ├── policy.py        # PolicyManager (resource ACL)
│   ├── exports.py       # AdminExporter
│   ├── sso.py           # OIDC providers
│   └── users.py         # User, Role, UserStore
├── connectors/
│   ├── base.py          # Connector protocol, ConnectorItem, MissingDependencyError
│   ├── registry.py      # CONNECTORS registry
│   ├── box.py / sharepoint.py / dropbox_.py / gdrive.py / kintone.py / salesforce.py
│   └── oauth/
│       ├── flow.py      # OAuthFlow + PKCE
│       ├── token_store.py # OAuthTokenStore (envelope-encrypted via KMS)
│       ├── state_store.py # PersistentStateStore (multi-worker safe)
│       ├── kms.py       # KmsAdapter + 5 implementations (local/aws/azure/gcp/vault)
│       └── providers.py # 5 pre-registered OAuth providers
├── io/
│   ├── parsers/         # PDF / Office / CSV / HTML / TXT / MD / structured
│   ├── audio/           # STT, TTS
│   └── exporters/       # md, html, json, pptx, docx
├── eval/                # Hallucination detection, retrieval metrics
├── analytics/           # Dashboard, usage stats
├── experiments/         # A/B variant assignment + outcome rollup
│   ├── __init__.py
│   └── framework.py     # Experiment, Variant, ExperimentRegistry, results()
├── extensions.py        # Registry, lazy()
├── cli/main.py          # Typer-based CLI
├── ui/                  # Streamlit UI (mode A)
└── server/              # FastAPI HTTP server (mode B)
```

---

## 2. Core domain model

### 2.1 `Praxia` (orchestrator facade)

```python
class Praxia:
    def __init__(
        self,
        *,
        user_id: str = "default",
        org_id: str = "default",
        llm: LLM | None = None,
        config: PraxiaConfig | None = None,
        memory_dir: Path = Path(".praxia"),
        enable_shared_memory: bool = True,
    ) -> None: ...

    @property
    def llm(self) -> LLM: ...
    @property
    def personal_memory(self) -> PersonalMemory: ...
    @property
    def shared_memory(self) -> SharedMemory | None: ...
    @property
    def auth(self) -> AuthManager: ...

    def run_flow(self, name: str, inputs: dict) -> FlowResult: ...
    def run_skill(self, name: str, input: str, **kwargs) -> str: ...
```

Side effects on every `run_*` call:
1. Resolve `MemoryAdminPolicy + MemoryUserPreference` → effective backend / mode.
2. Authenticate + authorize the action against `auth.policies`.
3. Execute the flow / skill.
4. If `mode == accumulate`, write an `episode` record.
5. Append an audit log entry.

### 2.2 `LLM` (provider abstraction)

```python
class LLM:
    config: ProviderConfig

    @property
    def model(self) -> str: ...      # alias-resolved
    @property
    def provider(self) -> str: ...    # the part before the first '/'

    def complete(self, messages, *, tools=None, response_format="text", **overrides) -> LLMResponse: ...
    async def acomplete(self, messages, **kwargs) -> LLMResponse: ...
```

Internals:
- `complete()` builds a kwargs dict from `ProviderConfig` + per-call overrides → calls `litellm.completion(**kwargs)`.
- LiteLLM is **lazy-imported** so users can browse skills / flows without installing it.
- `LLMResponse` exposes `tool_calls: list[dict]` extracted from `choice.tool_calls` — each entry has `id` / `name` / `arguments` (JSON-encoded string). This is the contract the autonomous agent loop reads from.
- `auto_detect()` priority: ANTHROPIC > OPENAI > GEMINI > DEEPSEEK > MISTRAL > XAI > DASHSCOPE > COHERE > PERPLEXITY > GROQ > TOGETHERAI > local (`PRAXIA_LOCAL_MODEL`, default `qwen-local`; valid local aliases include `qwen-local` / `gemma` / `phi` / `llama-local`).
- `DEFAULT_ALIASES` ships 27 entries spanning Anthropic, OpenAI, Google (Gemini + Gemma), Alibaba (Qwen), DeepSeek, Mistral (incl. Codestral), xAI Grok, Cohere Command R+, Perplexity Sonar (web-search-augmented), Groq-hosted Llama 3.3, local Ollama (Llama / Phi / Qwen / Gemma).

### 2.3 `MemoryBackend` protocol

```python
class MemoryBackend(Protocol):
    def add(self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]) -> MemoryRecord: ...
    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]: ...
    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]: ...
    def clear(self, *, user_id: str | None = None) -> None: ...

@dataclass
class MemoryRecord:
    id: str
    user_id: str
    text: str
    kind: str           # "episode" | "fact" | "preference" | "outcome" | (custom)
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

Implementations:
- **JsonBackend** — JSONL append + linear scan with simple BM25-like ranking (no extra deps).
- **Mem0Backend** — Wraps `mem0ai`. Hybrid semantic + keyword search; entity linking.
- **LangMemBackend** — Wraps `langmem`. Namespaced semantic memory.
- **LettaBackend** — Wraps `letta-client`. Read-only blocks supported.
- **ZepBackend** — Wraps `zep-python` + Graphiti. Time-axis KG.
- **HindSightBackend** — Wraps `hindsight`. Pure vector store.

### 2.4 Multi-LTM composition design

```
                    PersonalMemory.search(query, limit)
                                   │
                   ┌───────────────▼──────────────┐
                   │  backend  ← user-injected    │
                   └───────────────┬──────────────┘
                  ┌────────────────┼────────────────┐
                  │                │                │
        ┌─────────▼─────┐  ┌───────▼──────┐  ┌──────▼───────┐
        │ Single backend │  │ Composite    │  │ Routed       │
        │ (JsonBackend / │  │ Backend      │  │ Backend      │
        │  Mem0Backend / │  │              │  │              │
        │  ...)          │  │ Fan-out      │  │ Pick 1..N    │
        └────────────────┘  │ + Fusion     │  │ via Router   │
                            └──────┬───────┘  └──────┬───────┘
                                   │                 │
                          ┌────────▼─────────────────▼────────┐
                          │ ThreadPoolExecutor (max_workers)  │
                          └────────────┬──────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │  N MemoryBackend impls  │
                          │  (each in its own thread)│
                          └─────────────────────────┘
```

Fusion strategies (`CompositeBackend._fuse_*`):
- **rrf**: `score(d) = Σ_b weight_b / (k + rank_b(d))` with k=60. Good default.
- **union**: dedupe-on-id, preserve first-seen order.
- **intersection**: keep ids that appear in ≥ `min_agreement` backends.
- **weighted**: `Σ_b weight_b * (1 - rank_b(d) / |R_b|)`.
- **llm_rerank**: dedupe pool capped at 3·limit → call `rerank_fn(query, pool)`.

Failure handling: each backend's exception is caught and the result is treated as empty. The fan-out completes for the surviving backends.

### 2.5 Memory routing (`RuleRouter`)

```python
DEFAULT_RULES = [
    (regex, [backend_pref...], reason),
    ...
]
```

Order:
1. Audit / changelog / 履歴 → `[json, mem0]`
2. Temporal (`last week` / `先月`) → `[zep, mem0, hindsight]`
3. Entity question (`who is` / `について`) → `[mem0, hindsight, json]`
4. Similarity (`similar` / `類似`) → `[hindsight, mem0, letta]`
5. Fallback → `[mem0, hindsight, json]`

Implementation note: the regex pattern combines an ASCII fragment (with `\b`) and a CJK fragment (no `\b`) because Python's `\b` doesn't match between two adjacent CJK characters.

### 2.6 Memory policy resolution

```
 ┌─ admin.enforced_backend? ──── yes ──→ backend = enforced ─┐
 │                                                            │
 no                                                           │
 │                                                            │
 ┌─ requested_backend && admin.allowed? ─ yes ──→ requested ──┤
 │                                                            │
 no                                                           │
 │                                                            │
 ┌─ user_pref.backend && admin.allowed? ─ yes ──→ pref ───────┤
 │                                                            │
 no                                                           │
 │                                                            │
 └──→ admin.default_backend                                   │
                                                              │
                                                              ▼
                                                  (final backend)

 ┌─ admin.mode_locked? ─── yes ──→ mode = admin.default_mode (locked)
 │
 no
 │
 ┌─ user_role in admin.accumulate_locked_to? ─ yes ──→ "accumulate" (locked)
 │
 no
 │
 ┌─ requested_mode? ──── yes ──→ requested
 │
 no
 │
 ┌─ user_pref.mode? ──── yes ──→ pref
 │
 no
 │
 └──→ admin.default_mode
```

`ResolvedMemoryConfig.reason` carries the trace for debugging.

### 2.7 `AutonomousAgent` (LLM-driven tool-use loop)

```python
class AutonomousAgent:
    user_id: str
    role: str = "member"
    org_id: str = "default-org"
    llm: LLM
    tools: dict[str, AgentTool]   # 11 built-in + extras the host registered
    auth: AuthManager             # injected; never optional in production
    max_steps: int = 10
    max_tokens_per_step: int = 4096

    def run(self, user_input, *, history=None, images=None, system_prompt=None) -> AgentResult: ...
```

`images` is an optional list of `{"data": <base64>, "mime": "image/png"}`
attachments. When present, the current user message is built as the OpenAI/
LiteLLM multi-content `image_url` shape; otherwise the plain-string form is
preserved (no impact on non-vision models). `history` entries may already be in
multi-content shape if prior turns carried attachments.

**Loop invariants** (one iteration = one step):

1. Build `messages = [system, *history?, user]` on first iteration; thereafter
   carry forward.
2. Call `llm.complete(messages, tools=tool_schemas, max_tokens=...)` — schemas
   come from `AgentTool.to_litellm_schema()`.
3. If `resp.tool_calls == []` → loop exits with `resp.text` as the final answer.
4. Otherwise, append an `assistant` message that mirrors the model's `tool_calls`,
   then iterate them:
   - Look up the handler; unknown name → record an `ok=False` trace and continue.
   - Parse `arguments` as JSON; malformed → empty dict (not raised).
   - `pull_from_connector` → `auth.policies.require(...)` first (denial returns
     `{"ok": false, "error": "access denied"}` instead of raising).
   - `record_fact` → no-op when `pm.mode == "read_only"`.
   - Append a `tool` message with `tool_call_id` so the next LLM turn sees it.
   - If the call was `final_answer` and `ok` → exit early with the supplied answer.
5. After `max_steps` without termination, set `stopped_reason="max_steps"`.

**Audit contract**:
- `agent.run.start` recorded once per invocation (with `input_chars`).
- Every connector pull recorded with outcome `success` / `denied` / `error`.
- Every skill run recorded with outcome.
- `agent.run.end` recorded once with `steps` / `tool_calls` / `reason`.

**Failure modes**:
- LLM call raises → caught, `final_text` set to `"[agent error] LLM failed: …"`,
  `stopped_reason="error"`, audit ends with `outcome="error"`.
- Tool handler raises → caught, recorded into `ToolCallTrace.error`, loop
  continues so the model can recover.
- Audit recording itself fails → swallowed (the loop must never break for
  bookkeeping).

`praxia.mcp.server.build_tools()` adds an `autonomous_agent` MCP meta-tool
that constructs an `AutonomousAgent` per call (`user_id`, `task`, optional
`role` / `org_id` / `max_steps`) and returns `result.final_text`.

---

## 3. Cross-cutting sequence diagrams

### 3.1 SDK: run a flow with memory + ACL

```
 Caller   Praxia   AuthManager   PolicyManager   Memory(policy)   PersonalMemory   Flow   LLM   Backend   AuditLog
   │        │           │             │                │                  │         │     │       │         │
   ├ run_flow(name, inputs) ─────────►│                │                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ authenticate(api_key) ─►│                │                  │         │     │       │         │
   │        │           │ User        │                │                  │         │     │       │         │
   │        │◄──────────┤             │                │                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ authorize(user, run_flow, "flow:name") ─►│                  │         │     │       │         │
   │        │           │             │ Allow / Deny   │                  │         │     │       │         │
   │        │◄──────────┼─────────────┤                │                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ resolve_memory_config(user, role) ──────►│                  │         │     │       │         │
   │        │           │             │   ResolvedConfig                  │         │     │       │         │
   │        │◄──────────┼─────────────┼────────────────┤                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ instantiate PersonalMemory(backend, mode) ─────────────────►│         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ flow.run(inputs) ──────────────────────────────────────────►│         │     │       │         │
   │        │           │             │                │                  │         ├ LLM.complete() ►│     │
   │        │           │             │                │                  │         │     │ chat   │         │
   │        │           │             │                │                  │         │◄────┤        │         │
   │        │           │             │                │                  │         │     │       │         │
   │        │           │             │                │                  │         ├──── final ─►│         │
   │        │◄──────────┼─────────────┼────────────────┼──────────────────┤         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ if mode==accumulate: pm.record_episode() ──────────────────►│         │     │       │         │
   │        │           │             │                │                  ├ backend.add() ─►│      │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ audit.write("flow.run", success=True) ──────────────────────────────────────────────────────►│
   │ FlowResult                       │                │                  │         │     │       │         │
   │◄───────┤           │             │                │                  │         │     │       │         │
```

### 3.2 HTTP: same flow via `praxia serve`

```
Client       FastAPI app         Auth          (then identical to SDK seq above)
  │             │                 │
  ├ POST /api/v1/flows/{name}     │
  │   X-API-Key: ... ───────────►│
  │             │                 │
  │             ├ Depends(current_user) ──►│
  │             │                 │ User
  │             │◄────────────────┤
  │             │                 │
  │             ├ Praxia.run_flow(name, inputs) ──── (as above)
  │             │                 │
  │             │ FlowResult JSON │
  │◄────────────┤                 │
```

### 3.3 OAuth (per-user)

```
User    CLI/UI    OAuthFlow    Provider    OAuthTokenStore    Connector
  │       │           │            │              │                │
  │       ├ oauth start box --user-id alice
  │       │           │            │              │                │
  │       ├ flow.authorization_url(user="alice") ►│              │
  │       │           ├ build URL with state + PKCE ──────────────│
  │       │ URL,state │            │              │                │
  │       │◄──────────┤            │              │                │
  │       │           │            │              │                │
  ├──────►│ open URL  │            │              │                │
  │       │           │            │              │                │
  │       │           │ ◄ login + consent ────────┤                │
  │       │           │            │              │                │
  │       │           │ ◄ redirect with code ─────┤                │
  │       │           │            │              │                │
  │       ├ flow.exchange_code(code, state) ─────►│                │
  │       │           ├ POST token_url ──────────►│                │
  │       │           │ access_token, refresh_token                │
  │       │           │◄───────────┤              │                │
  │       │           │            │              │                │
  │       │           ├ store.save(token) ────────────────────────►│
  │       │           │            │              │ encrypt + write│
  │       │           │            │              │ to .praxia/oauth/alice/box.json
  │       │           │            │              │                │
  │ ────► │ later: pull from Box                                    │
  │       │           │            │              │                │
  │       │ Connector(user_id="alice") ─── oauth_token_for(...) ──►│
  │       │           │            │              │ load + decrypt │
  │       │           │            │              ├───────────────►│
  │       │           │            │              │  uses token    │
  │       │           │            │              │ ◄ Box API ────►│
```

---

## 4. Concurrency model

| Component | Model | Rationale |
|---|---|---|
| `LLM.complete` | Sync, blocking | LiteLLM's underlying calls are I/O-bound |
| `LLM.acomplete` | Async-on-thread (`asyncio.to_thread`) | Simplest path that still respects the blocking call |
| `CompositeBackend.search` | `ThreadPoolExecutor` (default `max_workers=6`) | I/O-bound across N backends — threading is sufficient |
| `Flow.run` | Sequential per step | Steps reference earlier outputs |
| `OAuthTokenStore` | Thread-safe via per-file flock | Safe from concurrent CLI / server processes |
| `AuditLog` | Append-only fsync per write | Crash-safe with minimal overhead |
| `JsonBackend` | Naive lock — coarse for v1 | Will move to per-user file with shard locks if profiled hot |

---

## 5. Data persistence layout

```
.praxia/
├── config.toml                   # praxia config set ...
├── auth/
│   ├── users/                    # User records (api_key_hash, role, ...)
│   ├── audit/audit.jsonl         # Append-only audit log
│   ├── policies.json             # Resource ACL policies
│   └── BOOTSTRAP_API_KEY.txt     # First-admin key (shown once)
├── admin/
│   └── memory_policy.json        # MemoryAdminPolicy
├── users/
│   └── <user_id>/
│       └── memory_pref.json      # MemoryUserPreference
├── personal/                     # JsonBackend storage (if backend=json)
│   └── <user_id>.jsonl
├── shared/                       # SharedMemory blocks (org-wide)
│   └── <org_id>/blocks.json
├── frozen/                       # Layer-4 Markdown
│   └── instructions/
├── chats/                        # ThreadStore — Agent conversation history
│   └── <user_id>/<thread_id>.json
├── oauth/                        # Encrypted per-user tokens
│   └── <user_id>/
│       └── <provider>.json       # encrypted blob
└── prompts/
    ├── personal/<user_id>.json
    ├── org.json
    └── distributed.json
```

Backups: copy the entire `.praxia/` tree atomically. All files are append-only or atomically rewritten.

---

## 6. Error handling

### 6.1 Exception hierarchy

```
Exception
├── MissingDependencyError(ImportError)   — connectors/parsers/backends w/o their SDK
├── ImportError                           — Python-level missing import
├── KeyError                              — registry lookup miss
├── ValueError                            — bad input
├── PermissionError                       — RBAC / ACL deny, OAuth not authorized
└── RuntimeError                          — internal logic invariant violated
```

### 6.2 Retry policy

| Failure | Retry? | Backoff |
|---|---|---|
| LLM API 429 | Yes (LiteLLM handles) | Exponential |
| LLM API 5xx | Yes | Exponential |
| LLM API 4xx (except 429) | No | — |
| Connector network error | No (caller's choice) | — |
| Memory backend search failure | No (composite drops it) | — |

### 6.3 User-facing error messages

- `MissingDependencyError`: includes the exact `pip install` command.
- `ValueError` from CLI: rendered in red by `rich`, exit code 1.
- `PermissionError` from CLI: includes which policy / role denied.
- HTTP 4xx / 5xx: structured `{"detail": "..."}` body, no stack traces leaked.

---

## 7. Testing strategy

| Layer | Approach |
|---|---|
| Unit | `tests/test_smoke.py` — 60 hermetic tests, no external services |
| Mocks | Stub backends for memory tests; no LLM calls in CI |
| Plugin tests | Each registry is asserted to contain the built-in names |
| Integration | Marked `@pytest.mark.integration`, opt-in via `pytest -m integration` |
| End-to-end | Manual checklist in `docs/testing.md` (TODO — covers UI screenshots, real OAuth flow, etc.) |

CI runs the unit + plugin layers on every PR. Integration tests run weekly against real provider sandboxes.

---

## 8. Performance budget (v1.0)

| Operation | Budget | Measured |
|---|---|---|
| Import `praxia` (cold) | < 200 ms | ~80 ms |
| `praxia init` | < 500 ms | ~250 ms |
| `praxia list flows / skills / models / backends` | < 100 ms | ~30 ms |
| Single `LLM.complete` (excluding model latency) | < 5 ms framework overhead | ~2 ms |
| `CompositeBackend.search` over 4 backends | parallel max + ~5 ms fusion | depends on backends |
| File parser (1 MB PDF) | < 1 s | ~400 ms |
| HTML exporter (10 KB md) | < 50 ms | ~5 ms |
| PPTX exporter (10 KB md) | < 200 ms (incl. python-pptx) | ~80 ms |

Hot paths are the registries (cached after first `.list()`) and the LLM client (LiteLLM lazy-imports).

---

## 9. Security design

### 9.1 Credentials at rest

| Secret | At-rest form |
|---|---|
| User API keys | bcrypt-hashed (`api_key_hash`) — raw shown once at issue |
| User passwords | Not stored — SSO only |
| JWT signing key | `PRAXIA_JWT_SECRET` (env / config; never in code) |
| OAuth tokens | Symmetric-encrypted (`PRAXIA_TOKEN_ENC_KEY`-derived); per-user-per-provider files |
| LLM provider keys | Env / `.env` / config — never logged |

### 9.2 Audit trail

`AuditLog.write(actor_id, action, resource=None, success=True, metadata=None)` is called by:
- `AuthManager` (login, role grant, user CRUD)
- `PolicyManager` (policy add / remove / deny)
- `Praxia.run_flow / run_skill` (every invocation)
- `OAuthFlow.exchange_code` (token issued)
- `AdminExporter` (every export self-audits)

Format: append-only JSONL under `.praxia/auth/audit/audit.jsonl`. Every record has `id`, `timestamp`, `actor_id`, `action`, `resource`, `success`, `metadata`.

### 9.3 ACL evaluation order

```python
PolicyManager.evaluate(user_id, role, resource_type, resource_id, action) -> Decision
```
1. Match all policies whose `resource_type` matches AND `resource_pattern` (glob) matches `resource_id` AND `actions` contains `action`.
2. Filter principals: `user:<user_id>` or `role:<role>` must match.
3. **Deny wins**: if any matched policy is `deny`, return Decision(False).
4. If at least one `allow` matches, return Decision(True).
5. Otherwise: `default_decision` (configurable, default `allow`).

---

## 10. Extensibility design — `Registry`

```python
class Registry(Generic[T]):
    def __init__(self, *, name: str, entry_point_group: str | None = None) -> None: ...

    def register(self, name: str, cls_or_lazy: type[T] | LazyImport) -> None: ...
    def register_decorator(self, name: str) -> Callable: ...
    def get(self, name: str) -> type[T]: ...                  # KeyError if absent
    def has(self, name: str) -> bool: ...
    def unregister(self, name: str) -> bool: ...
    def list(self) -> list[str]: ...
    def items(self) -> list[tuple[str, type[T]]]: ...
```

Registration sources, in order:
1. **Direct** — `register("name", cls)` at import time
2. **Lazy** — `register("name", lazy("module:Class"))` — resolved on first `get()`
3. **Entry-point** — discovered via `importlib.metadata.entry_points(group=...)` on first call to `list()` / `get()`

Why this matters: every plug point in Praxia uses **the same** `Registry`. A custom skill, custom connector, custom memory backend, custom output exporter, and custom OAuth provider all follow the same install-and-go pattern.

---

## 11. Known limitations (v1.0)

| Area | Limitation | Workaround / Plan |
|---|---|---|
| Single-host | One `.praxia/` per process | Run multiple processes for HA, share storage via NFS or migrate to object storage (planned) |
| LLM streaming | Not exposed | Wrap LiteLLM streaming yourself; first-class support planned |
| Large-file parsers | Whole-file in-memory | Stream-mode planned |
| OAuth token encryption | Symmetric, key in env | KMS-backed encryption planned |
| FastAPI server | Minimal endpoint set | Add as needed; protocol pattern is documented |
| Multi-tenancy | One tenant per process | SaaS variant on roadmap |

For the public roadmap, track Issues labeled `roadmap` on the GitHub repo.
