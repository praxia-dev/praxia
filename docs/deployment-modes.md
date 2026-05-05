# Deployment modes

> 🇯🇵 日本語版: [deployment-modes.ja.md](deployment-modes.ja.md)

Praxia ships in two halves you can mix and match:

* **Backend** — orchestrator, memory layers, skills, flows, LLM client, auth, connectors, exporters. Pure Python; embeds via SDK or speaks HTTP via the optional FastAPI app.
* **Frontend** — the Streamlit UI (`praxia ui`). Optional; you can replace it with your own.

The two combinations users typically deploy:

| Mode | What you run | When to choose it |
|---|---|---|
| **A. Full-stack** (Praxia frontend + backend) | `praxia ui` + storage on the same host | Internal tool, single team, fastest path to a working portal |
| **B. Backend-only** (your frontend, Praxia core) | Embed via Python SDK *or* run `praxia serve` and call HTTP | You already have a portal / mobile app / Slack bot and want Praxia as a brain behind it |

Both modes share the same configuration, auth, memory, and skills. The only difference is **who owns the UI**.

---

## Mode A. Full-stack (Streamlit UI included)

The simplest way to get a working portal. Everything in one process.

### A-1. Install
```bash
pip install "praxia[ui,connectors,office]"
```

### A-2. Configure once
```bash
cp .env.example .env       # fill in at least one LLM key
praxia config init
```

### A-3. Initialize storage + admin user
```bash
praxia init --user-id admin --backend mem0
# bootstrap admin API key is printed once — save it
```

### A-4. Launch
```bash
praxia ui --port 8501
# open http://localhost:8501
```

You now have all 11 tabs (Run Flow / Skill / Memory / Consolidate / Dashboard / Prompts / Users / Connectors / Policies / Admin / About). Streamlit handles auth via the API key issued in step A-3.

### A-5. (Optional) put it on a stable URL
- **Behind nginx / Caddy / Cloudflare Tunnel**: terminate TLS, proxy to `localhost:8501`.
- **Docker**: see [docs/docker.md] (TODO — currently you can build your own Dockerfile based on the install steps above).
- **Kubernetes**: a single Deployment + PersistentVolumeClaim for `.praxia/`.

The Streamlit UI is a thin wrapper over the same SDK that mode B uses, so anything reachable in the UI is reachable in code.

---

## Mode B. Backend-only (you bring the frontend)

Two ways to integrate:

### B-1. Embed via Python SDK (in-process)

If your frontend (FastAPI / Django / Flask / Slack bot / mobile backend) is already Python, just `import praxia`:

```python
from praxia import Praxia, LLM
from praxia.skills.business import InvestmentSkill
from praxia.skills.output_format import OutputFormatSkill

loom = Praxia(user_id="alice", llm=LLM("claude"))

# 1. Run a domain skill — get Markdown back
md = InvestmentSkill(llm=loom.llm).run("Q3 review of a hypothetical mid-cap")

# 2. Render to whatever the user asked for
result = OutputFormatSkill().deliver(md, user_request="パワポで")
return result.bytes  # ← serve as application/vnd.openxmlformats-...
```

That's it. Your FastAPI route handler does the work; Praxia is a library.

### B-2. Run as an HTTP service (out-of-process)

When your frontend is **not** Python (Next.js, mobile, Go, etc.) you need an HTTP boundary. Praxia ships a small FastAPI wrapper:

```bash
pip install "praxia[server]"
praxia serve --host 0.0.0.0 --port 8000
```

Endpoints (versioned under `/api/v1`):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/auth/login` | POST | Exchange API key for JWT |
| `/api/v1/flows/{name}` | POST | Run a flow with input JSON |
| `/api/v1/skills/{name}` | POST | One-shot skill call |
| `/api/v1/memory/search` | POST | Semantic search over personal memory |
| `/api/v1/memory/mode` | PUT | Change accumulate / read_only |
| `/api/v1/export` | POST | Render content to html/pptx/docx/json |
| `/api/v1/oauth/{provider}/start` | POST | Begin per-user OAuth flow |
| `/api/v1/oauth/{provider}/callback` | GET | OAuth redirect handler |

Authentication: `Authorization: Bearer <jwt>` (issued by `/auth/login`) or `X-API-Key: <raw>`. Same RBAC + audit log as the SDK / UI.

> **Note**: the FastAPI wrapper module is at `praxia.server.app`. If you need an endpoint that isn't yet wired, you can either (a) sub-class the SDK objects directly in your own FastAPI app, or (b) open an issue.

---

## Choosing a backend (LTM) per deployment

Whatever mode you pick, the LTM backend is configurable:

| Setting | Where | Effect |
|---|---|---|
| `PRAXIA_MEMORY_BACKEND` env var | `.env`, shell | Default backend for everyone |
| `praxia admin memory-policy-set --enforced-backend mem0` | CLI | Pins all users to one backend |
| `praxia memory backend --user-id alice mem0` | CLI | Per-user preference (subject to admin policy) |
| `PersonalMemory(..., backend=CompositeBackend(...))` | SDK | Per-call multi-LTM ensemble (see [FEATURES.md § 5.1](FEATURES.md#51-multi-ltm-fusion--dynamic-routing-accuracy-boost)) |

Resolution precedence: admin enforced > call-site argument > user pref > admin default > `"json"`.

---

## Per-user accumulate vs read-only

Both modes support a per-user toggle:

```bash
praxia memory mode --user-id alice accumulate   # writes pass through (default)
praxia memory mode --user-id alice read_only    # writes are silently dropped, reads still work
praxia memory show --user-id alice              # see the resolved config + reason
```

In **read_only** mode, `record_episode / record_fact / record_outcome / record_preference` become no-ops — useful when a user wants the assistant's help without leaving a memory trail (e.g., reviewing a legal document, exploring sensitive data).

Admins can lock the mode for the whole tenant or for specific roles:
```bash
praxia admin memory-policy-set --default-mode read_only --mode-locked
praxia admin memory-policy-set --accumulate-locked-roles operator,admin
```

---

## Production checklist

| Item | Mode A (full-stack) | Mode B (backend-only) |
|---|---|---|
| TLS termination | nginx / Caddy / Cloudflare Tunnel in front of `:8501` | Same, in front of `:8000` |
| Persistent storage | PersistentVolume / EBS for `.praxia/` | Same |
| Bootstrap admin key | Stored from `praxia init` output, rotated via `praxia user rotate-key` | Same |
| LLM provider keys | `.env` / `praxia config set` / cloud secret manager | Same |
| OAuth callback URL | `https://your-host/oauth/callback` (handled by Streamlit) | Same path served by `/api/v1/oauth/{provider}/callback` |
| Audit log retention | Append-only JSONL under `.praxia/audit/` — back up daily | Same |
| Rate limiting | Streamlit doesn't have built-in rate limits — put it behind a WAF | Add FastAPI rate-limit middleware (slowapi) |
| Multi-tenant isolation | Single tenant per process (separate `.praxia/` per tenant) | Same — run a process per tenant or shard storage by `org_id` |

---

## When to upgrade A → B

Start with mode A; you'll know it's time for mode B when one of these is true:

1. You want **single sign-on into your existing portal**, and Streamlit's auth doesn't fit.
2. You need a **mobile or non-Python client** (mobile, Slack, Teams).
3. You want to **A/B test UIs** without redeploying the brain.
4. You need **CDN-cached frontend assets** that Streamlit can't serve efficiently.

The migration is mechanical: every Streamlit tab maps 1:1 to an SDK call, which maps 1:1 to an HTTP endpoint.
