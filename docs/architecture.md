# Praxia Architecture

## Overview — Six Layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      Application / UI (Streamlit / CLI / SDK)            │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
              ┌──────────────────▼───────────────────┐
              │  AutonomousAgent (tool-use loop)     │ (praxia.agent)
              │  LLM-driven; LLM picks tools  │
              └──┬─────────────────────────────────┬─┘
                 │  uses                           │
                 ▼                                 ▼
                    ┌────────────────────────┐
                    │      Orchestrator      │  (praxia.core.Praxia)
                    │   memory + flow + skill│
                    └─┬──────────┬──────────┬┘
                      │          │          │
                ┌─────▼───┐ ┌────▼────┐ ┌──▼───────┐
                │ Flows   │ │ Skills  │ │ Memory   │
                │ (Multi- │ │ (Domain │ │ (5-layer │
                │ Agent)  │ │ Bundles)│ │ Stack)   │
                └────┬────┘ └────┬────┘ └────┬─────┘
                     │           │           │
                ┌────▼───────────▼───────────▼────┐
                │       Auth / RBAC / Audit       │  (praxia.auth)
                │  ACL gates connector / memory   │
                │  every tool call audited        │
                └────┬────────────────────────────┘
                     │
                ┌────▼─────────────────────────────┐
                │            LLM Layer             │  (litellm — multi-provider)
                │  Anthropic / OpenAI / Google /   │
                │  DeepSeek / Mistral / xAI /      │
                │  Cohere / Perplexity / Qwen +    │
                │  Llama (Groq / Ollama) / Phi /   │
                │  Gemma + 100+ via LiteLLM        │
                └──────────────────────────────────┘
```

## Memory: 5-Layer Stack

### Layer 1: Personal Memory (`PersonalMemory`)
- Auto-extracts tacit knowledge from conversations as a side effect of normal use.
- Pluggable backend: `json` (default) / `mem0` / `langmem` / `letta` / `zep` / `hindsight`.
- **Multi-backend composition**: wrap several backends in `CompositeBackend` for parallel fan-out + Reciprocal Rank Fusion, or `RoutedBackend` for query-aware dispatch (temporal → Zep, audit → JSON, entity → Mem0, similarity → HindSight). See [FEATURES.md § 5.1](FEATURES.md#51-multi-ltm-fusion--dynamic-routing-accuracy-boost).
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

## Autonomous Agent (`praxia.agent.AutonomousAgent`)

A LLM-driven tool-use loop sitting **on top** of the orchestrator,
flows, skills, and memory layers. Where a `Flow` is a script you author
with `${var}` substitution, the autonomous agent is the LLM **deciding
the script** turn-by-turn: search personal memory → run a skill → pull
a connector → emit a final answer.

```python
from praxia.agent import AutonomousAgent
from praxia.core.llm import LLM

agent = AutonomousAgent(user_id="alice", org_id="acme", llm=LLM("claude"))
result = agent.run("Tell me what we know about Acme and draft a proposal.")
print(result.final_text)
for tc in result.tool_calls:
    print(tc.name, "ok" if tc.ok else tc.error)
```

11 built-in tools (memory search × 3 layers, skill list/run × 3 scopes,
connector list/pull, frozen-layer search, fact recording, final-answer
sentinel). Each tool call is recorded via `auth.audit.record(...)`;
`pull_from_connector` is gated by `auth.policies.require(...)` so ACL
denials short-circuit cleanly. `record_fact` honors `read_only` memory
mode by no-op'ing.

The agent is also exposed as a single MCP meta-tool `autonomous_agent`
so remote clients (Claude Desktop / Cursor) can delegate an entire
investigation rather than orchestrating individual tools.

See [FEATURES § 38](FEATURES.md#38-autonomous-agent-llm-driven-tool-use-loop)
for the full tool catalog and governance details.

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

Thin wrapper over LiteLLM. 27 friendly aliases cover the major providers;
every other LiteLLM-supported model works via the raw `provider/model`
string. `LLM.complete()` returns `LLMResponse` with `text`, `usage`,
**and `tool_calls`** — the latter feeds the AutonomousAgent loop.

```python
# Frontier proprietary
LLM("claude")              # → anthropic/claude-opus-4-7
LLM("chatgpt")             # → openai/gpt-4o
LLM("gemini")              # → gemini/gemini-2.0-pro

# Strong cloud APIs
LLM("deepseek")            # → deepseek/deepseek-chat (v3)
LLM("deepseek-reasoner")   # → deepseek/deepseek-reasoner (R1, chain-of-thought)
LLM("mistral")             # → mistral/mistral-large-latest
LLM("codestral")           # → mistral/codestral-latest
LLM("grok")                # → xai/grok-2-latest
LLM("qwen")                # → dashscope/qwen-max
LLM("command-r")           # → cohere/command-r-plus
LLM("perplexity")          # → perplexity/llama-3.1-sonar-large-128k-online (web-search)

# OSS weights via fast inference / local
LLM("llama")               # → groq/llama-3.3-70b-versatile (hundreds tok/s)
LLM("llama-local")         # → ollama/llama3.3:70b
LLM("gemma")               # → ollama/gemma2:9b
LLM("phi")                 # → ollama/phi3.5:3.8b (edge / small)
LLM("qwen-local")          # → ollama/qwen2.5:14b

# Anything else LiteLLM supports
LLM("openrouter/anthropic/claude-3.5-sonnet")
```

`LLM.auto_detect()` picks a default based on which API key is set
(priority: Anthropic → OpenAI → Gemini → DeepSeek → Mistral → xAI →
Qwen → Cohere → Perplexity → Groq/Together → local Ollama). Set
`PRAXIA_LOCAL_MODEL=phi` to make the local fallback Phi instead of Qwen.

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
| 7 | AutonomousAgent (LLM-driven tool-use loop over the full stack) | ✅ Done |

## Design Decisions and Rationale

| Decision | Rationale |
|----------|-----------|
| Recommend Mem0 OSS as default LTM | Mature auto-extraction; entity-linking-based (after April 2026 graph removal) |
| Multi-LTM via `CompositeBackend` / `RoutedBackend` | Each backend has different strengths — fusion (RRF) lifts recall without picking a winner; routing keeps single-backend latency for queries that fit one well |
| Demote graph layer to optional | All-domain graphs have poor ROI (LinkedIn CMA / Mem0 itself signal this) |
| Three parallel promotion paths | Avoid single-mechanism dependence (frequency + outcome + self-eval) |
| Markdown + git as frozen layer | Reuse PR review / blame / history workflows already in place |
| LiteLLM | Don't reinvent the abstraction over 100+ providers |
| API key + JWT auth | Lightweight, swap-out friendly with PyJWT in production |
