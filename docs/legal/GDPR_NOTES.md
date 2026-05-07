# GDPR Notes

> 🇯🇵 日本語版: [GDPR_NOTES.ja.md](GDPR_NOTES.ja.md)
> Status: **template — review with qualified counsel before commercial use.**

This document explains who is the GDPR data controller in three common
scenarios involving Praxia. It is not legal advice. The role of "controller"
vs "processor" is highly fact-dependent and we encourage anyone running
Praxia in production with EU users to confirm their position with privacy
counsel.

---

## 1. Quick role mapping

| Scenario | You operate | EU data subjects involved? | Your GDPR role |
|---|---|---|---|
| **A.** You publish Praxia to PyPI / GitHub | Code distribution only | n/a | Out of scope (no personal data) |
| **B.** You self-host Praxia for your team | The Praxia install | Your colleagues / customers | **Controller** for memory + audit log + OAuth tokens |
| **C.** You run the Praxia.dev landing page | Static site + contact email | EU visitors | **Controller** for cookies + form submissions |
| **D.** You provide a managed Praxia service | Hosted Praxia + tenant data | Customer's end users | **Processor** for tenant data; **Controller** for billing / account data |
| **E.** You contribute a PR to Praxia | n/a | n/a | Out of scope |

---

## 2. Scenario A — OSS distribution

If your activity is limited to authoring code and publishing it to GitHub /
PyPI, **GDPR does not apply** to that activity. You are not collecting,
storing, or processing personal data via the codebase.

**Caveats:**
- GitHub itself processes your contributors' data (commit author email, IP).
  GitHub is the controller / processor for that — see GitHub's Privacy
  Statement.
- If you accept Issues / PRs, the contributor's email and content fall under
  GitHub's policies, not yours.
- Praxia ships templates (TERMS / PRIVACY / COOKIES / ACCEPTABLE_USE) for
  downstream operators to use after legal review. The templates themselves
  are not legal advice.

---

## 3. Scenario B — Self-hosted Praxia

When you run `praxia ui` / `praxia serve` on your infrastructure for users in
the EU, **you become the controller** for the personal data Praxia holds.

### 3.1 What personal data Praxia stores

Reviewing the code, the data categories are:

| Category | Where stored | Lawful basis (typical) |
|---|---|---|
| User account: username, email, role, last_login | `.praxia/auth/users/` | Contract / legitimate interest |
| API key hash (bcrypt) | Same | Contract |
| OAuth tokens (Box / SharePoint / Google / etc.) | `.praxia/auth/oauth_tokens.jsonl` (envelope-encrypted via KMS) | User consent |
| Personal memory (episodes / facts / preferences / outcomes) | `.praxia/personal/<user_id>.jsonl` (or chosen LTM backend) | Contract / legitimate interest |
| Audit log | `.praxia/auth/audit/audit.jsonl` (append-only, 0600 perms) | Legal obligation / legitimate interest |
| Connector pulls/pushes | Logged via audit log; payloads not persisted by default | Contract |
| Skill / flow inputs and outputs | Recorded as memory episodes (mode-controlled) | Contract |
| Session JWTs | Not persisted; signed with `PRAXIA_JWT_SECRET` | Contract |

### 3.2 Data subject rights — how to fulfill each

Praxia gives you tooling for GDPR Articles 15-22:

| Right | Article | How to fulfill in Praxia |
|---|---|---|
| Right of access | 15 | `praxia admin export-memory --user-id <id>` + `praxia admin export-users` (filter for the subject) + audit log filtered to actor |
| Right to rectification | 16 | `praxia user update <id> --email X` |
| Right to erasure | 17 | `praxia user delete <id>` (hard delete) — also clears their personal memory directory + revokes OAuth tokens. Audit log retains a redacted record of the deletion event. |
| Right to restrict processing | 18 | `praxia user deactivate <id>` (soft) or `praxia memory mode --user-id <id> read_only` |
| Right to portability | 20 | `praxia admin export-memory` outputs JSONL — machine-readable, structured, importable elsewhere |
| Right to object | 21 | Set memory mode to `read_only` per-user |
| Automated decision-making (Art. 22) | — | Praxia's outputs are advisory, not autonomous decisions |

**Note**: the audit log is intentionally append-only and survives `user.delete` (it records that the deletion happened). Speak to counsel about how to balance Article 17 erasure with Article 5(1)(f) integrity — most regulators accept tombstoning audit records over destroying them.

### 3.3 Required configuration in production

| Setting | Why |
|---|---|
| `PRAXIA_JWT_SECRET` (32+ random bytes, fixed) | Authentication integrity; session validity across restarts |
| `PRAXIA_TOKEN_ENC_KEY` or `PRAXIA_KMS_ADAPTER=aws/azure/gcp/vault` | Encryption-at-rest of OAuth tokens |
| File permissions on `.praxia/` | Restrict to the service user; audit files default to 0600 |
| Backups encrypted | `.praxia/` backups must preserve at-rest encryption properties |

