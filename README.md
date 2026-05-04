# Praxia

> **Specialized Multi-Agent Orchestrator with Cyclic Personal/Organizational Memory**
>
> A workflow-specific multi-agent orchestrator that **automatically promotes** individual tacit knowledge into organizational know-how. Built on a 5-layer memory stack with three independent promotion paths.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

> 🇯🇵 日本語版の各業務別記事 (Zenn): [docs/zenn/](docs/zenn/)
> 🔍 Complete feature reference: [docs/FEATURES.md](docs/FEATURES.md)
> 📊 Concrete Before/After tables: [docs/use-cases.md](docs/use-cases.md)
> 💼 Business growth plan (JP): [docs/business-plan.ja.md](docs/business-plan.ja.md)

---

## 🎯 Why Praxia?

General-purpose multi-agent frameworks (CrewAI, AutoGen, LangGraph, …) are powerful but stop short on these four problems:

| Problem with existing frameworks | Praxia's approach |
|---|---|
| Setup is complex; production deployment is hard | **Workflow-specific templates** (sales prep / logic check / RAG optimization) that run in 5 minutes |
| Senior-engineer "magic prompts" stay locked in one person's editor | **Personal-to-org auto-promotion pipeline** built in |
| "It works" doesn't prove "it works *well*" | **Hallucination detection + retrieval evals** shipped by default |
| Agents stagnate after launch | **Sleep-time consolidation** distills your past flows nightly |

Praxia turns "one expert's drawer" into "everyone's best practices."

---

## 🏗 Architecture — 5-Layer Memory Stack

```
┌──────────────────────────────────────────────────────────┐
│  AI Agents (Skills + MCP)                                │
└──────────────┬───────────────────────────────────────────┘
               │ Users just have normal conversations
               ▼
╔═══════════════════════════════════════════════════════════╗
║ Layer 1: Personal memory (auto-extracted)                 ║
║   Mem0 / LangMem / HindSight / Letta / Zep / JSON         ║
║   namespace = user_id                                     ║
║   ★ Zero-effort tacit-knowledge capture                   ║
╚══════════════╤════════════════════════════════════════════╝
               │ Sleep-time Consolidation (nightly batch)
               ▼
╔═══════════════════════════════════════════════════════════╗
║ Layer 2: Distillation & promotion engine                  ║
║   Three parallel "validity tests":                        ║
║     ① Frequency  (recurring across N+ users)              ║
║     ② Outcome    (correlated with wins/losses)            ║
║     ③ Self-eval  (LLM scored)                             ║
╚══════════════╤════════════════════════════════════════════╝
               │ Auto-promote above threshold; queue otherwise
               ▼
╔═══════════════════════════════════════════════════════════╗
║ Layer 3: Shared memory (living organizational knowledge)  ║
║   Letta-style shared blocks; all agents read/write        ║
╚══════════════╤════════════════════════════════════════════╝
               │ PR review for high-impact items
               ▼
╔═══════════════════════════════════════════════════════════╗
║ Layer 4: Frozen layer (git-managed best practices)        ║
║   Markdown + git + PR review                              ║
║   GitHub Copilot / Cursor Rules-compatible format         ║
╚══════════════╤════════════════════════════════════════════╝
               │ (optional)
               ▼
╔═══════════════════════════════════════════════════════════╗
║ Layer 5: Graph layer (only relationship-heavy domains)    ║
║   Zep / Graphiti — decisions, customer 360, incident DAG  ║
╚═══════════════════════════════════════════════════════════╝

Parallel Layer 6: Skills registry
  Personal skills get promoted to the organizational catalog.
  MCP / Claude Skills / Cursor Skills compatible.
```

Three promotion paths (**auto / statistical / manual**) run side by side — never depending on a single mechanism.

For details, see [docs/architecture.md](docs/architecture.md).

---

## ✨ What's Bundled

### 3 Specialized Multi-Agent Flows

