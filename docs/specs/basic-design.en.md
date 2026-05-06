# Praxia — Basic Design Specification

> Status: **v1.0** · Last updated: 2026-05 · 🇯🇵 [日本語版](basic-design.ja.md)

---

## 1. Purpose

Praxia is a multi-agent orchestrator with **cyclic personal-to-organizational memory**. It is the runtime that turns individual users' tacit working knowledge into reusable organizational assets without explicit "save" steps.

The system is designed to be:

- **OSS-first** (Apache 2.0) — adoption shouldn't depend on a sales call.
- **Vendor-agnostic** at every plug point: LLMs (LiteLLM), LTMs (6 backends + ensembles), connectors (6 default + entry-points), file formats, output formats.
- **Enterprise-ready** at the kernel: RBAC, SSO, ACL, audit log, per-user OAuth.
- **Composable** — every extension point uses the same `Registry` primitive.

## 2. Scope

| In scope | Out of scope (v1) |
|---|---|
| Multi-agent flow orchestration | Multi-tenant SaaS hosting |
| Auto-extracting personal memory | Mobile native apps |
| Personal → org memory promotion | Hosted GUI / dashboard service |
| 6 business-domain skills + extension points | Real-time streaming generation |
| 6 storage / SaaS connectors + extension points | Federated multi-org learning |
| Auth / RBAC / SSO / ACL / audit log | Causal inference for outcomes |
| File parsers (PDF / Office / CSV / HTML / TXT / MD) | |
| Output exporters (HTML / PPTX / DOCX / MD / JSON) | |
| Audio I/O (STT + TTS) | |
| Optional FastAPI HTTP server (`praxia serve`) | |
| KMS-backed OAuth token encryption (5 adapters) | |
| Production OAuth callback handler (multi-worker safe) | |
| A/B experiments framework | |
| LLM output-quality evaluation framework | |

## 3. System context

```
                    ┌──────────────────────────────────────┐
                    │       External users / clients       │
                    │   (browser / mobile / CLI / SDK)     │
                    └──────────────┬───────────────────────┘
                                   │
                  ┌────────────────┴───────────────────┐
                  │                                    │
        ┌─────────▼──────────┐               ┌─────────▼──────────┐
        │  Streamlit UI      │               │  FastAPI server    │
        │  (mode A)          │               │  (mode B optional) │
        └─────────┬──────────┘               └─────────┬──────────┘
                  │            Praxia SDK              │
                  └────────────────┬───────────────────┘
                                   │
       ┌───────────────────────────▼────────────────────────────┐
       │                       Orchestrator                     │
       │  ┌────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐  │
       │  │ Flows  │  │ Skills  │  │  Auth   │  │ Connectors │  │
       │  │ engine │  │ registry│  │ + ACL   │  │  registry  │  │
       │  └────┬───┘  └────┬────┘  └────┬────┘  └─────┬──────┘  │
       │       │           │            │             │         │
       │       └───────┬───┴───┬────────┴────┬────────┘         │
       │               │       │             │                  │
       │      ┌────────▼───┐ ┌─▼──────────┐ ┌▼────────────────┐ │
       │      │ Memory     │ │ I/O        │ │ LLM (LiteLLM)   │ │
       │      │ (5 layers  │ │ parsers /  │ │ Claude / GPT /  │ │
       │      │ + policy)  │ │ exporters/ │ │ Gemini / Qwen / │ │
       │      └────────────┘ │ audio      │ │ Gemma / Ollama  │ │
       │                     └────────────┘ └─────────────────┘ │
       └────────────────────────────┬───────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   ┌────▼──────┐  ┌────────────┐  ┌─▼─────────┐  ┌──────────────▼──┐
   │ LTM       │  │ Box / SP / │  │ OIDC IdP  │  │ Local FS for    │
   │ (Mem0/    │  │ Drive /    │  │ (Google / │  │ JSON memory,    │
   │ Zep/      │  │ kintone /  │  │  MS Entra │  │ frozen .md,     │
   │ HindSight)│  │ Salesforce │  │  / Okta)  │  │ audit JSONL     │
   └───────────┘  └────────────┘  └───────────┘  └─────────────────┘
```

