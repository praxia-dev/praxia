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
