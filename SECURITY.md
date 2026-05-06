# Security Policy

## Supported versions

Praxia is in alpha. The latest minor release receives security fixes.

| Version | Supported |
|---|---|
| 0.1.x   | ✅ |
| < 0.1   | ❌ |

## Reporting a vulnerability

**Do not** open a public GitHub issue for security vulnerabilities.

Instead, use one of these confidential channels:

1. **GitHub Security Advisory** (preferred):
   <https://github.com/your-org/praxia/security/advisories/new>
2. **Email**: open an issue requesting contact, and we will reply with a
   confidential channel.

We will:

- Acknowledge receipt within **72 hours**.
- Provide a preliminary assessment within **7 days**.
- Issue a fix and coordinated disclosure within **30 days** for confirmed
  high-severity issues.

## Scope

In scope:

- The Praxia framework code (`praxia/` package)
- Distributed plugins maintained in the Praxia Org
- Default Streamlit UI, CLI, and SDK

Out of scope (please report upstream):

- LLM provider APIs (Anthropic, OpenAI, Google, Alibaba)
- Memory backends (Mem0, LangMem, Letta, Zep, HindSight) — report to those
  projects directly
- Connector SDKs (Box, Microsoft Graph, Dropbox, Google API, kintone REST,
  Salesforce SDK)

## Data handling reminders for users

Praxia stores personal memory and audit logs **locally on disk by default**
(`.praxia/` directory). When using a hosted memory backend or connector,
data leaves your machine according to that service's terms.

Always review `praxia.auth.policies` (resource ACL) before enabling
production connectors, especially for sensitive folders or sObjects.

## Security posture in the OSS

Practical, observable security hygiene applied to this project:

| Control | Tool / mechanism |
|---|---|
| **Static analysis (SAST)** | `bandit` runs on every PR (`.github/workflows/security.yml`) |
| **Dependency scanning** | `pip-audit` runs on every PR + nightly cron |
| **Lockfile pinning** | `pyproject.toml` declares minimum versions; deployments should `pip-compile` to a `requirements.lock` |
| **Secrets in repo** | `gitleaks` recommended as pre-commit hook (operators add to their fork) |
| **Commit signing** | DCO `Signed-off-by:` required (verified by `dco.yml`); cryptographic signatures (`-S`) recommended |
| **OAuth token at rest** | Envelope-encrypted via configurable KMS (`local`/`aws`/`azure`/`gcp`/`vault`). Master key never on the application host |
| **JWT signing key** | Operator-supplied, never default; rotation procedure documented in `docs/specs/functional-spec.ja.md` |
| **API keys** | Bcrypt-hashed at rest; one-time display; rotation in single CLI command |
| **Audit log** | Append-only JSONL with file permission 0600. Tampering is detectable but not cryptographically prevented in v1 (Merkle / external SIEM forwarding is on the roadmap) |
| **CSRF on OAuth** | State token is high-entropy, single-use, persisted with TTL across workers |
| **PKCE** | Used by all providers that support it (5/12 default providers) |
| **Connector input safety** | Path / query parameters are passed verbatim to vendor SDKs — vendors are responsible for their own injection-safe APIs. Praxia does not interpret these strings as shell commands |
| **No telemetry** | Praxia ships with **zero outbound calls** by default. Operators who want analytics opt in via webhook subscriptions |

## Why "OSS connector code" is **not** an attack risk

A common concern: "if the connector code is open source, attackers know
how it talks to the SaaS — won't they exploit that?"

The honest answer: **no, that's not where the attack surface lives.**

1. **OAuth is a public spec.** Every connector talks to the vendor's
   public OAuth + REST endpoints. The protocol is documented by the
   vendor. Reading our code adds zero attacker advantage.
2. **Tokens are encrypted at rest.** An attacker reading the connector
   code gains nothing without the customer's KMS key — which lives in
   the customer's cloud, not in the OSS.
3. **The customer's deployment is the boundary.** Vulnerabilities, if
   any, live in the running deployment (misconfiguration, weak KMS,
   unpatched dependency) — not in the source code.
4. **OSS gets more eyes.** OpenSSL, OpenSSH, sshd, the Linux kernel,
   PostgreSQL, Kubernetes — every piece of internet-critical
   infrastructure is OSS. The model works.
5. **Procurement often *prefers* OSS.** Banks, governments, and
   regulated industries frequently require the ability to audit source
   code as a condition of adoption. Closed-source SaaS fails that bar.

What **is** worth worrying about (for any software, OSS or not):
- Supply chain (typosquatting on PyPI, malicious dependency updates)
- Misconfigured deployments (default secrets, world-readable files)
- Unmaintained third-party libraries

Praxia mitigates these via the controls in the table above. If you spot
something that should be tighter, please open a Security Advisory.
