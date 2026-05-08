# Praxia — I/F 仕様書

> ステータス: **v1.0** · 🇬🇧 [English](interface-spec.en.md)

公開インターフェースを網羅。本書記載のシグネチャは v1.x で安定。

---

## 1. Python SDK

### 1.1 トップレベル

```python
from praxia import (
    Praxia,            # オーケストレータ
    LLM,               # マルチプロバイダ LLM クライアント
    PersonalMemory,    # Layer-1 メモリ
    SharedMemory,      # Layer-3 メモリ
    MarkdownStore,     # Layer-4 メモリ
)
```

### 1.2 `praxia.LLM`

```python
LLM(
    model: str = "claude",                    # alias または "<provider>/<model>"
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    **extra,
)
```
エイリアス (27 種、ファーストクラス):

| グループ | エイリアス |
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
| **Perplexity** | `perplexity` (Web 検索内蔵) |
| **Llama** | `llama` (Groq 高速), `llama-local` (Ollama) |
| **Microsoft Phi** | `phi` (Ollama) |

LiteLLM がサポートするその他のモデルは `provider/model` 文字列を直渡しすれば動作します。

```python
LLM.complete(messages, *, tools=None, response_format="text"|"json", **overrides) -> LLMResponse
LLM.acomplete(messages, **kwargs) -> LLMResponse        # async
LLM.list_supported_providers() -> list[str]             # static
LLM.auto_detect() -> str                                 # static — 環境変数優先順位ベース
```

`LLMResponse`: `text: str`, `model: str`, `usage: dict[str, int]`, `raw: Any`,
**`tool_calls: list[dict]`** (各要素は `id` / `name` / `arguments` を持ち、
`arguments` は関数引数の JSON 文字列)。`tool_calls` は `praxia.agent.AutonomousAgent`
ループが読み取る情報源です。

### 1.3 `praxia.PersonalMemory`

```python
PersonalMemory(
    user_id: str,
    *,
    backend: str | MemoryBackend = "auto",   # "json" | "mem0" | "langmem" | "letta" | "zep" | "hindsight" | インスタンス
    storage_dir: Path | str | None = None,
    mode: "accumulate" | "read_only" | None = None,
    **backend_kwargs,
)
```

メソッド:
- `record_episode(*, flow_name, inputs, output, metadata=None) -> MemoryEntry`
- `record_fact(text, *, metadata=None) -> MemoryEntry`
- `record_preference(text, *, metadata=None) -> MemoryEntry`
- `record_outcome(*, episode_id, success, score=None, notes="") -> MemoryEntry`
- `outcomes_for(episode_id) -> list[MemoryEntry]`
- `search(query: str, limit: int = 5) -> list[str]`
- `all_entries() -> list[MemoryEntry]`
- `clear() -> None`
- プロパティ: `backend_name`, `mode`
- `set_mode(mode: "accumulate" | "read_only") -> None`

`read_only` モードでは `record_*` 全てが `MemoryEntry` (metadata に `read_only_dropped=True`) を返し、永続化はされません。

### 1.4 複数 LTM 合成

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
    router: MemoryRouter,            # RuleRouter | LLMRouter | カスタム
    write_to: str,                   # `backends` のキーである必要あり
)
```

両者とも `MemoryBackend` プロトコル実装 → `PersonalMemory(..., backend=instance)` に渡せます。

### 1.5 `praxia.memory.policy`

```python
MemoryAdminPolicy(
    enforced_backend: str | None = None,
    default_backend: str = "json",
    allowed_backends: list[str] = [],
    default_mode: "accumulate" | "read_only" = "accumulate",
    mode_locked: bool = False,
    accumulate_locked_to: list[str] = [],   # ロール名
)
MemoryAdminPolicy.load(storage_dir) -> "MemoryAdminPolicy"
MemoryAdminPolicy.save(storage_dir) -> Path
MemoryAdminPolicy.is_backend_allowed(backend) -> bool