## 4. Layered architecture

| Layer | Module | Responsibility |
|---|---|---|
| 0 | `praxia.config` | Unified config resolution: env > .env > `.praxia/config.toml` |
| 1 | `praxia.core.llm` | Multi-provider LLM client (LiteLLM-backed) |
| 2 | `praxia.core.agent` / `flows` / `skills` | Single agent + multi-agent flow + skill registry |
| 3 | `praxia.memory` | 5-layer memory stack + policy + multi-LTM composition |
| 4 | `praxia.auth` | AuthN (API key + JWT + SSO) / AuthZ (RBAC + ACL) / audit |
| 5 | `praxia.connectors` | Storage / SaaS connectors + per-user OAuth |
| 6 | `praxia.io` | File parsers + audio I/O + output exporters |
| 7 | `praxia.cli` / `praxia.ui` / `praxia.server` | Frontends — CLI, Streamlit, FastAPI |
| 8 | `praxia.experiments` | A/B experiments — variant assignment + outcome rollup |
| 9 | `tests/llm_eval` | LLM-output quality evaluation framework (CI gate) |

Layers are uni-directional (lower numbered layers do not import higher ones). Plugin discovery uses `praxia.extensions.Registry` at every extensible boundary.

## 5. Memory architecture (Layer 3 expanded)

```
  ┌── Layer 1: Personal memory ──┐    Backend choice:
  │  PersonalMemory(user_id, ...)│    - json (default)
  │  Mode: accumulate / read_only│    - mem0 / langmem / letta /
  │                              │      zep / hindsight
  │                              │    - CompositeBackend (RRF fusion)
  │                              │    - RoutedBackend (rule / LLM router)
  └──────────────┬───────────────┘
                 │  SleepTimeConsolidator
                 │  3-path PromotionEngine: frequency + outcome + LLM-self-eval
                 ▼
  ┌── Layer 3: Shared blocks (org-wide) ──┐
  │  SharedMemory(org_id, ...)            │
  │  Letta-style read/write blocks        │
  └──────────────┬────────────────────────┘
                 │  PR review (curation)
                 ▼
  ┌── Layer 4: Frozen Markdown + git ─────┐
  │  MarkdownStore(...)                   │
  │  Compatible with Claude Skills /      │
  │  Cursor Rules / Copilot instructions  │
  └───────────────────────────────────────┘

  Layer 5 (optional): Graph layer — Zep / Graphiti for temporal KG
```

The dual control plane (admin policy + user preference) governs Layer 1's backend choice and accumulation mode. See `praxia.memory.policy`.

## 6. Configuration model

Resolution order (first match wins):

1. Process environment variable (e.g., `ANTHROPIC_API_KEY`)
2. `.env` file in the working directory
3. `.praxia/config.toml` (managed via `praxia config set / get / show`)

