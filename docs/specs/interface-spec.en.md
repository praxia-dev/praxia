# Praxia — Interface Specification (I/F)

> Status: **v1.0** · 🇯🇵 [日本語版](interface-spec.ja.md)

This document enumerates every public interface Praxia exposes. All signatures listed here are stable in v1.x.

---

## 1. Python SDK

### 1.1 Top-level package

```python
from praxia import (
    Praxia,            # Orchestrator
    LLM,               # Multi-provider LLM client
    PersonalMemory,    # Layer-1 memory
    SharedMemory,      # Layer-3 memory
    MarkdownStore,     # Layer-4 memory
)
```

### 1.2 `praxia.LLM`

```python
LLM(
    model: str = "claude",                    # alias or "<provider>/<model>"
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    **extra,
)
```
Aliases (27 first-class):

| Group | Aliases |
|---|---|
| Anthropic | `claude`, `claude-sonnet`, `claude-haiku` |
| OpenAI | `chatgpt`, `gpt-4o`, `o1` |
| Google | `gemini`, `gemini-flash` |
| Google Gemma (open) | `gemma`, `gemma-2b`, `gemma-9b`, `gemma-27b`, `gemma-cloud` |
| Alibaba | `qwen`, `qwen-72b`, `qwen-local` |
| **DeepSeek** | `deepseek`, `deepseek-reasoner` |
| **Mistral** | `mistral`, `mistral-small`, `codestral` |
| **xAI** | `grok` |
| **Cohere** | `command-r` |
| **Perplexity** | `perplexity` (web-search-augmented) |
| **Llama** | `llama` (Groq fast), `llama-local` (Ollama) |
| **Microsoft Phi** | `phi` (Ollama) |

Anything else LiteLLM supports works via the raw `provider/model` string.

```python
LLM.complete(messages: list[dict], *, tools=None, response_format="text"|"json", **overrides) -> LLMResponse
LLM.acomplete(messages: list[dict], **kwargs) -> LLMResponse        # async
LLM.list_supported_providers() -> list[str]                         # static
LLM.auto_detect() -> str                                            # static — env-var driven priority order
```

