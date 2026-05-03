# Praxia Architecture

## Overview — Six Layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      Application / UI (Streamlit / CLI / SDK)            │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │      Orchestrator        │  (praxia.core.Praxia)
                    │   memory + flow + skill  │
                    └─┬──────────┬──────────┬──┘
                      │          │          │
                ┌─────▼───┐ ┌────▼────┐ ┌──▼───────┐
                │ Flows   │ │ Skills  │ │ Memory   │
                │ (Multi- │ │ (Domain │ │ (5-layer │
                │ Agent)  │ │ Bundles)│ │ Stack)   │
                └────┬────┘ └────┬────┘ └────┬─────┘
                     │           │           │
                ┌────▼───────────▼───────────▼────┐
                │       Auth / RBAC / Audit       │  (praxia.auth)
                └────┬────────────────────────────┘
                     │
                ┌────▼─────────────────────────────┐
                │            LLM Layer             │  (litellm — multi-provider)
                │  Claude / ChatGPT / Gemini /     │
                │  Qwen-API / Qwen-local (Ollama)  │
                └──────────────────────────────────┘
```

## Memory: 5-Layer Stack

### Layer 1: Personal Memory (`PersonalMemory`)
- Auto-extracts tacit knowledge from conversations as a side effect of normal use.
- Pluggable backend: `json` (default) / `mem0` / `langmem` / `letta` / `zep` / `hindsight`.
- Namespaced by `user_id`.

### Layer 2: Distillation & Promotion Engine (`SleepTimeConsolidator + PromotionEngine`)
Three independent verdicts run in parallel:
1. **Frequency** — does the pattern recur across N+ users / sessions?
2. **Outcome** — is it correlated with positive outcomes (won deals, passing tests, accepted PRs)?
3. **Self-eval** — LLM scores the pattern's "org-knowledge candidacy" on a 0..1 scale.

The final score is a weighted blend; auto-promote above one threshold, route to a review queue above a lower one.

### Layer 3: Shared Memory (`SharedMemory`)
- Letta-style **shared blocks**.
- All agents read/write; `read_only` mode for policy content.

### Layer 4: Frozen Layer (`MarkdownStore`)
- Markdown + git + PR review.
- Compatible with GitHub Copilot custom instructions / Cursor Rules formats.

### Layer 5 (optional): Graph Layer
- For relationship-heavy domains (decision histories, customer 360, incident causal chains).
- Use Zep / Graphiti; otherwise vector + entity linking is sufficient.

### Parallel Layer 6: Skills Registry
- Personal skills get promoted to the org registry through the same mechanisms as memory.
- Compatible with Claude Skills / MCP / Cursor Skills.

## Flow Execution Model

```python
flow = SalesAgentFlow()
result = flow.run({"customer_name": "...", "product": "..."})
# result.final_output     ← final output
# result.step_outputs     ← intermediate outputs from each agent
# result.total_usage      ← total token usage
```

Each `FlowStep` can reference earlier outputs via `${step_name}` template substitution.

## LLM Provider Abstraction

Thin wrapper over LiteLLM. String aliases for one-line provider switching:

```python
LLM("claude")        # → anthropic/claude-opus-4-7
LLM("chatgpt")       # → openai/gpt-4o
LLM("gemini")        # → gemini/gemini-2.0-pro
LLM("qwen")          # → dashscope/qwen-max
LLM("qwen-local")    # → ollama/qwen2.5:14b
LLM("openai/gpt-4o") # any LiteLLM-compatible model string
```

## Auth, RBAC, and Audit

All privileged actions flow through `praxia.auth`:

```python
from praxia.auth import AuthManager, Role

auth = AuthManager(storage_dir=".praxia/auth")
user, api_key = auth.create_user("alice", role=Role.MEMBER)

# Authentication
user = auth.authenticate(api_key=api_key)

# Authorization (raises PermissionError on denial)
auth.require(user, "promote_skills", resource="skill:investment_analyst")

# Audit log (every privileged action recorded)
events = auth.audit.tail(limit=50)
```

Default roles: `admin` / `operator` / `member` / `viewer`.

## Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Personal memory + 3 specialized flows + 6 business skills | ✅ Done |
| 2 | Sleep-time consolidator + statistical promotion | ✅ Done |
| 3 | Shared blocks + Markdown freeze workflow + CLI | ✅ Done |
| 4 | Skill registry promotion (personal → org) | ✅ Done |
| 5 | Auth, RBAC, audit log | ✅ Done |
| 6 | Enterprise GUI / multi-tenant SaaS | 💼 Commercial |

## Design Decisions and Rationale

| Decision | Rationale |
|----------|-----------|
| Recommend Mem0 OSS as default LTM | Mature auto-extraction; entity-linking-based (after April 2026 graph removal) |
| Demote graph layer to optional | All-domain graphs have poor ROI (LinkedIn CMA / Mem0 itself signal this) |
| Three parallel promotion paths | Avoid single-mechanism dependence (frequency + outcome + self-eval) |
| Markdown + git as frozen layer | Reuse PR review / blame / history workflows already in place |
| LiteLLM | Don't reinvent the abstraction over 100+ providers |
| API key + JWT auth | Lightweight, swap-out friendly with PyJWT in production |
