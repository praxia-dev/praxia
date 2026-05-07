# Privacy Policy — Praxia

> **⚠️ TEMPLATE NOTICE**: This is a starting template and **has not been
> reviewed by counsel**. Before processing personal data of EU
> residents (GDPR), California residents (CCPA), Japanese residents
> (個人情報保護法), or other regulated populations, have a qualified
> privacy lawyer review and adapt this document for your jurisdiction.

**Effective date**: TO BE FINALIZED
**Controller**: GenArch (the "Provider")
**Contact**: `hello@praxia.tools` · Privacy / data subject requests:
`privacy@praxia.tools`

---

## 1. What this policy covers

This policy describes how the Provider collects, uses, and protects
personal data when you use:

- The Praxia website (`praxia.tools`, `praxia.tools`,
  `genarch.github.io/praxia`)
- The Praxia portal (sign-in / sign-up forms)
- Any hosted Praxia service operated by the Provider

It does **not** cover the open-source Praxia software running on your
own infrastructure — when you self-host, you are the controller of any
data you process.

## 2. What we collect

### When you visit the website (no account)

- **Request metadata**: IP address, user-agent, referring URL, time of
  visit (collected by hosting provider — Cloudflare or GitHub Pages —
  for security and operations)
- **Aggregated analytics** (if enabled): page views, country (no
  individual tracking)
- **Cookies**: see our [Cookie Policy](COOKIES.md)

### When you create a portal account

- Email address (required)
- Organization name (required)
- Plan selection (required)
- Authentication information (password hash if email/password; OAuth
  provider identifier if SSO)

### When you use the hosted Praxia service

- **Conversation content** you submit (queries, uploaded files, audio
  recordings)
- **Generated output** from the agents
- **Memory entries** auto-extracted from your interactions (Layer 1
  personal memory)
- **Skill / flow invocation logs**
- **Audit log** of privileged operations (see Section 6)

### When you make a payment (paid plans)

- Billing address, organization details
- Payment processor identifiers (we do **not** store card numbers — they
  are handled by Stripe / equivalent processor)

## 3. How we use information

- **Provide the Service**: process your queries, store your memory,
  return results
- **Improve the Service** (only with your consent): aggregate usage
  patterns to improve default skills and flows
- **Security**: detect abuse, debug, comply with law
- **Communication**: respond to your inquiries, send service updates
- **Billing**: invoice and collect payment

We do **not** sell personal data. We do **not** use your conversation
content or memory entries to train Praxia's models or any third-party
model.

## 4. Sharing with third parties

To deliver the Service, we share data with:

| Third party | Purpose | Data shared |
|---|---|---|
| LLM providers you select (Anthropic / OpenAI / Google / Alibaba) | Generate agent responses | Your prompt + retrieved context |
| Memory backend you select (Mem0 / LangMem / etc., if hosted) | Persistent memory storage | Memory entries |
| Connector targets you authorize (Box / SharePoint / etc.) | Pull / push data on your behalf | Specific resources you specify |
| Hosting provider (Cloudflare, GitHub) | Serve the website | Request metadata |
| Payment processor (Stripe / equivalent) | Process payments | Billing details |

You can review and choose your providers in the Praxia configuration.
**Self-hosted deployments retain full data sovereignty**.

We do not share with advertisers, data brokers, or other commercial
third parties.

## 5. International transfers

Your data may be processed in regions where our service providers
operate (typically the EU, US, and Japan). Where required by law (e.g.,
GDPR), we use Standard Contractual Clauses or equivalent safeguards.

## 6. Audit log

The hosted Praxia service maintains an append-only audit log of
privileged operations (login, policy decisions, memory writes, exports).
This log is retained for security and compliance, typically for 12
months unless a longer retention is mandated by law or contract.

## 7. Retention

- **Personal memory entries**: retained while your account is active;
  deleted within 90 days of account closure unless you request export
- **Audit logs**: 12 months (or longer if required by contract)
- **Payment records**: retained as required by accounting / tax law
  (typically 7 years in Japan)
- **Marketing emails**: until you unsubscribe

## 8. Your rights

Depending on your jurisdiction, you may have the right to:

- **Access** the personal data we hold about you
- **Correct** inaccurate data
- **Delete** your data (subject to legal retention requirements)
- **Export** your data in a portable format
- **Object** to certain processing activities
- **Withdraw consent** where processing is based on consent
- **Lodge a complaint** with your local data protection authority

To exercise these rights, contact `privacy@praxia.tools`. We respond
within 30 days.

## 9. Security

We implement reasonable technical and organizational measures, including:

- HTTPS / TLS for all data in transit
- Encryption at rest for memory backends that support it
- API key + JWT authentication for the hosted service
- Resource access policies (ACL) for fine-grained authorization
- Append-only audit log
- Regular dependency vulnerability scanning

We do **not** currently hold SOC2 Type II or ISO 27001 certifications.
Certifications are on the roadmap; until then, our architecture is
"compliance-ready" and we provide audit-prep documentation on request.

For paid customers handling sensitive data, additional safeguards are
negotiated in a separate **Data Processing Agreement (DPA)**.

## 10. Children

The Service is not directed to children under 16 (or applicable local
threshold). We do not knowingly collect data from children.

## 11. Changes to this policy

We may update this policy. Material changes will be announced to active
users at least 30 days before taking effect.

## 12. Contact

- General privacy inquiries: `privacy@praxia.tools`
- Data subject requests: `privacy@praxia.tools`
- Security incidents: `security@praxia.tools`

For Japanese residents: 個人情報保護法に基づくお問い合わせは上記アドレスへ。

---

## Changelog

- 2026-05-05: Initial template drafted (not yet reviewed by counsel)
