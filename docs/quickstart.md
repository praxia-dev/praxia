# Quickstart

Get from `pip install` to a running multi-agent flow in under 5 minutes.

> 🇯🇵 日本語版は [quickstart.ja.md](quickstart.ja.md) を参照。

---

## 1. Install

Pick the extras you need (everything else stays out of your dependency tree):

```bash
pip install praxia                 # Core (CLI + JSON memory + 6 skills + 3 flows)
pip install "praxia[ui]"           # + Streamlit UI
pip install "praxia[connectors]"   # + Box / SharePoint / Dropbox / Drive / kintone / Salesforce
pip install "praxia[office]"       # + PDF / Word / PowerPoint / Excel parsing
pip install "praxia[audio]"        # + Whisper STT + OpenAI / ElevenLabs TTS
pip install "praxia[all]"          # Everything (excluding *-local variants)
```

## 2. Configure once — keys live in one place

Praxia reads configuration from these sources (first match wins):

1. **Process environment variables**
2. **`.env` file** in the working directory
3. **`.praxia/config.toml`** (managed by `praxia config`)

The easiest path:

```bash
cp .env.example .env
# Edit .env and fill in just the keys you actually use
```

Or use the interactive wizard:

```bash
praxia config init     # walks through the keys most users need
praxia config show     # display current resolved config (secrets masked)
praxia config path     # show where keys are resolved from
praxia config set ANTHROPIC_API_KEY sk-ant-xxx
praxia config get OPENAI_API_KEY
```

**Minimum**: set at least one LLM provider key. `auto_detect()` picks the
first one it finds in this priority order:

```bash
ANTHROPIC_API_KEY=sk-ant-...      # → claude (recommended for tool use)
OPENAI_API_KEY=sk-...             # → chatgpt (also enables Whisper STT + OpenAI TTS)
GEMINI_API_KEY=...                # → gemini (long context / multimodal)
DEEPSEEK_API_KEY=...              # → deepseek (Chinese SOTA, ~1/10 cost)
MISTRAL_API_KEY=...               # → mistral (EU-friendly, mistral-large-latest)
XAI_API_KEY=...                   # → grok
DASHSCOPE_API_KEY=...             # → qwen (Alibaba)
COHERE_API_KEY=...                # → command-r (enterprise RAG)
PERPLEXITY_API_KEY=...            # → perplexity (web-search-augmented)
GROQ_API_KEY=...                  # → llama (3.3 70B, hundreds of tok/s)
TOGETHERAI_API_KEY=...            # → llama via Together
```

Pass an explicit alias any time with `--model <alias>`:
`claude` / `chatgpt` / `gemini` / `deepseek` / `mistral` / `grok` / `qwen` /
`command-r` / `perplexity` / `llama` / `gemma` / `phi` / `llama-local` /
`qwen-local` / `gemma-cloud` and 10+ more (see [`praxia/core/llm.py`](../praxia/core/llm.py)).

To run **fully on-prem** with no cloud LLM:

```bash
ollama pull qwen2.5:14b      # default local
ollama pull llama3.3:70b     # or Llama 3.3
ollama pull gemma2:9b        # or Gemma
ollama pull phi3.5:3.8b      # or Phi (small footprint)

praxia run sales --model qwen-local --customer-name "Acme" --product "BizFlow"
# also works: --model llama-local / gemma / phi
```

## 3. Initialize

```bash
praxia init --user-id alice --backend json --model auto
```

This creates `.praxia/` with personal memory storage, registers the 6 default
business skills with the org registry, and bootstraps an admin user.

## 4. Run a flow

Three pre-built multi-agent flows ship with Praxia:

```bash
# B2B sales preparation — IR / minutes / RAG → hypotheses → FAQ → proposal
praxia run sales --customer-name "Acme Corp" --product "BizFlow"

# Long-document logical-consistency review (3-agent crew)
praxia run logic --document spec.pdf       # auto-parses .pdf / .docx / .pptx / .xlsx / .csv

# Self-correcting RAG — query expansion → eval → hallucination check loop
praxia run rag --question "Which license is Praxia released under?"
```

## 4½. Let the LLM drive — autonomous agent

For tasks where you don't want to hand-orchestrate flows, use
`praxia.agent.AutonomousAgent`. It runs a LLM-driven tool-use
loop over personal/org memory, the frozen layer, business skills, and
external connectors — the LLM decides which tools to call and when.

```bash
# CLI — one-liner
praxia agent run "Tell me what we know about Acme and draft a proposal" \
    --user-id alice --org-id acme --max-steps 10

# List the 11 built-in tools
praxia agent tools
```