| Flow | What it does |
|---|---|
| **SalesAgentFlow** | Reads customer IR, past minutes, RAG context → generates **hypotheses → FAQ → proposal outline** |
| **LogicCheckerFlow** | Three agents (structure / contradiction / reader) review long documents for logical consistency |
| **RAGOptimizationFlow** | Self-correcting RAG: query expansion → retrieval → relevance eval → hallucination check loop |

### 6 Default Business-Domain Skills

| Skill | Domain | Use cases |
|---|---|---|
| **InvestmentSkill** | Investment | Equity research, due diligence, portfolio decisions |
| **SalesSkill** | Sales | Account research, proposal drafting, FAQ prep |
| **DesignSkill** | Engineering Design | System design review, requirements engineering |
| **PurchasingSkill** | Procurement | Supplier evaluation, RFQ analysis, TCO, BCP risk |
| **PatentSkill** | IP / Patent | Prior-art search, claims drafting, patent maps |
| **LegalSkill** | Legal | Contract review, compliance, M&A diligence |

Each skill serializes to Claude-Skills / MCP-compatible `SKILL.md`.

### All Major LLMs

LiteLLM-powered single-line provider switching:

| Provider | Aliases | Auth |
|---|---|---|
| Anthropic Claude | `claude` / `claude-sonnet` / `claude-haiku` | `ANTHROPIC_API_KEY` |
| OpenAI ChatGPT | `chatgpt` / `gpt-4o` / `o1` | `OPENAI_API_KEY` |
| Google Gemini | `gemini` / `gemini-flash` | `GEMINI_API_KEY` |
| Alibaba Qwen (cloud) | `qwen` / `qwen-72b` | `DASHSCOPE_API_KEY` |
| Qwen / Llama (local) | `qwen-local` (Ollama) | (none — runs in-house) |

```python
LLM("claude")        # Anthropic Claude
LLM("qwen-local")    # Local Qwen via Ollama
LLM("openai/gpt-4o") # Any LiteLLM-compatible model string
```

### 6 Pluggable LTM Backends

| Backend | Notes |
|---|---|
| **json** (default) | Zero-dependency, JSONL on disk, fully auditable |
| **mem0** | Entity linking + hybrid search (recommended for production) |
| **langmem** | LangChain LangMem SDK |
| **letta** | Letta shared blocks (with read-only policy support) |
| **zep** | Zep / Graphiti for temporal KGs (Layer 5) |
| **hindsight** | [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) — agent memory store |

Switch with one line:
```python
PersonalMemory(user_id="alice", backend="mem0")
```

### Built-in Authentication, RBAC, SSO & Resource Policies

- **API-key + JWT auth** (`praxia.auth`) with 4 default roles (`admin` / `operator` / `member` / `viewer`)
- **SSO via OIDC**: Google, Microsoft Entra ID, Okta, GitHub, Keycloak, custom OIDC, plus SAML skeleton
- **Resource access policies (ACL)** — glob-pattern allow/deny rules per resource (built for enterprise IS departments)
- **Append-only audit log** — every authn / authz / policy decision / privileged action recorded
- **Admin data exports** — CSV / JSON / JSONL dumps of audit, users, usage, memory, policies, shared blocks (chain-of-custody preserved)

### Admin User Management
- Create / read / update / delete users
- Activate / deactivate, role grants, API-key rotation
- All actions audited
- Available via CLI, Streamlit UI, and SDK

### Custom Prompts (per-user + admin-distributed)
- Users save personal prompts; admins promote them to org or distribute to specific users / roles
- Three scopes (personal / org / distributed) with merge precedence
- Same model as the skill registry

### External Connectors — 6 systems, Pull + Push
| Connector | Pull | Push | Auth |
|---|---|---|---|
| **Box** | ✅ folder → files | ✅ upload to folder | OAuth2 / JWT |
| **SharePoint / M365** | ✅ drive folder → files | ✅ upload to folder | Microsoft Entra app |
| **Dropbox** | ✅ folder → files | ✅ upload to folder | OAuth2 |
| **Google Drive** | ✅ parent folder → files | ✅ upload to folder | Service account / OAuth |
| **kintone** | ✅ app + query → records | ✅ create record | API token / basic |
| **Salesforce** | ✅ SOQL → records | ✅ sObject create | Username/token / OAuth |

