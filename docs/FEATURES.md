# Praxia — Complete Feature Reference

Everything Praxia ships, organized for evaluators, integrators, and adopters.

> Looking for a quick overview? Start with [README.md](../README.md).
> Need workflow-specific Before/After tables? See [docs/use-cases.md](use-cases.md).
> Need extensibility patterns? See [Extending Praxia](#extending-praxia) below.

---

## Table of contents

1. [Core capabilities](#1-core-capabilities)
2. [Multi-agent flows](#2-multi-agent-flows)
3. [Business-domain skills](#3-business-domain-skills)
4. [Memory layers (5+1)](#4-memory-layers-51)
5. [LTM backend matrix](#5-ltm-backend-matrix)
6. [LLM provider matrix](#6-llm-provider-matrix)
7. [Promotion engine (3-path)](#7-promotion-engine-3-path)
8. [Evaluation tooling](#8-evaluation-tooling)
9. [Authentication, RBAC, audit, SSO](#9-authentication-rbac-audit-sso)
10. [Default UI](#10-default-ui)
11. [CLI command reference](#11-cli-command-reference)
12. [Unique advantages over competitors](#12-unique-advantages-over-competitors)
13. [Extending Praxia](#13-extending-praxia)
14. [ROI projection model](#14-roi-projection-model)
15. [Roadmap & extensibility](#15-roadmap--extensibility)
16. [FAQ](#16-faq)

---

## 1. Core capabilities

| Capability | Status | Description |
|---|---|---|
| Multi-agent orchestration | ✅ | Declarative `Flow` of `FlowStep`s with `${var}` template substitution |
| Workflow-specialized templates | ✅ | 3 production-ready flows + community-contributable recipes |
| Auto-extracting personal memory | ✅ | Layer 1; no explicit `save()` calls in business code |
| Sleep-time consolidation | ✅ | Layer 2; nightly batch promotes effective patterns |
| 3-path promotion (freq / outcome / self-eval) | ✅ | Statistical + LLM + frequency-based, run in parallel |
| Shared memory blocks | ✅ | Layer 3; living organizational knowledge with `read_only` policies |
| Markdown + git frozen layer | ✅ | Layer 4; PR-reviewed, GitHub Copilot / Cursor Rules compatible |
| Optional graph layer | ✅ | Layer 5; only for relationship-heavy domains |
| Skills registry promotion | ✅ | Layer 6; promotes skills, not just memory entries |
| 6 default business skills | ✅ | Investment / Sales / Design / Purchasing / Patent / Legal |
| 6 LTM backends | ✅ | json / mem0 / langmem / letta / zep / hindsight |
| Multi-LLM provider | ✅ | Claude / ChatGPT / Gemini / Qwen-API / Qwen-local + 100+ via LiteLLM |
| Built-in evaluation | ✅ | Hallucination check + retrieval metrics |
| Auth + RBAC + audit | ✅ | API key + JWT + 4 roles + append-only audit log |
| SSO (OIDC + SAML skeleton) | ✅ | Google / Microsoft / Okta / GitHub / Keycloak / custom |
| Resource access policies (ACL) | ✅ | Glob-pattern allow/deny rules per resource type, principal, action — built for IS depts |
| Admin user CRUD | ✅ | Create / read / update / delete / deactivate / rotate keys |
| Admin data exports | ✅ | CSV / JSON / JSONL exports of audit, users, usage, memory, policies |
| External connectors (Pull + Push) | ✅ | Box, SharePoint, Dropbox, Google Drive, kintone, Salesforce |
| Custom prompts (per-user + admin distribute) | ✅ | Personal / org / distributed scopes with role targeting |
| Personal & organizational dashboards | ✅ | Flow/skill counts, success rate, top users, promoted blocks |
| Default Streamlit UI | ✅ | 5-tab dashboard for non-technical users |
| MCP / Claude Skills compatibility | ✅ | Skills serialize to standard `SKILL.md` format |
| Outcome tracking | ✅ | `record_outcome()` for statistical promotion |
| Open Core license model | ✅ | Apache 2.0 core, commercial extras planned |

---

## 2. Multi-agent flows

### SalesAgentFlow

Three-agent pipeline:

| Step | Role | Output |
|---|---|---|
| `research` | Account researcher | Public IR / press / industry context |
| `hypothesis` | Pain hypothesizer | Top-3 customer pain hypotheses + product fit |
| `proposal` | Proposal writer | FAQ table + proposal outline |

```python
from praxia import Praxia
from praxia.flows import SalesAgentFlow

p = Praxia(user_id="alice", default_model="claude")
result = p.run(SalesAgentFlow, inputs={
    "customer_name": "Acme Manufacturing",
    "product": "Praxia Sales",
    "additional_context": "Mid-term plan calls for 30B JPY DX investment",
})
print(result.final_output)
```

```bash
praxia run sales --customer-name "Acme" --product "Praxia Sales"
```

### LogicCheckerFlow

| Step | Role | Output |
|---|---|---|
| `structure` | Structure extractor | Document tree + gap markers |
| `contradiction` | Contradiction detector | Inconsistencies + unfulfilled set-ups |
| `reader_perspective` | Target-reader simulator | Friction points + clarity score (10-pt) |

Use cases: long reports, manuals, novels, RFP responses.

### RAGOptimizationFlow

| Step | Role | Output |
|---|---|---|
| `query_rewriter` | Query expander | 3 alternative queries (keyword / NL / synonym) |
| `retrieval` | Pluggable retriever | Combined chunks |
| `evaluator` | Relevance scorer | Score 0..1 + missing-info gaps |
| `answerer` | Grounded answerer | Cited answer or "insufficient information" |
| `hallucination_check` | Verifier | Sentence-level grounded/ungrounded verdicts |

Plug in your retriever via the `retriever` input — any callable matching
`(query: str) -> list[dict]`.

---

## 3. Business-domain skills

Each skill ships with a battle-tested system prompt **plus guardrails**
(licensing reminders, jurisdictional caveats, hallucination guards).

### InvestmentSkill (`investment_analyst`)

Built-in framework: 5-step (Profile → Quant → Qual → Risk → Decision).

```bash
praxia skill run investment "Mid-term thesis on Sony Group stock"
```

```python
from praxia.skills import InvestmentSkill
print(InvestmentSkill().run("3-year investment thesis on Toyota"))
```

Guardrails: includes "final decision is yours" disclaimer, NISA tax notes,
explicit confidence-interval framing.

### SalesSkill (`sales_strategist`)

Framework: 4P (Profile / Pain / Power / Proposal).

```bash
praxia skill run sales "Acme Mfg, mid-cap electronics, our product: BizFlow"
```

Output: executive summary → customer profile → top-3 hypotheses → 5-row FAQ.

### DesignSkill (`design_reviewer`)

Framework: DRAGON (Data flow / Requirements traceability / Architectural fit /
Gaps / Operation / NFRs).

```bash
praxia skill run design "Review this design doc: $(cat spec.md)"
```

Output: review summary (Approve / Request Changes / Reject) + severity-tagged
issues + before/after code blocks.

### PurchasingSkill (`purchasing_analyst`)

Framework: QCD+S (Quality / Cost / Delivery + Sustainability) + geopolitical
risk + Subcontract Act compliance.

```bash
praxia skill run purchasing "Evaluate 5 suppliers for our PCB sourcing"
```

Output: 5-row supplier comparison + TCO breakdown + risk matrix + recommended
actions (immediate / mid / long).

### PatentSkill (`patent_analyst`)

Framework: 5-step prior-art search (element extraction → search formula →
hit analysis → novelty → inventive step) + claims drafting principles.

```bash
praxia skill run patent "Prior-art search: solid-state battery with X structure"
```

Guardrails: "final filing requires patent attorney review" reminder.

### LegalSkill (`legal_reviewer`)

Framework: RACE (Risk / Allocation / Compliance / Exit) + 🔴/🟡/🟢 severity
ladder.

```bash
praxia skill run legal "Review NDA: $(cat nda.txt)"
```

Guardrails: "lawyer required for final advice" reminder, references statute
revisions.

---

## 4. Memory layers (5+1)

| Layer | Class | Persistence | Lifecycle |
|---|---|---|---|
| 1 | `PersonalMemory` | Per-user JSONL or LTM backend | Auto-extracted from each interaction |
| 2 | `SleepTimeConsolidator` + `PromotionEngine` | Stateless (reads L1, writes L3 / review queue) | Nightly batch |
| 3 | `SharedMemory` | Per-org JSONL | Mutable, all agents read/write |
| 4 | `MarkdownStore` | git-tracked Markdown files | PR-reviewed, immutable until merged |
| 5 | Graph backend (optional) | Neo4j / Zep / Graphiti | Manual or batch ingestion |
| 6 | `SkillRegistry` | Per-user → org file tree | Promotes when usage thresholds met |

### Layer 1 — auto-extraction in action

```python
# These three lines accumulate memory implicitly. No explicit save().
result = p.run(SalesAgentFlow, inputs={...})
p.run(LogicCheckerFlow, inputs={...})
p.run(SalesAgentFlow, inputs={...})

# Each run stores an "episode" + extracted facts/preferences.
all_entries = p.personal_memory.all_entries()
print(len(all_entries))  # → 3+ entries
```

### Layer 2 — promotion in action

```python
# Run nightly (or on-demand)
report = p.consolidate(dry_run=False)
print(report)
# {
#   "candidates_evaluated": 12,
#   "auto_promoted": 3,           # high-confidence patterns moved to L3
#   "review_queued": 5,           # mid-confidence; need human review
#   "skipped": 4,
#   "verdicts": [...]
# }
```

### Layer 3 → Layer 4 — freezing

```bash
praxia freeze --block manufacturing_pain_hypotheses
# → .praxia/frozen/instructions/manufacturing_pain_hypotheses.md (git-tracked)
```

---

## 5. LTM backend matrix

| Backend | Auto-extract | Vector search | Entity linking | Relationship graph | Production-ready | Cost |
|---|---|---|---|---|---|---|
| **json** (default) | ❌ | BM25-like | ❌ | ❌ | Dev / SMB | Free |
| **mem0** | ✅ | ✅ hybrid | ✅ | ❌ (since 2026-04) | ✅ recommended | LLM tokens |
| **langmem** | ✅ | ✅ | ✅ | ❌ | ✅ (LangChain shop) | LLM tokens |
| **letta** | ✅ | ✅ | ❌ | ❌ | ✅ | Letta service |
| **zep** | ✅ | ✅ | ✅ | ✅ temporal KG | ✅ (Layer 5) | Zep service |
| **hindsight** | ✅ | ✅ | ❌ | ❌ | ✅ | Vectorize service / self-host |

```python
PersonalMemory(user_id="alice", backend="mem0")          # recommended
PersonalMemory(user_id="alice", backend="hindsight",
               api_url="https://hindsight.example.com")  # vectorize-io
PersonalMemory(user_id="alice", backend="zep")           # for graph use
```

---

## 6. LLM provider matrix

| Provider | Aliases | API key env var | Best for |
|---|---|---|---|
| Anthropic | `claude` / `claude-sonnet` / `claude-haiku` | `ANTHROPIC_API_KEY` | Reasoning, long-form |
| OpenAI | `chatgpt` / `gpt-4o` / `o1` | `OPENAI_API_KEY` | Tool use, breadth |
| Google | `gemini` / `gemini-flash` | `GEMINI_API_KEY` | Long-context, multimodal |
| Alibaba | `qwen` / `qwen-72b` | `DASHSCOPE_API_KEY` | Cost / Chinese-language |
| Ollama (local) | `qwen-local` | (none) | On-prem, no data leaves |
| 100+ others | `<provider>/<model>` | varies | LiteLLM-supported |

Praxia auto-detects which provider to use at startup based on which
environment variable is set; explicit selection via `--model` or `LLM(...)`
also works.

---

## 7. Promotion engine (3-path)

The single most-novel mechanism in Praxia. Each personal-memory cluster
gets evaluated by **all three paths in parallel**, with a weighted
combination determining auto-promote / review / skip.

```python
from praxia.memory.promoter import PromotionEngine

engine = PromotionEngine(
    llm=llm,
    weights=(0.4, 0.3, 0.3),  # frequency / outcome / self-eval
    auto_threshold=0.75,       # ≥ this → auto-promote to L3
    review_threshold=0.5,      # ≥ this → human review queue
)
```

| Path | Computation | Strength | Limitation |
|---|---|---|---|
| **Frequency** | (unique users with same pattern) / (total users) | Catches consensus patterns | Slow when team is small |
| **Outcome** | success rate of attached `record_outcome()` results | Highest signal-to-noise | Needs explicit outcome data |
| **Self-eval** | LLM scores 0..1 on generalizability + non-PII + actionable | Catches edge cases | LLM cost; subjective |

In practice: frequency drives early promotions; outcome takes over once
ground-truth data accumulates; self-eval acts as a safety net for novel
patterns that haven't yet been used by enough people.

---

## 8. Evaluation tooling

### Hallucination check (LLM-as-judge, sentence-level)

```python
from praxia.eval import check_hallucination

result = check_hallucination(
    answer="Praxia ships under MIT.",
    chunks=["Praxia is licensed under Apache 2.0."],
)
print(result.is_clean)            # False
print(result.hallucination_rate)  # 1.0 (every sentence ungrounded)
```

### Retrieval metrics

```python
from praxia.eval import recall_at_k, retrieval_precision

recall_at_k(retrieved=["doc3", "doc1"], gold=["doc1", "doc2"], k=2)  # 0.5
retrieval_precision(retrieved=["doc1", "doc9"], gold=["doc1"])       # 0.5
```

These are intentionally minimal helpers — for full RAG benchmarks, plug in
[RAGAS](https://github.com/explodinggradients/ragas) or
[Vectara HHEM](https://huggingface.co/vectara/hallucination_evaluation_model).

---

## 9. Authentication, RBAC, audit, SSO

### Local auth (default)

```python
from praxia.auth import AuthManager, Role
auth = AuthManager()
user, key = auth.create_user("alice", role=Role.MEMBER)

resolved = auth.authenticate(api_key=key)
auth.require(resolved, "promote_skills")  # raises PermissionError if denied
```

### Roles & permissions

| Role | Permissions |
|---|---|
| `admin` | All — including `manage_users`, `view_audit_log` |
| `operator` | `promote_skills`, `freeze_blocks`, `run_consolidator`, `edit_shared_memory` + member-level |
| `member` | `run_flows`, `run_skills`, `write_personal_memory` + viewer-level |
| `viewer` | `read_shared_memory`, `read_personal_memory` only |

### SSO providers (OIDC)

```python
from praxia.auth import google_provider, AuthManager

auth = AuthManager()
auth.attach_sso(google_provider(
    client_id="...",
    client_secret="...",
    redirect_uri="https://praxia.example.com/auth/callback",
))

# Web handler (FastAPI / Django / Next.js):
sso = auth.get_sso("google")
auth_url = sso.authorization_url(state=session_state)
# user redirects, comes back with code:
info = sso.exchange_code(code, state=session_state)
user = auth.upsert_sso_user(info, provider_name="google")
token = auth.issue_token(user.id)
```

Presets: `google_provider` / `microsoft_provider` / `okta_provider` /
`github_provider` / `keycloak_provider`. Custom OIDC is two lines:

```python
from praxia.auth import OIDCProvider, SSOConfig
sso = OIDCProvider(SSOConfig(
    provider_name="custom",
    issuer_url="https://idp.example.com",
    client_id="...", client_secret="...",
    redirect_uri="https://praxia.example.com/cb",
    role_mapping={"praxia-admins": "admin"},
))
```

SAML is supported via skeleton (`SAMLProvider`); production deployments
should swap in `python3-saml`.

### Audit log

Every privileged action records an `AuditEvent`:

```python
auth.audit.tail(limit=50)            # latest 50 events
auth.audit.search(actor_id="alice", action="memory.")  # filtered
```

Events include: `auth.api_key`, `auth.sso.login`, `authz.<permission>`,
`user.create`, `user.grant_role`, `memory.read`, `memory.write`, `skill.run`,
`flow.run`, `block.upsert`, `block.freeze`.

---

## 10. Default UI

5-tab Streamlit app launched via `praxia ui`:

| Tab | Functionality |
|---|---|
| **Run Flow** | Pick flow + LLM, fill inputs, see step-by-step output |
| **Business Skill** | Drop-down of 6 skills, send input, render Markdown response |
| **Memory** | Browse personal memory entries + shared blocks; search |
| **Consolidate** | Trigger sleep-time consolidation, view promotion verdicts |
| **About** | LLM/backend selection, GitHub links |

Sidebar lets users switch model and backend without code changes.

---

## 11. CLI command reference

```bash
praxia init                                  # bootstrap
praxia run <flow> [opts]                     # run a flow
praxia skill run <name> "<input>"            # run a skill
praxia skill promote --candidates            # list eligible skills
praxia skill promote --name X --user-id alice
praxia freeze --block <label>                # promote shared block → Markdown
praxia consolidate [--dry-run] [--threshold] # nightly batch
praxia user create alice --role member
praxia user list
praxia user grant alice admin
praxia user rotate-key alice
praxia user audit [--limit 50]
praxia list flows | skills | models | backends
praxia ui [--port 8501]
```

---

## 12. Unique advantages over competitors

| # | Advantage | Why no one else has it |
|---|---|---|
| 1 | **Personal-to-org memory cycling** | Frameworks treat memory as per-agent state, not as a community resource |
| 2 | **3-path promotion engine** | Most "memory" tools commit to one signal; Praxia runs all three |
| 3 | **Workflow-specialized templates** | CrewAI/AutoGen are intentionally generic |
| 4 | **Evidence-by-default (Eval bundled)** | Eval is usually a separate library |
| 5 | **6 LTM backends + 100+ LLMs** | Most projects pick one of each |
| 6 | **6 default business skills** | Most frameworks ship empty + docs |
| 7 | **Auth + RBAC + SSO + audit in core OSS** | Usually paywalled enterprise add-on |
| 8 | **Skills also promoted (not just memory)** | Novel — even Letta only promotes memory blocks |
| 9 | **MCP / Claude Skills format compatibility** | Future-proof against ecosystem standards |
| 10 | **Open Core ready (Apache 2.0)** | Permissive, commercial-friendly |

---

## 13. Extending Praxia

### Add a custom flow

```python
# my_flows.py
from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM


class IncidentResponseFlow(Flow):
    """Triage → root-cause hypothesis → mitigation suggestion."""

    name = "incident_response_flow"
    description = "On-call incident response: triage, root cause, mitigation"

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()
        self.steps = [
            FlowStep(
                name="triage",
                agent=Agent(name="triage", llm=llm,
                            system_prompt="You are an SRE triaging alerts..."),
                inputs={"alert": "${alert}"},
            ),
            FlowStep(
                name="hypothesis",
                agent=Agent(name="hypothesis", llm=llm,
                            system_prompt="You hypothesize root causes..."),
                inputs={"triage": "${triage}", "alert": "${alert}"},
            ),
            FlowStep(
                name="mitigation",
                agent=Agent(name="mitigation", llm=llm,
                            system_prompt="You suggest immediate mitigations..."),
                inputs={"triage": "${triage}", "hypothesis": "${hypothesis}"},
            ),
        ]
```

```python
from praxia import Praxia
from my_flows import IncidentResponseFlow

p = Praxia(user_id="oncall_alice")
result = p.run(IncidentResponseFlow, inputs={"alert": "..."})
```

### Add a custom business skill

```python
# my_skills.py
from praxia.skills.skill import Skill, SkillManifest


class HRRecruitingSkill(Skill):
    manifest = SkillManifest(
        name="hr_recruiting",
        description="Resume screening + interview question generation",
        domain="hr",
        tags=["recruiting", "screening"],
    )

    system_prompt = """You are an HR recruiting specialist.

    [Role]
    - Screen resumes against role requirements
    - Generate role-specific interview questions
    - Highlight strengths/concerns with evidence

    [Guardrails]
    - Never use protected characteristics (age, gender, race) in evaluation
    - Always cite specific resume passages for your judgments
    """
```

Register into the org skill catalog so it appears in `praxia list skills`:

```python
from praxia.skills.registry import SkillRegistry
from my_skills import HRRecruitingSkill
SkillRegistry().register_org(HRRecruitingSkill())
```

### Add a custom LTM backend

```python
# pinecone_backend.py — for example
from praxia.memory.backends.base import MemoryBackend, MemoryRecord

class PineconeBackend:
    def __init__(self, *, index_name, api_key, **kwargs):
        from pinecone import Pinecone
        self._client = Pinecone(api_key=api_key)
        self._index = self._client.Index(index_name)

    def add(self, *, user_id, text, kind, metadata): ...
    def search(self, *, user_id, query, limit): ...
    def all(self, *, user_id=None): ...
    def clear(self, *, user_id=None): ...
```

Then plug in:

```python
from praxia import PersonalMemory
pm = PersonalMemory("alice", backend=PineconeBackend(index_name="...", api_key="..."))
```

### Add custom MCP tools

Skills serialize to standard `SKILL.md`; just place under `~/.claude/skills/`
or any MCP-compatible registry.

```python
from praxia.skills import InvestmentSkill
md = InvestmentSkill().to_skill_md()
# Ship this Markdown to Claude Skills / Cursor Skills / MCP catalog
```

---

## 14. ROI projection model

A simple model to estimate ROI before / during / after a Praxia rollout.

### Variables

| Variable | Symbol | Typical range |
|---|---|---|
| Knowledge workers in scope | N | 30–500 |
| Average loaded cost / FTE / yr | C | ¥10–18M |
| Time on routine knowledge work | t | 30–60% |
| Time savings per task (alpha rollout) | s₁ | 30–50% |
| Time savings per task (after 12 mo, with org memory) | s₂ | 50–75% |
| Quality lift (errors avoided, $ value) | Q | ¥5–50M / yr |
| Praxia cost (license + infra + people) | P | ¥3–30M / yr |

### Annual ROI formula

```
Year 1 ROI = (N × C × t × s₁) + Q − P
Year 2+ ROI = (N × C × t × s₂) + Q × growth − P
```

### Worked example (mid-cap, 100 knowledge workers)

| Variable | Value |
|---|---|
| N | 100 |
| C | ¥14M |
| t | 40% |
| s₁ | 35% (year 1) → s₂ 60% (year 2) |
| Q | ¥10M (year 1) → ¥30M (year 2) |
| P | ¥12M / yr |

**Year 1**: 100 × 14M × 0.4 × 0.35 + 10M − 12M = **¥194M net benefit**
**Year 2**: 100 × 14M × 0.4 × 0.60 + 30M − 12M = **¥354M net benefit**

3-year cumulative net ≈ **¥800M**. Even after halving each parameter,
ROI remains > 10×.

---

## 15. Roadmap & extensibility

| Phase | Scope | Status | Public OSS? |
|---|---|---|---|
| 1 | Personal memory + 3 flows + 6 skills | ✅ Done | ✅ |
| 2 | Sleep-time consolidator + statistical promotion | ✅ Done | ✅ |
| 3 | Shared blocks + Markdown freeze workflow | ✅ Done | ✅ |
| 4 | Skill registry promotion (personal → org) | ✅ Done | ✅ |
| 5 | Auth + RBAC + audit + SSO (OIDC + SAML skeleton) | ✅ Done | ✅ |
| 6 | Multi-tenant SaaS, advanced GUI | 🚧 Planned | 💼 Commercial |
| 7 | Vertical SaaS editions (Sales / Legal / Patent / R&D) | 🚧 Planned | 💼 Commercial |
| 8 | Mobile apps, voice integration | 📋 Future | TBD |
| 9 | Federated multi-org learning (privacy-preserving) | 📋 Research | TBD |

### Community-driven extensibility

| Extension type | How to contribute | Where it lives |
|---|---|---|
| New flow | PR to `praxia/flows/` | Core OSS |
| New business skill | PR to `praxia/skills/business/` | Core OSS |
| New LTM backend | PR to `praxia/memory/backends/` | Core OSS |
| Industry recipe | PR to `docs/recipes/` | Core OSS |
| Custom integration | Standalone package + entry point | Third-party |

See [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## 16. FAQ

**Q: Does Praxia send my data to a third-party?**
No. By default, the `json` backend stores everything on local disk. LLM calls
go to whichever provider you configured (Claude / Qwen-local for fully
in-house, Mem0 for entity-linking, etc.). You choose the trust boundary.

**Q: How is this different from "just using Mem0"?**
Mem0 is a memory layer. Praxia is the **orchestrator** *plus* memory layer
*plus* skill registry *plus* flows *plus* eval *plus* auth. Mem0 is one of
six interchangeable backends inside Praxia.

**Q: Is "auto-promotion" actually safe?**
Three guardrails: (a) the auto-threshold defaults to 0.75 (high), (b) review
queue catches mid-confidence items for human approval, (c) the audit log
records every promotion, making rollback trivial.

**Q: Can I run Praxia fully offline / on-prem?**
Yes — pick `qwen-local` (Ollama) for the LLM and `json` (or self-hosted Mem0
/ HindSight) for memory. No cloud calls.

**Q: What's the difference between the 3 flows and the 6 skills?**
A flow chains multiple agents through a workflow (sales prep, doc review,
RAG self-correction). A skill is a single agent specialized for a domain.
You can embed skills inside flows.

**Q: How does Praxia compare to LangGraph?**
LangGraph excels at general agent orchestration but doesn't ship workflow
templates, business skills, memory cycling, or auth. Praxia is opinionated
and batteries-included for the "specialized multi-agent + organizational
memory" niche.

**Q: Can I use this commercially?**
Yes. Apache 2.0. Even the auth/SSO module is in the OSS — many competing
frameworks paywall those features.

**Q: Is the 6-business-skill set fixed?**
No. Add your own with ~20 lines (see [Extending Praxia](#13-extending-praxia)).
PRs that contribute new skills are very welcome.

**Q: What about MCP / Claude Skills compatibility?**
Skills serialize to the `SKILL.md` frontmatter format. You can take any
Praxia skill and drop it into Claude Skills / Cursor Skills / any MCP
registry without code changes.

**Q: How big can my organization grow before I hit limits?**
The JSON backend handles ~10k users comfortably. Beyond that, switch to
Mem0 + Qdrant / Pinecone or HindSight. The promotion engine scales with
LLM tokens; budget 10–50 LLM calls per consolidation run per cluster.

**Q: Is my org memory locked into Praxia?**
No. Layer 4 is plain Markdown in your git repo. Layer 3 (shared blocks)
exports to JSONL. Layer 1 personal memory is standard JSONL or your chosen
backend's native format. You can leave at any time.