`LLMResponse`: `text: str`, `model: str`, `usage: dict[str, int]`, `raw: Any`,
**`tool_calls: list[dict]`** (each entry has `id` / `name` / `arguments` —
a JSON-encoded string of the function call's arguments). The `tool_calls`
field is what `praxia.agent.AutonomousAgent` reads to drive its loop.

### 1.3 `praxia.PersonalMemory`

```python
PersonalMemory(
    user_id: str,
    *,
    backend: str | MemoryBackend = "auto",   # "json" | "mem0" | "langmem" | "letta" | "zep" | "hindsight" | instance
    storage_dir: Path | str | None = None,
    mode: "accumulate" | "read_only" | None = None,
    **backend_kwargs,
)
```

Methods:
- `record_episode(*, flow_name, inputs, output, metadata=None) -> MemoryEntry`
- `record_fact(text, *, metadata=None) -> MemoryEntry`
- `record_preference(text, *, metadata=None) -> MemoryEntry`
- `record_outcome(*, episode_id, success, score=None, notes="") -> MemoryEntry`
- `outcomes_for(episode_id) -> list[MemoryEntry]`
- `search(query: str, limit: int = 5) -> list[str]`
- `all_entries() -> list[MemoryEntry]`
- `clear() -> None`
- Properties: `backend_name`, `mode`
- `set_mode(mode: "accumulate" | "read_only") -> None`

In `read_only` mode, all `record_*` calls return a `MemoryEntry` with `metadata["read_only_dropped"] = True` and persist nothing.

### 1.4 Multi-LTM composition

```python
from praxia.memory.composite import CompositeBackend, WeightedBackend
from praxia.memory.router import RoutedBackend, RuleRouter, LLMRouter

CompositeBackend(
    backends: list[WeightedBackend | MemoryBackend],
    *,
    fusion: "rrf" | "union" | "intersection" | "weighted" | "llm_rerank" = "rrf",
    write_to: str | None = None,
    min_agreement: int = 2,
    rrf_k: int = 60,
    max_workers: int = 6,
    rerank_fn: Callable | None = None,
)

RoutedBackend(
    backends: dict[str, MemoryBackend],
    *,
    router: MemoryRouter,            # RuleRouter | LLMRouter | custom
    write_to: str,                   # must be a key in `backends`
)
```

Both implement the `MemoryBackend` protocol → can be passed to `PersonalMemory(..., backend=instance)`.

### 1.5 `praxia.memory.policy`

```python
MemoryAdminPolicy(
    # --- backend strategy ---
    backend_strategy: Literal["single", "composite", "routed"] = "single",
    backend: str = "json",                                # used by 'single'

    # 'composite' mode (CompositeBackend)
    composite_backends: list[str] = [],                    # e.g. ["mem0", "zep"]
    composite_fusion: Literal["rrf", "union", "intersection",
                              "weighted", "llm_rerank"] = "rrf",
    composite_write_to: str = "",

    # 'routed' mode (RoutedBackend)
    routed_backends: list[str] = [],
    routed_router: Literal["rule", "llm"] = "rule",
    routed_write_to: str = "",

    # --- accumulation mode ---
    default_mode: Literal["accumulate", "read_only"] = "accumulate",

    # --- legacy fields (kept so old policy.json files load cleanly) ---
    # __post_init__ migrates `enforced_backend` / `default_backend`
    # into the new `backend` field when only the legacy field is set.
    enforced_backend: str | None = None,
    default_backend: str = "json",
    allowed_backends: list[str] = [],
    mode_locked: bool = False,
    accumulate_locked_to: list[str] = [],
)
MemoryAdminPolicy.load(storage_dir) -> "MemoryAdminPolicy"
MemoryAdminPolicy.save(storage_dir) -> Path
MemoryAdminPolicy.is_backend_allowed(backend) -> bool

# Build the actual Layer-1 backend per the policy. Returns either a
# backend name string (for 'single' mode — caller can pass it to
# PersonalMemory(backend=name)) or a fully-built MemoryBackend
# instance (CompositeBackend / RoutedBackend for the other modes).
build_personal_backend(storage_dir, *, user_id) -> str | MemoryBackend

MemoryUserPreference(user_id, backend=None, mode=None)
MemoryUserPreference.load(storage_dir, user_id) -> "MemoryUserPreference"
MemoryUserPreference.save(storage_dir) -> Path

resolve_memory_config(*, user_id, storage_dir, user_role=None,
                      requested_backend=None, requested_mode=None) -> ResolvedMemoryConfig
```

The Streamlit Admin UI (`Admin → Settings → 🧠 Memory policy`) writes
`MemoryAdminPolicy` to `.praxia/admin/memory_policy.json`. The CLI
equivalents are `praxia admin memory-policy-show` and
`praxia admin memory-policy-set`. **Per-user `MemoryUserPreference` no
longer has a UI surface** — admin policy is the single source of
truth for runtime backend behavior.

### 1.6 `praxia.skills`

```python
class Skill:
    manifest: SkillManifest
    system_prompt: str
    tools: list[Callable]
    reference_files: list[Path]

    def __init__(self, llm: LLM | None = None) -> None: ...
    def as_agent(self) -> Agent: ...
    def run(self, user_input: str, **inputs) -> str: ...
    def to_skill_md(self) -> str: ...

class SkillManifest:
    name: str
    description: str
    version: str = "0.1.0"
    domain: str = "general"
    tags: list[str] = []
    author: str | None = None
```

Built-in skills: `InvestmentSkill`, `SalesSkill`, `DesignSkill`, `PurchasingSkill`, `PatentSkill`, `LegalSkill`, **`OutputFormatSkill`** (utility).

### 1.7 `praxia.skills.output_format.OutputFormatSkill`

```python
fs = OutputFormatSkill()
fs.detect(user_request: str, *, default: str = "md") -> FormatRequest
fs.detect_with_llm(user_request: str, *, default: str = "md") -> FormatRequest
fs.deliver(content, *, user_request="", format=None, output_path=None, **exporter_kwargs) -> ExporterResult
```

`FormatRequest`: `format: str`, `confidence: float`, `reason: str`.

### 1.8 `praxia.io` exporters

```python
from praxia.io.exporters import export_as, supported_formats, EXPORTERS

export_as(content, *, format: str, output_path=None, **kwargs) -> ExporterResult
supported_formats() -> list[str]
```

`ExporterResult`: `format: str`, `bytes: bytes`, `suggested_extension: str`, `output_path: Path | None`, `size: int`.

Built-in formats: `md` / `markdown`, `html`, `pptx`, `docx`, `json`. Each exporter's constructor kwargs:

| Exporter | kwargs |
|---|---|
| `MarkdownExporter` | `title`, `author`, `frontmatter` |
| `HtmlExporter` | `title`, `css`, `wrap_in_document`, `lang` |
| `PptxExporter` | `title`, `subtitle`, `author` |
| `DocxExporter` | `title`, `author` |
| `JsonExporter` | `indent`, `ensure_ascii` |

### 1.9 `praxia.flows`

```python
class FlowResult:
    final_output: str
    step_outputs: dict[str, str]
    total_usage: dict[str, int]

flow = SalesAgentFlow()
result: FlowResult = flow.run({"customer_name": ..., "product": ...})
```

Built-in: `SalesAgentFlow`, `LogicCheckerFlow`, `RAGOptimizationFlow`. Custom flows register via `@FLOWS.register_decorator(name)` or entry-point.

### 1.9.1 `praxia.agent.AutonomousAgent`

LLM-driven tool-use loop over the full Praxia stack. Mirrors how modern code-editing assistants
pick their own tools, scoped to memory / skills / connectors / frozen layer.

```python
from praxia.agent import AutonomousAgent, AgentResult, ToolCallTrace
from praxia.agent.tools import AgentTool, builtin_tools

agent = AutonomousAgent(
    user_id: str,
    *,
    role: str = "member",
    org_id: str = "default-org",
    llm: LLM | None = None,                   # defaults to LLM() (auto-detect)
    memory_dir: str | Path = ".praxia",
    memory_backend: str = "auto",
    connector_configs: dict[str, dict] | None = None,    # {"box": {"access_token": "..."}}
    enable_tools: list[str] | None = None,    # whitelist; final_answer always kept
    extra_tools: list[AgentTool] | None = None,
    max_steps: int = 10,
    max_tokens_per_step: int = 4096,
    system_prompt: str | None = None,
    auth: AuthManager | None = None,
)

result: AgentResult = agent.run(
    user_input: str,
    *,
    history: list[dict] | None = None,
    images: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
)
```

`images` — optional vision attachments for the current turn. Each entry is
`{"data": "<base64>", "mime": "image/png"}` and is forwarded as an OpenAI/LiteLLM
`image_url` content part on the user message; the underlying model must support
vision (Claude 3+, GPT-4o, Gemini 1.5+, etc.). History entries may already be in
multi-content shape if they carry attachments from prior turns.

`AgentResult`:
- `final_text: str`
- `tool_calls: list[ToolCallTrace]` — every call inspected during the loop
- `steps: int`
- `stopped_reason: "completed" | "max_steps" | "error"`
- `usage: dict[str, int]` — accumulated input/output tokens

`ToolCallTrace`:
- `step: int`, `name: str`, `arguments: dict`, `arguments_text: str`
- `result: Any`, `result_text: str`
- `ok: bool`, `error: str`

**Conversation persistence (`praxia.data.threads`):**

`ThreadStore` saves each Agent conversation as JSON at
`.praxia/chats/<user_id>/<thread_id>.json`. The Streamlit UI uses it via the
`💬 Conversations` popover to list / resume / rename / delete past threads;
ephemeral mode bypasses persistence entirely.

```python
from praxia.data.threads import ChatMessage, ChatThread, ThreadStore

store = ThreadStore(memory_dir / "chats")
thread = store.create("alice")                              # empty thread
thread.messages.append(ChatMessage(role="user",
                                   content="What is in this chart?",
                                   images=[{"data": b64, "mime": "image/png"}]))
store.save(thread)                                          # auto-titles on first user msg
threads = store.list_for_user("alice")                      # newest-updated first
store.rename("alice", thread.id, "Q3 chart review")
store.delete("alice", thread.id)
```

`ChatMessage` fields: `role` / `content` / `timestamp` / `trace` (tool-use trace
from `AgentResult.tool_calls`) / `images` (list of base64+mime dicts).

**Built-in tools** (`praxia.agent.tools.builtin_tools()` returns the dict):

| Tool | Layer | Notes |
|---|---|---|
| `search_personal_memory` | 1 | hits + count |
| `search_org_memory` | 3 | hits + count |
| `search_frozen_layer` | 4 | substring match over `.praxia/frozen/**.md` |
| `list_skills` | — | optional `domain=` filter |
| `list_personal_skills` | 6 | per-user catalog |
| `list_org_skills` | 6 | effective: org + distributed + personal |
| `run_skill` | 6 | invokes by name with text input |
| `list_connectors` | — | from `CONNECTORS` registry |
| `pull_from_connector` | — | **ACL-checked** (`auth.policies.require`), audited |
| `record_fact` | 1 | no-op when memory mode is `read_only` |
| `final_answer` | — | sentinel that terminates the loop |

Every tool call is recorded via `auth.audit.record(...)` regardless of outcome.

The agent is also exposed as a single MCP meta-tool `autonomous_agent` (see
`praxia.mcp.server.build_tools`) so remote MCP clients can delegate an entire
investigation rather than orchestrating individual tools.

### 1.10 `praxia.auth`

```python
auth = AuthManager(storage_dir=".praxia/auth", bootstrap_admin: str | None = None)
auth.create_user(username, *, role: Role, email=None) -> tuple[User, raw_api_key]
auth.authenticate(*, api_key=None, token=None) -> User | None
auth.authorize(user, action: str, resource: str | None = None) -> bool
auth.require(user, action, resource=None) -> None              # raises PermissionError
auth.issue_token(user_id) -> str                               # JWT
auth.grant_role(username, role: Role) -> None
auth.update_user(username, **fields) -> User
auth.deactivate_user(username) -> None
auth.delete_user(username) -> bool
auth.audit.write(actor_id, action, resource=None, success=True, metadata=None) -> None
auth.audit.tail(limit=100) -> list[AuditEvent]
auth.policies.add(*, effect, resource_type, resource_pattern, actions, principals, description) -> Policy
auth.policies.evaluate(user_id, role, resource_type, resource_id, action) -> Decision
auth.policies.require(...) -> None                              # raises PermissionError
auth.exports.export_audit(output_path, format, since=None, actor_id=None) -> Path
auth.exports.export_users(output_path, format) -> Path
auth.exports.export_personal_memory(user_id, output_path, format) -> Path
auth.exports.export_policies(output_path, format) -> Path
auth.exports.export_shared_memory(output_path, format) -> Path
```

Roles: `Role.ADMIN`, `Role.OPERATOR`, `Role.MEMBER`, `Role.VIEWER`.

### 1.11 `praxia.connectors`

```python
from praxia.connectors import get_connector, list_builtin

conn = get_connector(name: str, **provider_kwargs)
items: list[ConnectorItem] = conn.pull(path: str, *, limit=100)
receipt = conn.push(path: str, data: ConnectorItem | dict)
```

Built-in: `box`, `sharepoint`, `dropbox`, `gdrive`, `kintone`, `salesforce`. Per-user OAuth: pass `user_id="..."` instead of `access_token=...`.

### 1.12 `praxia.connectors.oauth`

```python
OAuthFlow(
    provider_config, *,
    client_id, client_secret, redirect_uri,
    token_store=None,    # OAuthTokenStore
    state_store=None,    # PersistentStateStore — required for multi-worker
)
flow.authorization_url(user_id) -> tuple[url, state]
flow.exchange_code(code, state) -> OAuthToken

OAuthTokenStore(
    storage_dir, *,
    encryption_secret=None,
    kms=None,           # KmsAdapter; default = build_adapter(PRAXIA_KMS_ADAPTER or "local")
)
store.save(token: OAuthToken) -> None
store.get(user_id, provider) -> OAuthToken | None
store.list_for_user(user_id) -> list[OAuthToken]
store.delete(user_id, provider) -> bool

PersistentStateStore(storage_dir, *, ttl_seconds=600)
state_store.put(state_token, OAuthState) -> None
state_store.pop(state_token) -> OAuthState | None
state_store.clear() -> None

oauth_token_for(user_id, provider, *, store=None) -> OAuthToken
```

Pre-registered providers: `BOX_OAUTH`, `MICROSOFT_OAUTH`, `DROPBOX_OAUTH`, `GOOGLE_OAUTH`, `SALESFORCE_OAUTH`.

### 1.12.1 `praxia.connectors.oauth.kms` — KMS adapters

```python
class KmsAdapter(Protocol):
    name: str
    def wrap(self, dek: bytes) -> bytes: ...    # encrypt 32-byte DEK
    def unwrap(self, wrapped: bytes) -> bytes:  # decrypt → 32-byte DEK

KMS_ADAPTERS: Registry[KmsAdapter]   # entry-point group: praxia.kms_adapters

build_adapter(name=None, **kwargs) -> KmsAdapter
# name resolution: arg > PRAXIA_KMS_ADAPTER env > "local"

envelope_encrypt(adapter, plaintext: bytes) -> dict
envelope_decrypt(adapter, envelope: dict) -> bytes
```

Built-in adapters:
- `LocalKmsAdapter(secret=...)` — HKDF / AES-GCM, dev only
- `AwsKmsAdapter(key_id=..., region=...)` — boto3
- `AzureKeyVaultAdapter(vault_url=..., key_name=..., key_version=...)`
- `GcpKmsAdapter(project_id=..., location=..., key_ring=..., key_name=...)`
- `VaultTransitAdapter(vault_url=..., key_name=..., token=..., mount_point="transit")`

### 1.13 `praxia.io.parsers`

```python
from praxia.io.parsers import parse_file, supported_extensions

parsed: ParsedFile = parse_file(content_bytes, filename: str)
# parsed.content: str, parsed.metadata: dict
```

Supported extensions: `pdf`, `docx`, `pptx`, `xlsx`, `csv`, `json`, `yaml`, `yml`, `xml`, `html`, `htm`, `md`, `markdown`, `txt`.

### 1.14 `praxia.io.audio`

```python
STT(provider: "openai" | "openai-local" = "openai")
stt.transcribe(audio: bytes, *, language=None) -> str

TTS(provider: "openai" | "elevenlabs" | "piper-local" = "openai")
tts.synthesize(text: str, *, voice="alloy", format="mp3") -> bytes
```

### 1.15 `praxia.experiments`

```python
class ExperimentStatus(str, Enum):
    DRAFT = "draft"; RUNNING = "running"; PAUSED = "paused"; FINISHED = "finished"

@dataclass
class Variant:
    name: str
    payload: dict[str, Any] = {}

@dataclass
class Experiment:
    id: str
    name: str
    variants: dict[str, Variant] = {}
    traffic_split: dict[str, float] = {}      # auto-uniform if omitted
    description: str = ""
    status: str = "draft"
    target_audience: dict[str, Any] = {}      # {"roles": [...], "users": [...]} or {} for all
    start_at: float = 0.0
    end_at: float = 0.0

ExperimentRegistry(storage_dir=".praxia/experiments")
reg.create(exp: Experiment) -> Experiment
reg.get(exp_id: str) -> Experiment | None
reg.list(*, status=None) -> list[Experiment]
reg.update(exp: Experiment) -> Experiment
reg.set_status(exp_id, status) -> Experiment
reg.delete(exp_id: str) -> bool

reg.assign(exp_id, *, user_id, role="member") -> Variant | None
reg.record_outcome(exp_id, *, user_id, episode_id, success, score=None, notes="", role="member") -> ExperimentOutcome | None
reg.outcomes(exp_id: str) -> list[ExperimentOutcome]
reg.results(exp_id, *, users=None, role="member") -> ExperimentResults

# Pure assignment (no storage)
assign_variant(exp: Experiment, *, user_id: str) -> Variant | None
```

Assignment is deterministic: `SHA-256(experiment_id + ":" + user_id)` mod traffic_split.

### 1.16 `praxia.extensions.Registry` (plugin core)

```python
reg: Registry[T] = Registry(name: str, entry_point_group: str | None = None)
reg.register(name, cls)                      # direct
reg.register(name, lazy("module:Class"))     # lazy
reg.register_decorator(name)                 # decorator form
reg.unregister(name) -> bool
reg.has(name) -> bool
reg.get(name) -> type[T]                     # raises KeyError if absent
reg.list() -> list[str]
reg.items() -> list[tuple[str, type[T]]]
```

---

## 2. Command-line interface (CLI)

All commands accept `--help` for full args. Categories below.

### 2.1 Lifecycle
- `praxia init [--user-id ID] [--backend BACKEND] [--model MODEL]`
- `praxia run sales|logic|rag [...flow-specific args]`
- `praxia consolidate [--threshold 0.75] [--dry-run]`
- `praxia freeze --block LABEL`
- `praxia ui [--port 8501]`
- `praxia serve [--host 127.0.0.1] [--port 8000] [--cors-origin URL]` *(requires `[server]` extra)*

### 2.2 Discovery
- `praxia list flows | skills | models | backends`
- `praxia connector list`
- `praxia config show | path | get KEY | set KEY VALUE | init`

### 2.3 Skills & flows
- `praxia skill run <name> "<input>"`
- `praxia skill promote <name>`
- `praxia skill distribute <name> --target-roles role1,role2`

### 2.3.1 Autonomous agent
- `praxia agent run "<task>" [--user-id alice] [--role member] [--org-id default-org] [--model auto] [--max-steps 10] [--enable-tools t1,t2,...] [--show-trace/--no-show-trace]`
- `praxia agent tools` — list the 11 built-in agent tools with descriptions

### 2.4 Users (admin)
- `praxia user create <name> --role ROLE [--email]`
- `praxia user list`
- `praxia user grant <name> ROLE`
- `praxia user update <name> [--email] [--role]`
- `praxia user deactivate <name>`
- `praxia user delete <name>`
- `praxia user rotate-key <name>`
- `praxia user audit [--limit N]`

### 2.5 Prompts
- `praxia prompt create --user-id ID --name N --body B`
- `praxia prompt list [--user-id] [--scope personal|org|distributed]`
- `praxia prompt distribute --name N --target-roles ...`
- `praxia prompt delete --user-id --name`

### 2.6 Connectors
- `praxia connector pull <name> <path> [--user-id] [--limit]`
- `praxia connector push <name> <path> --content-file FILE [--user-id]`

### 2.7 Per-user OAuth
- `praxia oauth start <provider> --user-id ID`
- `praxia oauth list --user-id ID`
- `praxia oauth revoke <provider> --user-id ID`

### 2.8 Policies (ACL)
- `praxia policy add ALLOW|DENY RESOURCE_TYPE PATTERN --principals ROLE1,USER1 --description ...`
- `praxia policy list`
- `praxia policy remove POLICY_ID`
- `praxia policy test USER ROLE RESOURCE_TYPE RESOURCE_ID ACTION`

### 2.9 Memory mode / backend (per-user, admin-controlled)
- `praxia memory mode --user-id ID accumulate|read_only`
- `praxia memory backend --user-id ID BACKEND`
- `praxia memory show --user-id ID [--role ROLE]`
- `praxia admin memory-policy-show`
- `praxia admin memory-policy-set [--enforced-backend B] [--default-backend B] [--allowed B1,B2] [--default-mode M] [--mode-locked] [--accumulate-locked-roles R1,R2]`

The Streamlit UI also exposes the same `MemoryAdminPolicy` (`.praxia/admin/memory_policy.json`) under **Admin → Settings → 🧠 Memory policy** as a form. There is intentionally **no user-facing memory-preference UI** — memory backend / mode is an admin-only concern. The `MemoryUserPreference` SDK class remains available for programmatic use but no UI writes to it.

### 2.10 Output exporters
- `praxia export <input.md> <output.html|.pptx|.docx|.json> [--format] [--title]`

### 2.10b A/B experiments
- `praxia experiment create <id> --name N --variants '{...}' [--traffic-split "..."]`
- `praxia experiment list`
- `praxia experiment {start|pause|finish|delete} <id>`
- `praxia experiment results <id>`

### 2.11 Admin exports (compliance / SIEM)
- `praxia admin export-audit OUTFILE --format csv|json|jsonl --since-days N --actor USER`
- `praxia admin export-users OUTFILE --format json|csv`
- `praxia admin export-memory DIR --user-id USER` *(or `--all`)*
- `praxia admin export-policies OUTFILE --format json|csv`
- `praxia admin export-shared-memory OUTFILE --format jsonl|json`

---

## 3. HTTP API (`praxia serve`)

Versioned under `/api/v1`. All endpoints except `/auth/login` require either `X-API-Key` header or `Authorization: Bearer <jwt>`.

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/v1/auth/login` | `{"api_key": "..."}` | `{"token", "user_id", "role"}` |
| GET | `/api/v1/me` | — | `{"id", "username", "role"}` |
| POST | `/api/v1/skills/{name}` | `{"input": "...", "kwargs": {...}}` | `{"output", "skill"}` |
| POST | `/api/v1/flows/{name}` | `{"inputs": {...}}` | `{"output", "step_outputs", "usage"}` |
| POST | `/api/v1/memory/search` | `{"query": "...", "limit": 5}` | `{"results": [...]}` |
| PUT | `/api/v1/memory/mode` | `{"mode": "accumulate" \| "read_only"}` | `{"ok", "mode"}` |
| GET | `/api/v1/memory/show` | — | `{"backend", "mode", "locked_by_admin", "reason"}` |
| POST | `/api/v1/export` | `{"content", "format", "title"}` | `application/octet-stream` (binary) |
| POST | `/api/v1/oauth/{provider}/start` | — | `{"authorize_url", "state", "provider"}` |
| GET | `/api/v1/oauth/{provider}/callback` | (query: code, state) | HTML success page or 302 redirect |
| GET | `/api/v1/oauth/{provider}/status` | — | `{"authorized", "expires_at", "is_expired", "scope"}` |
| DELETE | `/api/v1/oauth/{provider}` | — | `{"deleted": bool}` |

CORS: configure with `--cors-origin URL` (repeatable).

---

## 4. Configuration interface

Resolution: env > `.env` > `.praxia/config.toml`. Canonical key list in `.env.example`.

| Category | Keys |
|---|---|
| LLM | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_BASE` |
| Memory | `PRAXIA_MEMORY_BACKEND`, `PRAXIA_MEMORY_MODE`, `QDRANT_URL` |
| Auth | `PRAXIA_JWT_SECRET`, `PRAXIA_TOKEN_ENC_KEY`, `PRAXIA_LOCAL_MODEL` |
| KMS (token encryption) | `PRAXIA_KMS_ADAPTER` (`local`/`aws`/`azure`/`gcp`/`vault`) + adapter-specific kwargs |
| HTTP server | `PRAXIA_PUBLIC_URL` (pin redirect URI), `PRAXIA_OAUTH_SUCCESS_REDIRECT` |
| SSO | `PRAXIA_SSO_PROVIDER`, `PRAXIA_SSO_CLIENT_ID`, `PRAXIA_SSO_CLIENT_SECRET`, `PRAXIA_SSO_REDIRECT_URI`, `PRAXIA_SSO_TENANT_ID`, `PRAXIA_SSO_OKTA_DOMAIN`, `PRAXIA_SSO_KEYCLOAK_BASE_URL`, `PRAXIA_SSO_KEYCLOAK_REALM`, `PRAXIA_SSO_ISSUER_URL` |
| OAuth | `PRAXIA_OAUTH_BOX_CLIENT_ID/SECRET`, `PRAXIA_OAUTH_MICROSOFT_*`, `PRAXIA_OAUTH_DROPBOX_*`, `PRAXIA_OAUTH_GOOGLE_*`, `PRAXIA_OAUTH_SALESFORCE_*` |
| Connectors | `PRAXIA_CONN_<NAME>_<UPPERCASE_KEY>` (legacy / service-account fallback) |
| Audio | `ELEVENLABS_API_KEY` (OpenAI uses `OPENAI_API_KEY`) |

---

## 5. Plugin protocols (entry-point groups)

Each is a discoverable extension point. Implement, declare, install — no edit to Praxia core.

| Group | Implements | Built-in count |
|---|---|---|
| `praxia.connectors` | `Connector` (`name`, `pull`, `push`) | 6 |
| `praxia.memory_backends` | `MemoryBackend` (`add`, `search`, `all`, `clear`) | 6 |
| `praxia.parsers` | `Parser` (`parse`, `extensions`) | 8 |
| `praxia.exporters` | `Exporter` (`format`, `extensions`, `export`) | 5 |
| `praxia.oauth_providers` | `OAuthProviderConfig` instance | 5 |
| `praxia.skills` | `Skill` subclass with `manifest` | 6 (+1 utility) |
| `praxia.flows` | `Flow` subclass with `name`, `description`, `run()` | 3 |
| `praxia.kms_adapters` | `KmsAdapter` (`name`, `wrap`, `unwrap`) | 5 (local + 4 cloud) |

See [`docs/PLUGINS.md`](../PLUGINS.md) and [`docs/CUSTOM_CONNECTORS.md`](../CUSTOM_CONNECTORS.md).

---

## 6. Error model

| Exception | Where raised | Mapped HTTP status (server module) |
|---|---|---|
| `MissingDependencyError` | Optional SDK absent | 503 |
| `ValueError` | Bad input | 400 |
| `KeyError` | Unknown registry name | 404 |
| `PermissionError` | RBAC / ACL deny | 403 |
| `ImportError` | Optional extra missing | 503 |
| `RuntimeError` | Internal logic error | 500 |

The HTTP server logs exception details server-side and returns sanitized messages to clients.

---

## 7. Backwards-compatibility commitments

- All public class / function signatures listed above are stable in v1.x.
- New features add new arguments with **defaults**; never repurpose existing argument names.
- Removal of a public name requires a major version bump and a deprecation warning during one minor version.
- Plugin protocols (`MemoryBackend`, `Connector`, `Parser`, `Exporter`, `Skill`, `Flow`) are **frozen** in v1.x — adding a method to a Protocol is breaking; we will add `MemoryBackendV2` etc. instead.