Pull data into agent flows; push agent outputs back to your system of record. All access subject to admin policies.

### Dashboards
- **Personal**: flow runs, skill invocations, memory entries, outcome success rate, token usage, top skills, recent episodes
- **Organizational**: active users, total invocations, promoted/frozen/distributed counts, top users, top skills, audit event counts

---

## 🚀 Quickstart

```bash
pip install praxia                   # Core
pip install "praxia[ui]"             # + Streamlit UI
pip install "praxia[connectors]"     # + Box / SharePoint / Dropbox / GDrive / kintone / Salesforce
pip install "praxia[all]"            # Everything

# Initialize (creates personal memory + skill registry + admin user)
praxia init --backend json --model auto

# Run a flow
praxia run sales --customer-name "Acme" --product "BizFlow"
praxia run logic --document path/to/doc.md
praxia run rag --question "What license is Praxia released under?"

# Run a business skill
praxia skill run investment "Mid-term investment thesis on Sony Group stock"
praxia skill run legal "Review the risk in this services agreement"

# Launch the UI (11 tabs incl. Dashboard / Policies / Admin / Connectors)
praxia ui --port 8501

# Personal → org memory distillation
praxia consolidate --dry-run
praxia freeze --block team_norms

# Dashboards
praxia dashboard --scope personal --user-id alice
praxia dashboard --scope org

# Admin: user management
praxia user create alice --role member
praxia user update alice --role operator --email alice@a.test
praxia user deactivate alice
praxia user delete alice --yes
praxia user audit --limit 100

# Admin: resource access policies (ACL — for IS depts)
praxia policy add deny connector "box:/Confidential/*" \
    --principals "role:member,role:viewer" \
    --description "Lock Confidential folder to operators+"
praxia policy list
praxia policy test alice member connector box:/Confidential/q3.pdf read

# Admin: data exports (CSV / JSON / JSONL — every export audit-logged)
praxia admin export-audit audit.csv --since-days 30
praxia admin export-users users.json --format json
praxia admin export-memory ./memory_backup --all
praxia admin export-policies policies.json

# External connectors (Pull / Push, subject to ACL)
praxia connector list
praxia connector pull box 0 --limit 20 --save-to ./box_pulled
praxia connector push salesforce Lead lead.json
praxia connector pull kintone "42?status='open'"

# Custom prompts (per-user + admin distribution)
praxia prompt create my_qualifier prompt_body.txt
praxia prompt list
praxia prompt distribute curated_prompt body.md --target-roles member

# Skill registry — promotion and admin distribution
praxia skill promote --candidates
praxia skill distribute investment_analyst --target-roles member,operator
```

Minimal Python example:

```python
from praxia import Praxia
from praxia.flows import SalesAgentFlow
from praxia.skills import InvestmentSkill

m = Praxia(user_id="alice", default_model="claude")

# Run a multi-agent flow
result = m.run(SalesAgentFlow, inputs={
    "customer_name": "Acme",
    "product": "BizFlow",
})

# Run a single business skill
print(InvestmentSkill().run("3-year investment thesis on Toyota"))

# Personal memory accumulates automatically — no explicit save needed.
# The nightly consolidator promotes effective patterns to org memory.
m.consolidate(dry_run=True)
```

Full guide: [docs/quickstart.md](docs/quickstart.md).

---

## 📐 Design Philosophy

### 1. Capture tacit knowledge with **zero effort**
No explicit `CLAUDE.md`-style writing. Mem0/LangMem/HindSight extract entities and preferences from ordinary conversations.

### 2. Promote only what's **effective**, **automatically**
Three independent verdicts run in parallel. The framework auto-promotes only when consensus is high; medium-confidence items go to a review queue.

### 3. Separate "frozen" from "living" knowledge
- Living layer (shared blocks): updated instantly, all agents see it
- Frozen layer (Markdown + git): only PR-reviewed, stable best practices