MemoryUserPreference(user_id, backend=None, mode=None)
MemoryUserPreference.load(storage_dir, user_id) -> "MemoryUserPreference"
MemoryUserPreference.save(storage_dir) -> Path

resolve_memory_config(*, user_id, storage_dir, user_role=None,
                      requested_backend=None, requested_mode=None) -> ResolvedMemoryConfig
```

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

組込スキル: `InvestmentSkill`, `SalesSkill`, `DesignSkill`, `PurchasingSkill`, `PatentSkill`, `LegalSkill`, **`OutputFormatSkill`** (utility)。

### 1.7 `praxia.skills.output_format.OutputFormatSkill`

```python
fs = OutputFormatSkill()
fs.detect(user_request: str, *, default: str = "md") -> FormatRequest
fs.detect_with_llm(user_request: str, *, default: str = "md") -> FormatRequest
fs.deliver(content, *, user_request="", format=None, output_path=None, **exporter_kwargs) -> ExporterResult
```

`FormatRequest`: `format: str`, `confidence: float`, `reason: str`.

### 1.8 `praxia.io` エクスポータ

```python
from praxia.io.exporters import export_as, supported_formats, EXPORTERS

export_as(content, *, format: str, output_path=None, **kwargs) -> ExporterResult
supported_formats() -> list[str]
```

`ExporterResult`: `format: str`, `bytes: bytes`, `suggested_extension: str`, `output_path: Path | None`, `size: int`.

組込形式: `md` / `markdown`, `html`, `pptx`, `docx`, `json`。各エクスポータのコンストラクタ kwargs:

| エクスポータ | kwargs |
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

組込: `SalesAgentFlow`, `LogicCheckerFlow`, `RAGOptimizationFlow`。カスタムフローは `@FLOWS.register_decorator(name)` または entry-point。

### 1.9.1 `praxia.agent.AutonomousAgent`

LLM 駆動のツール使用ループを Praxia スタック全体 (メモリ /
スキル / コネクタ / 凍結層) に対して実行する自律エージェント。

```python
from praxia.agent import AutonomousAgent, AgentResult, ToolCallTrace
from praxia.agent.tools import AgentTool, builtin_tools