Categories:
- LLM provider keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`, `OLLAMA_API_BASE`)
- Memory backend (`PRAXIA_MEMORY_BACKEND`, `PRAXIA_MEMORY_MODE`)
- Auth (`PRAXIA_JWT_SECRET`, `PRAXIA_TOKEN_ENC_KEY`)
- SSO (`PRAXIA_SSO_PROVIDER`, `PRAXIA_SSO_CLIENT_ID`, ...)
- Per-user OAuth (`PRAXIA_OAUTH_<PROVIDER>_CLIENT_ID/SECRET`)
- Connector shared credentials (`PRAXIA_CONN_<NAME>_<KEY>`)

See `.env.example` for the full canonical reference.

## 7. Non-functional requirements

| NFR | Target | How it's met |
|---|---|---|
| Performance | First flow run < 5 s end-to-end (excluding LLM latency) | All registries cached; parsers stream; exporters in-memory |
| Scalability | Single process: 100 active users | Each user's memory is namespaced; backends are I/O-bound, not CPU-bound |
| Availability | 99.5% (single-host self-managed) | Stateless except for `.praxia/`; HA via shared FS / object storage + multiple replicas |
| Security | OWASP Top 10 conformance | API keys hashed, OAuth tokens encrypted, JWT signed, audit logged |
| Privacy | PII filter on personal → org promotion | `PromotionEngine._self_eval` excludes PII candidates |
| Auditability | Every privileged action logged | Append-only JSONL under `.praxia/audit/`, exportable to CSV/JSON for SIEM |
| Compatibility | Claude / OpenAI / Gemini / Qwen / Gemma / 100+ via LiteLLM | Provider-agnostic at the LLM layer |
| Portability | Linux / macOS / Windows | Pure Python; only optional deps need C extensions |
| Extensibility | New connector / backend / skill in < 50 LoC | `Registry` + entry-points |

## 8. Deployment topology

| Mode | Components | Recommended for |
|---|---|---|
| **A. Full-stack** | Streamlit UI + Praxia core | Internal teams, fastest path |
| **B-1. Embedded SDK** | User's Python service + Praxia library | Existing Python backend |
| **B-2. HTTP service** | `praxia serve` (FastAPI) + user's frontend | Non-Python frontend, mobile |

See [`docs/deployment-modes.md`](../deployment-modes.md) for the full setup.

## 9. Lifecycle / data flow

A typical "run a flow" lifecycle:

1. Client → Auth (API key / JWT validate)
2. Auth → ACL (resource:action permitted?)
3. Praxia → Flow (resolve `flows.get(name)`)
4. Flow → Skills / Agent (per-step, system prompt + LLM call via LiteLLM)
5. Skills → Memory (search relevant context; record episode if mode=accumulate)
6. Memory → backend(s) (single, composite, or routed)
7. Result → Exporter (if user requested specific format)
8. Audit log entry written

## 10. Out-of-band lifecycle

| Process | Frequency | Purpose |
|---|---|---|
| `praxia consolidate` | Nightly | Run sleep-time consolidator → personal-to-org promotion |
| `praxia freeze` | On stable patterns | Promote shared block to git-tracked Markdown |
| `praxia admin export-*` | On demand / scheduled | Compliance / SIEM export of audit log + user data |
| OAuth token refresh | On expiry | Silent — handled by `OAuthTokenStore` |

## 11. Trust boundaries

```
   [Browser/Client] -->|HTTPS|--> [Auth: AuthManager]
                                      |
                            (API key / JWT / SSO)
                                      |
   [Untrusted input]                  v
   [User-uploaded files] -->|parser|-> [Sanitized text]
                                      |
   [LLM provider]  <--|HTTPS|<-- [LLM: LiteLLM client]
                                      |
   [Memory backend(s)]    <-- [Memory + Policy guard] <-- [ACL check]
   [Connector targets]    <-- [Per-user OAuth token]  <-- [ACL check]
   [Audit log .jsonl]     <-- [AuditLog (append-only)]
```

User-uploaded files cross from "untrusted" to "trusted text" via the parsers in `praxia.io.parsers`. LLM responses are not blindly trusted — `praxia.eval.hallucination` provides verification primitives.

## 12. Standards / interop

- **Claude Skills format** — `Skill.to_skill_md()` outputs a SKILL.md compatible with Anthropic's spec.
- **Model Context Protocol (MCP)** — skills implement compatible tool descriptors.
- **OpenAI tool-call format** — flows / agents emit tool calls in the function-calling shape used by GPT-4o.
- **OIDC / OAuth 2.0** — SSO + per-user delegation use standard flows with PKCE.
- **OWASP ASVS Level 1** — auth / authZ design follows ASVS controls.

## 13. Glossary

| Term | Meaning |
|---|---|
| Flow | Declarative DAG of agent steps |
| Skill | A capability bundle: prompt + tools + reference docs (Claude Skills compatible) |
| LTM | Long-term memory backend |
| RRF | Reciprocal Rank Fusion (used for multi-backend ensemble) |
| Promotion | Personal → organizational memory transition |
| Consolidator | Sleep-time job that runs PromotionEngine across users |
| Connector | Plugin that pulls/pushes from external storage/SaaS |
| Mode (memory) | accumulate (writes pass through) / read_only (writes dropped) |