This keeps both **freshness** and **trust** intact.

### 4. Use Graph storage **only where relationships are the value**
Mem0 OSS removed `graph_store` support in April 2026. We follow that signal: vector + entity linking is the default; graphs apply only to decision histories, customer 360, and incident causal chains.

### 5. **Vendor lock-in is a non-goal**
- LiteLLM lets any provider work
- LTM backends are pluggable
- Markdown + git is the persistence layer of last resort
- Apache 2.0 license, evolving toward an open-core model

### 6. Ship "**evidence**" alongside the framework
Hallucination detection (`praxia.eval.hallucination`) and retrieval metrics (`praxia.eval.metrics`) are first-class. Customers don't have to take "it works" on faith.

For more, see [docs/design-philosophy.md](docs/design-philosophy.md).

---

## 📊 Use Cases by Industry

Detailed Before/After tables for each domain are in **[docs/use-cases.md](docs/use-cases.md)**. Highlights:

| Industry | Representative use case | Headline impact |
|---|---|---|
| Investment | Seed-stage VC due diligence | 4–6h → **45–60 min** per deck |
| Sales | Pre-meeting research + storyboard | Proposal-acceptance rate **+15–20pt** |
| Engineering Design | Requirements doc review | Senior architect time freed: **week 16h → 4h** |
| Procurement | RFQ TCO comparison | Hidden costs found: **+30%** vs initial quote |
| Patent | Prior-art search + novelty assessment | External patent-attorney fees **−50–70%** |
| Legal | M&A contract review | External law-firm costs **halved** (~$100k/deal) |

**3-year compounding effects**: New-hire ramp **6–12mo → 2–3mo** / Veteran-departure knowledge loss **→ zero** / Cross-team best-practice diffusion **30+ items/month**.

---

## 🆚 Compared with Existing Frameworks

| Capability | CrewAI | AutoGen | LangGraph | Glean | **Praxia** |
|---|---|---|---|---|---|
| Multi-agent orchestration | ✅ | ✅ | ✅ | — | ✅ |
| Workflow-specific templates | ❌ | ❌ | ❌ | ❌ | ✅ |
| Auto-extracting personal memory | ❌ | ❌ | △ | ✅ | ✅ |
| Personal → org promotion | ❌ | ❌ | ❌ | △ | ✅ |
| Sleep-time consolidation | ❌ | ❌ | ❌ | ❌ | ✅ |
| Skills registry + admin distribution | ❌ | ❌ | ❌ | ❌ | ✅ |
| Custom prompt distribution | ❌ | ❌ | ❌ | ❌ | ✅ |
| Hallucination eval bundled | ❌ | ❌ | ❌ | ❌ | ✅ |
| Built-in auth + RBAC + SSO | ❌ | ❌ | ❌ | ✅ | ✅ |
| Resource access policies (ACL) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Audit log + admin data exports | ❌ | ❌ | ❌ | ✅ | ✅ |
| Personal & org dashboards | ❌ | ❌ | ❌ | ✅ | ✅ |
| Storage / SaaS connectors (Pull + Push) | ❌ | ❌ | △ | △ | ✅ ×6 |
| MCP / Claude Skills compatible | △ | △ | △ | ❌ | ✅ |
| License | MIT | MIT | MIT | Commercial | Apache 2.0 |

---

## 🗺 Roadmap

| Phase | Scope | Status |
|---|---|---|
| **Phase 1** | Personal memory + 3 specialized flows + 6 business skills | ✅ **Done** |
| **Phase 2** | Sleep-time consolidator + statistical (outcome-correlated) promotion | ✅ **Done** |
| **Phase 3** | Shared blocks + Markdown freeze workflow + CLI | ✅ **Done** |
| **Phase 4** | Skill registry promotion (personal → org) | ✅ **Done** |
| **Phase 5** | Auth + RBAC + SSO + audit log + admin user CRUD | ✅ **Done** |
| **Phase 5+** | Resource access policies (ACL) + admin data exports + custom prompts + 6 connectors + dashboards | ✅ **Done** |
| **Phase 6** | Multi-tenant SaaS, advanced GUI, vertical editions | 🚧 Commercial |