```python
# SDK
from praxia.agent import AutonomousAgent
from praxia.core.llm import LLM

agent = AutonomousAgent(user_id="alice", org_id="acme", llm=LLM("claude"))
result = agent.run("Tell me what we know about Acme and draft a proposal.")
print(result.final_text)
for tc in result.tool_calls:
    print(f"- {tc.name}({tc.arguments_text[:60]}) ok={tc.ok}")
```

Every tool call is **audit-logged** and `pull_from_connector` is
**ACL-checked**. `record_fact` is a no-op when memory mode is `read_only`.
See [FEATURES § 38](FEATURES.md#38-autonomous-agent-llm-driven-tool-use-loop)
for the full tool catalog and governance details.

## 5. Run a single business skill

Six domain-tuned skills with built-in guardrails:

```bash
praxia skill run investment "3-year thesis on a hypothetical mid-cap issuer"
praxia skill run sales      "Plan an outreach to Acme Corp (manufacturing)"
praxia skill run design     "Review the architecture in spec.md"
praxia skill run purchasing "Compare 5 supplier RFQs from suppliers.csv"
praxia skill run patent     "Prior-art search: solid-state battery design"
praxia skill run legal      "Review the risks in services_agreement.pdf"
```

## 6. Launch the UI

```bash
praxia ui --port 8501
# Open http://localhost:8501
```

11 tabs are available:

- **Run Flow** — pick flow, attach files (PDF / Office / etc.), watch each agent run
- **Skill** — invoke any of the 6 business skills with file or 🎙 voice input
- **Memory** — browse personal memory and shared org blocks
- **Consolidate** — trigger sleep-time personal-to-org promotion
- **Dashboard** — personal + org usage metrics
- **Prompts** — manage custom prompts (personal / org / distributed)
- **Users** — admin: create / update / delete / rotate keys
- **Connectors** — Pull / Push to Box / SharePoint / Dropbox / Drive / kintone / Salesforce
- **Policies** — admin: resource access policies (ACL)
- **Admin** — export audit log, users, usage, memory, policies (CSV / JSON / JSONL)
- **About**

## 7. Multi-LTM fusion + dynamic routing (optional, accuracy boost)

Different LTMs are good at different things — entity linking (Mem0),
temporal KG (Zep), audit trail (JSON), vector recall (HindSight). You can
run several at once and either fuse the results or pick per-query.

```python
from praxia.memory.composite import CompositeBackend, WeightedBackend
from praxia.memory.backends import load_backend
from praxia import PersonalMemory

# A. Parallel fan-out + Reciprocal Rank Fusion
composite = CompositeBackend(
    backends=[
        WeightedBackend("mem0",      load_backend("mem0"),      weight=1.5),
        WeightedBackend("zep",       load_backend("zep"),       weight=1.0),
        WeightedBackend("hindsight", load_backend("hindsight"), weight=1.0),
    ],
    fusion="rrf",       # rrf | union | intersection | weighted | llm_rerank
    write_to="mem0",    # writes go here only; reads fan-out
)
pm = PersonalMemory(user_id="alice", backend=composite)
```

```python
# B. Dynamic routing — query-aware backend selection
from praxia.memory.router import RoutedBackend, RuleRouter

routed = RoutedBackend(
    backends={
        "mem0":      load_backend("mem0"),
        "zep":       load_backend("zep"),
        "hindsight": load_backend("hindsight"),
        "json":      load_backend("json"),
    },
    router=RuleRouter(),   # or LLMRouter(llm=praxia.llm) for LLM-classified routes
    write_to="mem0",
)
pm = PersonalMemory(user_id="alice", backend=routed)
```

The rule router auto-detects English **and** Japanese keywords:
temporal (`last week` / `先月`) → Zep, audit (`changelog` / `履歴`) → JSON,
entity (`who is` / `について`) → Mem0, similarity (`類似`) → HindSight.

See [FEATURES.md § 5.1](FEATURES.md#51-multi-ltm-fusion--dynamic-routing-accuracy-boost) for the full strategy table and tradeoffs.

## 8. Personal-to-org memory distillation

Run the nightly batch that promotes effective patterns from individual
memory to organizational blocks:

```bash
praxia consolidate --dry-run                 # preview what would be promoted
praxia consolidate --threshold 0.75          # production threshold
praxia freeze --block team_norms             # freeze a stable block to git-tracked Markdown
```

## 8a. Production-grade OAuth + KMS encryption

For multi-worker / multi-host deployments, run the FastAPI server and configure a KMS adapter:

```bash
# Install with server + KMS extras
pip install "praxia[server,kms-aws]"   # or kms-azure / kms-gcp / kms-vault

# Pin the public URL so the redirect URI is stable
export PRAXIA_PUBLIC_URL=https://praxia.example.com

# Switch to KMS-backed envelope encryption
export PRAXIA_KMS_ADAPTER=aws
export PRAXIA_KMS_KEY_ID=arn:aws:kms:us-east-1:111122223333:key/...

praxia serve --host 0.0.0.0 --port 8000
```

OAuth endpoints exposed under `/api/v1/oauth/{provider}/`:
- `POST /start` — build authorization URL for current user
- `GET /callback` — handle IdP redirect, exchange code, save token
- `GET /status` — token presence + expiry
- `DELETE` — revoke locally

State is shared across workers via a TTL-pruned JSON file, so the redirect can land on any replica.

## 8b. A/B experiments

```bash
# Define an experiment (DRAFT)
praxia experiment create proposal_v2 \
    --name "Proposal: shorter vs longer prompt" \
    --variants '{"control":{"prompt":"<800-word>"},"candidate":{"prompt":"<400-word>"}}' \
    --traffic-split "control=0.5,candidate=0.5"

# Activate
praxia experiment start proposal_v2

# Inspect results once enough outcomes are recorded
praxia experiment results proposal_v2
# → 🏆 Tentative winner: candidate (confidence 0.41)
```

In your skill / flow, retrieve the variant for the current user:

```python
from praxia.experiments import ExperimentRegistry

reg = ExperimentRegistry()
variant = reg.assign("proposal_v2", user_id="alice", role="member")
prompt = variant.payload["prompt"] if variant else default_prompt
```

The same user always sees the same variant during the experiment (SHA-256 bucket). Outcomes are recorded via `record_outcome()` and rolled up per variant.

## 8c. LLM output quality evaluation

```bash
# Skipped by default (requires real API keys + costs tokens)
pytest tests/llm_eval -m llm_eval -v

# Update baselines after a known-good change
pytest tests/llm_eval --update-baselines

# Compare a different model on the same cases
pytest tests/llm_eval --llm-eval-model gpt-4o
```

Each PR is graded against a committed baseline; a > 5pt score drop fails CI. See [docs/EVALUATION.md](EVALUATION.md).

## 9. Per-user OAuth (recommended for enterprise)

Each Praxia user authorizes external systems with **their own credentials** —
the external system's native ACL is enforced per-user.

```bash
# Once: register OAuth apps and add client credentials to .env
PRAXIA_OAUTH_BOX_CLIENT_ID=...
PRAXIA_OAUTH_BOX_CLIENT_SECRET=...

# Per user: authorize once
praxia oauth start box --user-id alice
# Open the URL → log in to Box → token saved encrypted

# From now on, alice's connector calls use her token
praxia connector pull box 0 --user-id alice
```

Supported providers: Box, Microsoft (SharePoint/OneDrive), Dropbox,
Google Drive, Salesforce. See [PLUGINS.md](PLUGINS.md) to add more.

## 10. Admin operations

```bash
# User management (audited)
praxia user create alice --role member
praxia user update alice --role operator --email alice@a.test
praxia user audit --limit 100

# Resource access policies (for IS departments)
praxia policy add deny connector "box:/Confidential/*" \
    --principals "role:member,role:viewer" \
    --description "Block Confidential folder for non-operators"
praxia policy test alice member connector box:/Confidential/q3.pdf read

# Data exports (chain-of-custody — every export self-audits)
praxia admin export-audit audit.csv --since-days 30
praxia admin export-users users.json --format json
praxia admin export-memory ./backup --all
```

## 11. Discover what's available

```bash
praxia list flows         # available multi-agent flows
praxia list skills        # 6 business-domain skills
praxia list models        # supported LLM aliases
praxia list backends      # memory backends
praxia connector list     # external connectors
```

---

## Troubleshooting

**"No LLM provider key found"** → run `praxia config init` and add at least
one of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` /
`DASHSCOPE_API_KEY`, or use `qwen-local` with Ollama running.

**File parsing fails** → install the office extra: `pip install "praxia[office]"`.

**Audio input/output silent** → install `praxia[audio]` and ensure your
LLM provider key is set (Whisper / OpenAI TTS reuse `OPENAI_API_KEY`).

**OAuth flow fails with "Unknown state"** → the state cache is in-memory.
For production, replace the in-memory state store with Redis / DB; see
[FEATURES.md § 25](FEATURES.md#25-user-delegated-oauth-per-user-external-system-access).

For more, see [docs/FEATURES.md](FEATURES.md), [docs/PLUGINS.md](PLUGINS.md),
or open an issue at <https://github.com/praxia-dev/praxia/issues>.
