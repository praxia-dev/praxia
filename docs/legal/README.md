# Praxia Legal Documents

> **⚠️ DISCLAIMER**: These documents are **templates** prepared for an
> alpha-stage open-source project. They are **not a substitute for
> qualified legal advice**. Before using Praxia commercially or
> processing personal data on behalf of customers, have these reviewed
> and adapted by a lawyer admitted in your jurisdiction.

## Documents

| Document | Audience | Status |
|---|---|---|
| [LICENSE](../../LICENSE) | OSS code users | ✅ Apache 2.0 (final) |
| [NOTICE](../../NOTICE.md) | OSS code users | ✅ Final |
| [Terms of Service](TERMS.md) | Users of hosted Praxia (`praxia.tools`, portal) | 🟡 Template — review with counsel |
| [Privacy Policy](PRIVACY.md) | Visitors + portal sign-ups | 🟡 Template — review with counsel |
| [Acceptable Use Policy](ACCEPTABLE_USE.md) | All users | 🟡 Template |
| [Cookie Policy](COOKIES.md) | Website visitors | 🟡 Template |
| [GDPR Notes (EN)](GDPR_NOTES.md) / [JA](GDPR_NOTES.ja.md) | Operators with EU users | 🟡 Operational guidance — not legal advice |
| [Trademark Policy (EN)](TRADEMARK.md) / [JA](TRADEMARK.ja.md) | Forks, plugins, third-party uses of "Praxia" | ✅ Policy v1.0 (registration pending) |

## When you need each

| Phase | Required documents |
|---|---|
| OSS-only (`pip install praxia`) | Just LICENSE + NOTICE |
| Landing page (informational only) | LICENSE + NOTICE + minimal Privacy / Cookie |
| Portal with sign-up | + Terms of Service + Privacy Policy + AUP |
| Paid customers (Team / Enterprise) | + Service Agreement + DPA (Data Processing Agreement) per customer |
| EU customers | All of the above + GDPR-compliant Privacy Policy + DPA |
| Japan B2B customers | All of the above + 個人情報保護法 適合プライバシーポリシー (JP version) |

## Recommended next steps before commercial use

1. **Engage a lawyer** familiar with SaaS / OSS in your jurisdiction
2. **Translate** for primary markets (JP / EN essential)
3. **DPA template** for B2B customers (especially in regulated industries)
4. **Run a privacy audit** of all data flows (memory store, audit log, connectors)
5. **Add IDs** (entity name + contact) to each doc once formalized

## Updating these docs

When updating, **always log the change** at the top of each file (date +
short summary). Material changes to ToS / Privacy require notifying
existing users.

```
## Changelog
- 2026-05-15: Initial template drafted
- 2026-MM-DD: Reviewed by [lawyer], operationalized
- 2026-MM-DD: Added GDPR-compliant clauses
```