agent = AutonomousAgent(
    user_id: str,
    *,
    role: str = "member",
    org_id: str = "default-org",
    llm: LLM | None = None,                   # 既定は LLM() (auto-detect)
    memory_dir: str | Path = ".praxia",
    memory_backend: str = "auto",
    connector_configs: dict[str, dict] | None = None,    # {"box": {"access_token": "..."}}
    enable_tools: list[str] | None = None,    # ホワイトリスト (`final_answer` は常時保持)
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

`images` — 当該ターンの画像添付 (任意)。各要素は `{"data": "<base64>", "mime": "image/png"}`。OpenAI/LiteLLM の `image_url` content part として送出されるため、Vision 対応モデル (Claude 3+, GPT-4o, Gemini 1.5+ 等) が前提。`history` 側のメッセージは過去ターンに添付があった場合 multi-content 形式が含まれる場合がある。

`AgentResult`:
- `final_text: str`
- `tool_calls: list[ToolCallTrace]` — 全ツール呼出の記録
- `steps: int`
- `stopped_reason: "completed" | "max_steps" | "error"`
- `usage: dict[str, int]` — 累計入出力トークン

`ToolCallTrace`:
- `step: int`, `name: str`, `arguments: dict`, `arguments_text: str`
- `result: Any`, `result_text: str`
- `ok: bool`, `error: str`

**会話の永続化 (`praxia.data.threads`):**

`ThreadStore` が Agent 会話を 1 スレッド = 1 JSON ファイル (`.praxia/chats/<user_id>/<thread_id>.json`) で保存。Streamlit UI は `💬 会話履歴` ポップオーバから一覧 / 再開 / 改名 / 削除を行う。エフェメラルチェック ON 時は永続化を完全にスキップ。

```python
from praxia.data.threads import ChatMessage, ChatThread, ThreadStore

store = ThreadStore(memory_dir / "chats")
thread = store.create("alice")                               # 空スレッド
thread.messages.append(ChatMessage(role="user",
                                   content="この図表は何を示してる?",
                                   images=[{"data": b64, "mime": "image/png"}]))
store.save(thread)                                           # 初回ユーザメッセージで自動タイトル付与
threads = store.list_for_user("alice")                       # 更新降順
store.rename("alice", thread.id, "Q3 図表レビュー")
store.delete("alice", thread.id)
```

`ChatMessage` フィールド: `role` / `content` / `timestamp` / `trace` (`AgentResult.tool_calls` の永続化形) / `images` (base64+mime の dict 配列)。

**組込ツール 11 種** (`praxia.agent.tools.builtin_tools()` で取得可能):

| ツール | レイヤ | 備考 |
|---|---|---|
| `search_personal_memory` | 1 | 個人メモリ検索 |
| `search_org_memory` | 3 | 組織共有ブロック検索 |
| `search_frozen_layer` | 4 | `.praxia/frozen/**.md` 部分文字列検索 |
| `list_skills` | — | `domain=` 任意フィルタ |
| `list_personal_skills` | 6 | ユーザ個人カタログ |
| `list_org_skills` | 6 | 実効カタログ (org + distributed + personal) |
| `run_skill` | 6 | スキル名 + テキスト入力で起動 |
| `list_connectors` | — | `CONNECTORS` レジストリから |
| `pull_from_connector` | — | **ACL チェック** (`auth.policies.require`)、監査済 |
| `record_fact` | 1 | `read_only` モード時 no-op |
| `final_answer` | — | ループ終了センチネル |

全ツール呼出は成否を問わず `auth.audit.record(...)` で記録。

エージェント自体は `praxia.mcp.server.build_tools` 経由で MCP メタツール
`autonomous_agent` としても公開、リモート MCP クライアント (Claude Desktop /
Cursor) から個別ツール配線なしで委譲可能。

### 1.10 `praxia.auth`

```python
auth = AuthManager(storage_dir=".praxia/auth", bootstrap_admin: str | None = None)
auth.create_user(username, *, role: Role, email=None) -> tuple[User, raw_api_key]
auth.authenticate(*, api_key=None, token=None) -> User | None
auth.authorize(user, action: str, resource: str | None = None) -> bool
auth.require(user, action, resource=None) -> None              # PermissionError raise
auth.issue_token(user_id) -> str                               # JWT
auth.grant_role(username, role: Role) -> None
auth.update_user(username, **fields) -> User
auth.deactivate_user(username) -> None
auth.delete_user(username) -> bool
auth.audit.write(actor_id, action, resource=None, success=True, metadata=None) -> None
auth.audit.tail(limit=100) -> list[AuditEvent]
auth.policies.add(*, effect, resource_type, resource_pattern, actions, principals, description) -> Policy
auth.policies.evaluate(...) -> Decision
auth.policies.require(...) -> None
auth.exports.export_audit(...) -> Path
auth.exports.export_users(...) -> Path
auth.exports.export_personal_memory(...) -> Path
auth.exports.export_policies(...) -> Path
auth.exports.export_shared_memory(...) -> Path
```

ロール: `Role.ADMIN`, `Role.OPERATOR`, `Role.MEMBER`, `Role.VIEWER`.

### 1.11 `praxia.connectors`

```python
from praxia.connectors import get_connector, list_builtin

conn = get_connector(name: str, **provider_kwargs)
items: list[ConnectorItem] = conn.pull(path: str, *, limit=100)
receipt = conn.push(path: str, data: ConnectorItem | dict)
```

組込: `box`, `sharepoint`, `dropbox`, `gdrive`, `kintone`, `salesforce`. ユーザ委譲 OAuth 利用時は `access_token` の代わりに `user_id="..."` を渡す。

### 1.12 `praxia.connectors.oauth`

```python
OAuthFlow(
    provider_config, *,
    client_id, client_secret, redirect_uri,
    token_store=None,    # OAuthTokenStore
    state_store=None,    # PersistentStateStore — multi-worker 必須
)
flow.authorization_url(user_id) -> tuple[url, state]
flow.exchange_code(code, state) -> OAuthToken

OAuthTokenStore(
    storage_dir, *,
    encryption_secret=None,
    kms=None,           # KmsAdapter; 既定 = build_adapter(PRAXIA_KMS_ADAPTER or "local")
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

事前登録プロバイダ: `BOX_OAUTH`, `MICROSOFT_OAUTH`, `DROPBOX_OAUTH`, `GOOGLE_OAUTH`, `SALESFORCE_OAUTH`.

### 1.12.1 `praxia.connectors.oauth.kms` — KMS アダプタ

```python
class KmsAdapter(Protocol):
    name: str
    def wrap(self, dek: bytes) -> bytes: ...    # 32 byte DEK 暗号化
    def unwrap(self, wrapped: bytes) -> bytes:  # 復号 → 32 byte DEK

KMS_ADAPTERS: Registry[KmsAdapter]   # entry-point グループ: praxia.kms_adapters

build_adapter(name=None, **kwargs) -> KmsAdapter
# name 解決順: 引数 > PRAXIA_KMS_ADAPTER 環境変数 > "local"

envelope_encrypt(adapter, plaintext: bytes) -> dict
envelope_decrypt(adapter, envelope: dict) -> bytes
```

組込アダプタ:
- `LocalKmsAdapter(secret=...)` — HKDF / AES-GCM、開発のみ
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

対応拡張子: `pdf`, `docx`, `pptx`, `xlsx`, `csv`, `json`, `yaml`, `yml`, `xml`, `html`, `htm`, `md`, `markdown`, `txt`.

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
    traffic_split: dict[str, float] = {}      # 省略時は均等分割
    description: str = ""
    status: str = "draft"
    target_audience: dict[str, Any] = {}      # {"roles": [...], "users": [...]} or {} で全員
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

# 純関数アサインメント (ストレージ無し)
assign_variant(exp: Experiment, *, user_id: str) -> Variant | None
```

アサインメントは決定論的: `SHA-256(experiment_id + ":" + user_id)` mod traffic_split。

### 1.16 `praxia.extensions.Registry` (プラグインコア)

```python
reg: Registry[T] = Registry(name: str, entry_point_group: str | None = None)
reg.register(name, cls)                      # 直接
reg.register(name, lazy("module:Class"))     # 遅延
reg.register_decorator(name)                 # デコレータ
reg.unregister(name) -> bool
reg.has(name) -> bool
reg.get(name) -> type[T]                     # 不在で KeyError
reg.list() -> list[str]
reg.items() -> list[tuple[str, type[T]]]
```

---

## 2. CLI

全コマンド `--help` で詳細。カテゴリ別に列挙:

### 2.1 ライフサイクル
- `praxia init [--user-id ID] [--backend BACKEND] [--model MODEL]`
- `praxia run sales|logic|rag [...flow 引数]`
- `praxia consolidate [--threshold 0.75] [--dry-run]`
- `praxia freeze --block LABEL`
- `praxia ui [--port 8501]`
- `praxia serve [--host 127.0.0.1] [--port 8000] [--cors-origin URL]` *(`[server]` extra 必須)*

### 2.2 検索 / 一覧
- `praxia list flows | skills | models | backends`
- `praxia connector list`
- `praxia config show | path | get KEY | set KEY VALUE | init`

### 2.3 スキル / フロー
- `praxia skill run <name> "<input>"`
- `praxia skill promote <name>`
- `praxia skill distribute <name> --target-roles role1,role2`

### 2.3.1 自律エージェント
- `praxia agent run "<task>" [--user-id alice] [--role member] [--org-id default-org] [--model auto] [--max-steps 10] [--enable-tools t1,t2,...] [--show-trace/--no-show-trace]`
- `praxia agent tools` — 組込ツール 11 種を説明文付で列挙

### 2.4 ユーザ管理 (admin)
- `praxia user create <name> --role ROLE [--email]`
- `praxia user list`
- `praxia user grant <name> ROLE`
- `praxia user update <name> [--email] [--role]`
- `praxia user deactivate <name>`
- `praxia user delete <name>`
- `praxia user rotate-key <name>`
- `praxia user audit [--limit N]`

### 2.5 プロンプト
- `praxia prompt create --user-id ID --name N --body B`
- `praxia prompt list [--user-id] [--scope personal|org|distributed]`
- `praxia prompt distribute --name N --target-roles ...`
- `praxia prompt delete --user-id --name`

### 2.6 コネクタ
- `praxia connector pull <name> <path> [--user-id] [--limit]`
- `praxia connector push <name> <path> --content-file FILE [--user-id]`

### 2.7 ユーザ委譲 OAuth
- `praxia oauth start <provider> --user-id ID`
- `praxia oauth list --user-id ID`
- `praxia oauth revoke <provider> --user-id ID`

### 2.8 アクセスポリシー (ACL)
- `praxia policy add ALLOW|DENY RESOURCE_TYPE PATTERN --principals ROLE1,USER1 --description ...`
- `praxia policy list`
- `praxia policy remove POLICY_ID`
- `praxia policy test USER ROLE RESOURCE_TYPE RESOURCE_ID ACTION`

### 2.9 メモリ モード / バックエンド (ユーザ毎、admin 制御)
- `praxia memory mode --user-id ID accumulate|read_only`
- `praxia memory backend --user-id ID BACKEND`
- `praxia memory show --user-id ID [--role ROLE]`
- `praxia admin memory-policy-show`
- `praxia admin memory-policy-set [--enforced-backend B] [--default-backend B] [--allowed B1,B2] [--default-mode M] [--mode-locked] [--accumulate-locked-roles R1,R2]`

Streamlit UI からは **Admin → Settings → 🧠 メモリポリシー** 画面で同じ `MemoryAdminPolicy` (`.praxia/admin/memory_policy.json`) をフォーム編集可能。**ユーザ向けメモリ設定 UI は意図的に存在しません** — メモリのバックエンドとモードは管理者専管事項です。`MemoryUserPreference` SDK クラスは API としては残置 (プログラム経由の利用向け) ですが、UI からの書き込み経路はありません。

### 2.10 出力エクスポータ
- `praxia export <input.md> <output.html|.pptx|.docx|.json> [--format] [--title]`

### 2.10b A/B 実験
- `praxia experiment create <id> --name N --variants '{...}' [--traffic-split "..."]`
- `praxia experiment list`
- `praxia experiment {start|pause|finish|delete} <id>`
- `praxia experiment results <id>`

### 2.11 管理者エクスポート (コンプライアンス / SIEM)
- `praxia admin export-audit OUTFILE --format csv|json|jsonl --since-days N --actor USER`
- `praxia admin export-users OUTFILE --format json|csv`
- `praxia admin export-memory DIR --user-id USER` *(または `--all`)*
- `praxia admin export-policies OUTFILE --format json|csv`
- `praxia admin export-shared-memory OUTFILE --format jsonl|json`

---

## 3. HTTP API (`praxia serve`)

`/api/v1` 配下にバージョニング。`/auth/login` 以外は `X-API-Key` または `Authorization: Bearer <jwt>` が必須。

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
| GET | `/api/v1/oauth/{provider}/callback` | (query: code, state) | HTML 成功画面または 302 リダイレクト |
| GET | `/api/v1/oauth/{provider}/status` | — | `{"authorized", "expires_at", "is_expired", "scope"}` |
| DELETE | `/api/v1/oauth/{provider}` | — | `{"deleted": bool}` |

CORS: `--cors-origin URL` (繰り返し可) で設定。

---

## 4. 設定インターフェース

優先順位: env > `.env` > `.praxia/config.toml`. 正準キー一覧は `.env.example` 参照。

| カテゴリ | キー |
|---|---|
| LLM | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_BASE` |
| Memory | `PRAXIA_MEMORY_BACKEND`, `PRAXIA_MEMORY_MODE`, `QDRANT_URL` |
| Auth | `PRAXIA_JWT_SECRET`, `PRAXIA_TOKEN_ENC_KEY`, `PRAXIA_LOCAL_MODEL` |
| KMS (トークン暗号化) | `PRAXIA_KMS_ADAPTER` (`local`/`aws`/`azure`/`gcp`/`vault`) + アダプタ別 kwargs |
| HTTP server | `PRAXIA_PUBLIC_URL` (redirect URI 固定), `PRAXIA_OAUTH_SUCCESS_REDIRECT` |
| SSO | `PRAXIA_SSO_PROVIDER`, `PRAXIA_SSO_CLIENT_ID`, `PRAXIA_SSO_CLIENT_SECRET`, `PRAXIA_SSO_REDIRECT_URI`, `PRAXIA_SSO_TENANT_ID`, `PRAXIA_SSO_OKTA_DOMAIN`, `PRAXIA_SSO_KEYCLOAK_BASE_URL`, `PRAXIA_SSO_KEYCLOAK_REALM`, `PRAXIA_SSO_ISSUER_URL` |
| OAuth | `PRAXIA_OAUTH_BOX_CLIENT_ID/SECRET`, `PRAXIA_OAUTH_MICROSOFT_*`, `PRAXIA_OAUTH_DROPBOX_*`, `PRAXIA_OAUTH_GOOGLE_*`, `PRAXIA_OAUTH_SALESFORCE_*` |
| Connectors | `PRAXIA_CONN_<NAME>_<UPPERCASE_KEY>` (legacy / service-account fallback) |
| Audio | `ELEVENLABS_API_KEY` (OpenAI 系は `OPENAI_API_KEY` を流用) |

---

## 5. プラグインプロトコル (entry-point グループ)

各拡張ポイントは entry-point で発見可能。実装 → 宣言 → install。Praxia コアは触らない。

| グループ | 実装する Protocol | 組込件数 |
|---|---|---|
| `praxia.connectors` | `Connector` (`name`, `pull`, `push`) | 6 |
| `praxia.memory_backends` | `MemoryBackend` (`add`, `search`, `all`, `clear`) | 6 |
| `praxia.parsers` | `Parser` (`parse`, `extensions`) | 8 |
| `praxia.exporters` | `Exporter` (`format`, `extensions`, `export`) | 5 |
| `praxia.oauth_providers` | `OAuthProviderConfig` インスタンス | 5 |
| `praxia.skills` | `Skill` サブクラス + `manifest` | 6 (+1 utility) |
| `praxia.flows` | `Flow` サブクラス + `name`, `description`, `run()` | 3 |
| `praxia.kms_adapters` | `KmsAdapter` (`name`, `wrap`, `unwrap`) | 5 (local + 4 cloud) |

詳細: [`docs/PLUGINS.md`](../PLUGINS.md), [`docs/CUSTOM_CONNECTORS.ja.md`](../CUSTOM_CONNECTORS.ja.md).

---

## 6. エラーモデル

| 例外 | 発生箇所 | server モジュールでの HTTP マップ |
|---|---|---|
| `MissingDependencyError` | 任意 SDK 不在 | 503 |
| `ValueError` | 不正入力 | 400 |
| `KeyError` | レジストリに存在しない名前 | 404 |
| `PermissionError` | RBAC / ACL 拒否 | 403 |
| `ImportError` | 任意 extras 未 install | 503 |
| `RuntimeError` | 内部論理エラー | 500 |

HTTP サーバはサーバ側でログ詳細を残し、クライアントにはサニタイズしたメッセージを返します。

---

## 7. 後方互換性

- 上記の公開クラス / 関数シグネチャは v1.x で安定
- 新機能は **デフォルト値付き** の引数追加のみ。既存引数の意味変更はしない
- 公開名の削除はメジャーバージョン UP + 1 マイナーの間 deprecation warning が必須
- プラグイン Protocol (`MemoryBackend`, `Connector`, ...) は v1.x で **凍結**。メソッド追加は破壊的変更扱い → 必要時は `MemoryBackendV2` 等を別途追加