---

## 🤝 Contributing

We're building a **community-driven library of industry recipes**. Three primary contribution paths:

1. New workflow flows (`praxia/flows/`)
2. New business skills (`praxia/skills/business/`)
3. Industry recipes (`docs/recipes/`)

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📜 License

[Apache License 2.0](LICENSE) — commercial use, modification, and redistribution permitted.

**Copyright holder**: GENARCH (sole proprietor: Genki Watanabe) and Praxia Contributors.

Third-party dependencies retain their own licenses; see [NOTICE.md](NOTICE.md) for the full attribution list.

We may evolve toward an **open-core** model: enterprise GUI / advanced audit features under a separate license, while the framework remains Apache 2.0.

---

## 🛠 Extending Praxia

Praxia uses a **single extensibility primitive** (`praxia.extensions.Registry`) for all four plugin types — connectors, memory backends, skills, flows. Adding a plugin **does not require editing any core file**.

| Plugin type | Base | Registry | Entry-point group | Lines |
|---|---|---|---|---|
| Connector | `Connector` protocol | `CONNECTORS` | `praxia.connectors` | ~50 |
| Memory backend | `MemoryBackend` protocol | `BACKENDS` | `praxia.memory_backends` | ~80 |
| Business skill | `Skill` | `SKILLS` | `praxia.skills` | ~20 |
| Multi-agent flow | `Flow` | `FLOWS` | `praxia.flows` | ~30 |
| Industry recipe | Markdown | n/a | — | n/a |

**Two ways to register**:

```python
# (a) Decorator (in-tree contributions)
from praxia.connectors.registry import CONNECTORS

@CONNECTORS.register_decorator("notion")
class NotionConnector: ...
```

```toml
# (b) Entry-point (third-party packages — no fork needed)
[project.entry-points."praxia.connectors"]
notion = "praxia_connector_notion:NotionConnector"
```

After `pip install praxia-connector-notion`, the new connector shows up automatically in `praxia connector list`, the Streamlit UI, and the SDK — with **no edit to Praxia itself**.

Full guide with examples for all 4 plugin types: **[docs/PLUGINS.md](docs/PLUGINS.md)**.

---

## 📈 ROI estimate (100-knowledge-worker mid-cap)

| Variable | Year 1 | Year 2 |
|---|---|---|
| Workers in scope (N) | 100 | 100 |
| Loaded cost / FTE (C) | ¥14M | ¥14M |
| Routine work share (t) | 40% | 40% |
| Time savings (s) | 35% | 60% |
| Quality lift (Q) | ¥10M | ¥30M |
| Praxia cost (P) | ¥12M | ¥12M |
| **Net benefit** | **¥194M** | **¥354M** |

3-year cumulative net ≈ **¥800M**. Even halving every parameter still produces > 10× ROI.

Full model + worked examples: [docs/FEATURES.md#roi-projection-model](docs/FEATURES.md#14-roi-projection-model).

---

## 📚 Acknowledgements & Inspirations

- [Mem0](https://github.com/mem0ai/mem0) — personal memory layer
- [Letta](https://github.com/letta-ai/letta) — shared memory blocks concept
- [LangMem](https://github.com/langchain-ai/langmem) — long-term memory SDK
- [LiteLLM](https://github.com/BerriAI/litellm) — unified provider abstraction
- [Claude Skills](https://docs.claude.com/) — skills registry conventions
- [Model Context Protocol](https://modelcontextprotocol.io) — tool/skill interop
- HindSight — Experience / Entity Summary / Belief model

Theoretical groundwork:
- LinkedIn Cognitive Memory Agent (Episodic + Semantic + Procedural)
- Mem0 paper (arXiv:2504.19413)
- Letta sleep-time agents

---

> **Mission**: Bridge "individual brilliance" and "organizational continuity" with AI.
