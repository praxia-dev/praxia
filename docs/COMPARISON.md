# Comparison with adjacent projects

> **As of 2026-05.** Capabilities of all listed projects evolve quickly.
> All product names are trademarks of their respective owners — see
> [NOTICE.md § Trademark notice](../NOTICE.md#trademark-notice).
>
> This document is a **factual technical reference**, not marketing
> material. Every entry below should be verifiable against each project's
> public documentation; please open an issue if you spot a mistake.

---

## How to read this matrix

Praxia, CrewAI, AutoGen, LangGraph, and Glean all live in the broader
"AI agent / knowledge framework" space, but their goals differ. The matrix
captures the **specific dimensions** where these projects make different
trade-offs — it is not a "Praxia is best" leaderboard.

If you only need a generic agent graph builder, **LangGraph** is excellent.
If you need a hosted enterprise knowledge platform without operating it,
**Glean** is excellent. Praxia exists because no single tool covered all
the dimensions below for organizations that want OSS + workflow templates +
auto memory cycling + integrated auth.

---

## Capability matrix

Legend: ✅ supported · ~ partial / via plug-in · — not currently supported

| Capability | CrewAI | AutoGen | LangGraph | Glean | Praxia |
|---|---|---|---|---|---|
| Multi-agent orchestration | ✅ | ✅ | ✅ | — | ✅ |
| Workflow-specialized templates (out of box) | — | — | — | — | ✅ |
| Auto-extracting personal memory | — | — | ~ | ✅ | ✅ |
| Personal-to-org pattern promotion | — | — | — | ~ | ✅ |
| Sleep-time / batch memory consolidation | — | — | — | — | ✅ |
| Skills + prompt distribution to roles | — | — | — | — | ✅ |
| Hallucination eval bundled in core | — | — | — | — | ✅ |
| Built-in auth + RBAC + audit log | — | — | — | ✅ | ✅ |
| SSO (OIDC) in core | — | — | — | ✅ | ✅ |
| Resource access policies (ACL) in core | — | — | — | ✅ | ✅ |
| Admin data exports (CSV/JSON) | — | — | — | ✅ | ✅ |
| Personal + org usage dashboards | — | — | — | ✅ | ✅ |
| Storage / SaaS connectors (Pull + Push) | — | — | ~ | ~ | ✅ ×20 |
| Multi-LTM fusion + dynamic routing | — | — | — | — | ✅ |
| MCP / Claude Skills format | ~ | ~ | ~ | — | ✅ |
| Autonomous agent (Claude-Code-style tool-use loop) | ~ | ~ | ~ | — | ✅ |
| First-class LLM aliases (with auto-detect) | ~ | ~ | ~ | — | ✅ ×27 |
| License model | MIT (OSS) | MIT (OSS) | MIT (OSS) | Commercial | Apache 2.0 (OSS) |

> The license / pricing entries are factual at time of writing. For latest
> commercial terms, consult the respective vendor.

---

## Why each project exists

| Project | Primary intent (per their public docs) |
|---------|---------------------------------------|
| **CrewAI** | Generic role-based agent orchestration with declarative crews/tasks |
| **AutoGen** | Research-grade conversational multi-agent system from Microsoft Research |
| **LangGraph** | Stateful, graph-based agent workflow library for the LangChain ecosystem |
| **Glean** | Hosted enterprise knowledge platform with built-in connectors and search |
| **Praxia** | Workflow-specialized multi-agent orchestrator with cyclic personal-to-org memory |

There is significant overlap, but the **distinguishing axis** for Praxia
is the personal-to-organizational memory loop combined with bundled
business-domain skills. Frameworks like LangGraph could be used to build
something similar, but it would require integrating ~10 components that
Praxia ships out of the box.

---

## When to pick which

- **Pick CrewAI** when you need a lightweight role-based crew abstraction
  and don't need bundled domain skills or memory cycling.
- **Pick AutoGen** when you're doing agent research and want maximum
  flexibility over conversation graphs.
- **Pick LangGraph** when you're already invested in LangChain and need
  fine-grained state machines.
- **Pick Glean** when you want a hosted product with no operational burden
  and your data pattern fits their connectors.
- **Pick Praxia** when you need OSS + workflow templates + memory cycling
  + integrated auth/ACL + Pull/Push connectors in a single library you
  control end-to-end.

These choices are not mutually exclusive — Praxia uses Mem0 / LangMem /
Letta as memory backends and could be embedded inside a LangGraph node.

---

## Verifying these claims yourself

We strongly encourage you to verify each row against the source project's
documentation:

- CrewAI: <https://docs.crewai.com/>
- AutoGen: <https://microsoft.github.io/autogen/>
- LangGraph: <https://langchain-ai.github.io/langgraph/>
- Glean: <https://www.glean.com/>
- Praxia: this repository

If any claim is incorrect, please open an issue with `comparison` label
and we will update within 7 days.