### 3.4 Sub-processors (when you self-host)

If you choose `mem0` / `zep` / `hindsight` as the memory backend (or any
LLM provider), **you become a controller and they become your processor**
for the data you send them. You need:

- A Data Processing Agreement (DPA) with that vendor
- Standard Contractual Clauses (SCCs) if data flows EU → US (e.g., OpenAI,
  Anthropic, Google, AWS — most have these as click-through)
- Disclosure of these sub-processors to your EU users

Praxia supports running fully on-prem (Ollama Gemma + JSON backend) — that
configuration has no third-party sub-processors and is the simplest path
for highly regulated EU customers.

---

## 4. Scenario C — The Praxia.dev landing page

The static landing page processes:

| Data | Cookie / mechanism | Lawful basis |
|---|---|---|
| Chosen language | `localStorage["praxia-lang"]` | Strictly necessary (Art. 6(1)(f)) |
| Cookie consent record | `localStorage["praxia-consent"]` | Strictly necessary |
| Anonymous visit count | Cloudflare Web Analytics (cookie-less) — **only if user opts in** | Consent (Art. 6(1)(a)) |
| Contact email (`hello@praxia.tools`) submissions | Email inbox | Legitimate interest |

**The consent banner** ([consent.js](../landing/consent.js)) implements:
- Default-off for analytics (no analytics cookies set without explicit opt-in)
- "Accept all" / "Essential only" / "Customize" choices
- A persistent "Cookie preferences" link in the footer for re-opening
- Versioned consent records (re-prompt on policy changes)

**What you should do** when commercializing the site:
1. Have a real lawyer review the templates in this folder.
2. List your sub-processors (Cloudflare, GitHub Pages, Cloudflare Pages, your email provider).
3. Add a "How to contact us" line in PRIVACY.md with a real address.
4. Decide on a DPO requirement (if you become large enough or process special-category data).

---

## 5. Scenario D — Managed Praxia service (Team plan)

When you run a hosted multi-tenant Praxia for paying customers:

- **Customer account data** (billing, login emails) → you are the controller.
- **End-user data inside customer tenants** (memories, OAuth tokens) → you
  are typically the processor; the customer is the controller.
- You will need:
  - A signed DPA with each business customer (template + click-through).
  - A list of sub-processors (your hosting, your KMS provider, the LLM
    provider the customer chose).
  - A breach notification process: 72 hours to the customer (you to them);
    the customer notifies their regulator if needed.
  - Retention policy (default 12-24 months for active accounts; longer for
    audit log per legal-hold requirements).
  - Right-to-be-forgotten workflow tied to the `praxia user delete` and
    `praxia connector revoke-all` paths.

Praxia v1.0 is **not** delivered as a hosted service yet. When the Team plan
launches, this document will be updated with concrete sub-processor lists.

---

## 6. Special categories of data (Art. 9)

Praxia is **not designed** for processing health / political / biometric /
sexual-orientation data. If your use case touches these categories
(healthcare, HR background checks, criminal records), Article 9 imposes
additional safeguards:

- Higher-bar lawful basis (explicit consent or specific exemption)
- Data Protection Impact Assessment (DPIA, Art. 35) often required
- Stricter retention + access controls

For these use cases we recommend:
- `praxia memory mode --user-id X read_only` per session for sensitive content
- `praxia admin memory-policy-set --enforced-backend mem0 --mode-locked --default-mode read_only` for tenant-wide enforcement
- KMS-backed encryption for OAuth tokens (`PRAXIA_KMS_ADAPTER=aws` or stronger)
- Air-gapped operation if possible (Gemma + Ollama + JSON backend)

---

## 7. International transfers

If your EU users' data is transferred outside the EU/EEA (e.g., to a US-hosted LLM provider):

- You need a transfer mechanism: Standard Contractual Clauses (SCCs) is the
  most common; some vendors are certified under the EU-US Data Privacy
  Framework as of 2024.
- Praxia gives you the lever to **avoid the transfer entirely** — choose
  EU-region LLM endpoints or fully local models (Gemma / Qwen via Ollama).
- Document your decision and the safeguards in your Privacy Policy.

---

## 8. Children's data

Praxia is intended for business / professional use. We do not knowingly
process data of children under 16. The TERMS template requires users to
confirm they are at least 16 (or the local minimum age for online consent).

---

## 9. Useful links

- EDPB guidelines: <https://www.edpb.europa.eu/our-work-tools/our-documents_en>
- ICO (UK) GDPR guide: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/>
- CNIL (France): <https://www.cnil.fr/en/data-protection-around-the-world>
- Standard Contractual Clauses: <https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/standard-contractual-clauses-scc_en>

---

## 10. Reporting a privacy concern

If you believe Praxia has been used in a way that violates GDPR, or if you
spot a security/privacy issue in the codebase:

- Open an issue with the `privacy` label at <https://github.com/genarch/praxia/issues>
- Or email `security@praxia.tools` (PGP key TBD)

We aim to respond within 7 days.
