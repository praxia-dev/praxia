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

**Minimum**: set at least one LLM provider key:

```bash
ANTHROPIC_API_KEY=sk-ant-...      # recommended
# or
OPENAI_API_KEY=sk-...             # also enables Whisper STT + OpenAI TTS
# or
GEMINI_API_KEY=...                # Google Gemini
# or
DASHSCOPE_API_KEY=...             # Alibaba Qwen API
```

To run **fully on-prem** with no cloud LLM:

```bash
ollama pull qwen2.5:14b
praxia run sales --model qwen-local --customer-name "Acme" --product "BizFlow"
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

## 7. Personal-to-org memory distillation

Run the nightly batch that promotes effective patterns from individual
memory to organizational blocks:

```bash
praxia consolidate --dry-run                 # preview what would be promoted
praxia consolidate --threshold 0.75          # production threshold
praxia freeze --block team_norms             # freeze a stable block to git-tracked Markdown
```

## 8. Per-user OAuth (recommended for enterprise)

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

## 9. Admin operations

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

## 10. Discover what's available

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
or open an issue at <https://github.com/genarch/praxia/issues>.
