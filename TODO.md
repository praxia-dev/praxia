# TODO — Praxia operational backlog

Open items that aren't ready to merge yet but need to be tracked. Each
entry has an owner placeholder and rough effort. Move resolved items to
the bottom under "Done — keep for changelog".

## 🔧 Pending — placeholders to fill once info is available

### URLs / handles to swap in once finalized
- [ ] **GitHub repo**: replace `https://github.com/genarch/praxia` with the real repo URL.
  Affected files: `web-publish/index.html` (10+ occurrences), `web-publish/portal/index.html`,
  `README.md`, `PUBLISH.md`, `zenn-publish/0[0-6]*.md`, `docs/*.md` (links to blob/main paths).
  Bulk-fix command (PowerShell):
  ```powershell
  Get-ChildItem -Recurse -Include *.html,*.md,*.js,*.py |
    ForEach-Object { (Get-Content $_ -Raw) -replace 'github\.com/genarch/praxia','github.com/<NEW-ORG>/<NEW-REPO>' |
                      Set-Content $_ }
  ```
- [ ] **Web home**: confirm `praxia.dev` ownership. If different, replace canonical/alternates in
  `web-publish/index.html` (lines 12-20) + the ~10 `praxia.pages.dev` and `genarch.github.io/praxia`
  references in `index.html`, `404.html`, `_redirects`, `sitemap.xml`, `portal/index.html`,
  `web-publish/DEPLOY.md`, `web-publish/README.md`.
- [ ] **Email addresses**: today the page advertises `hello@praxia.dev` (contact),
  `privacy@praxia.dev` (legal), `security@praxia.dev` (SECURITY.md). Confirm domain + that the
  inboxes route somewhere read.
- [ ] **X / Twitter handle**: account TBD. Once obtained:
    1. add a `<li><a href="https://x.com/<HANDLE>" data-i18n="footer.com.x">𝕏</a></li>`
       to the footer's "Community" column in `web-publish/index.html`.
    2. add 8-language `footer.com.x` translations to `web-publish/i18n.js`.
    3. mention it in `README.md` near the GitHub badge.

### Tally waitlist form
- [ ] Create the Tally form (see fields list in the HTML comment of
      `web-publish/portal/index.html`).
- [ ] Replace `REPLACE_WITH_TALLY_FORM_ID` placeholder with the published form's id.
- [ ] Add a notification webhook (Slack / email / Notion) so submissions surface in real time.

### Pricing & commercial messaging (decision needed — see proposal in chat / below)
- [ ] Decide whether to keep the 3-tier pricing on the landing or downscale to
      OSS-only + waitlist while we're alpha. **Recommendation: downscale.**
- [ ] If downscaling, also remove "Pricing" from the nav for now (or rename to "Editions").
- [ ] Once a hosted backend actually runs, restore tier-2 with real pricing + Stripe link.

## 📋 Roadmap (not blocked on info)

### Hosted alpha plane (when waitlist starts converting)
- [ ] Decide hosting target: Cloudflare Workers + KV + Durable Objects, or
      Render / Fly.io with Postgres. (DO is cheaper, Render is more familiar.)
- [ ] Wire `praxia serve` behind a real custom domain with TLS.
- [ ] Implement the SSO redirect handlers that portal/index.html's earlier stub assumed
      (Google / MS / GitHub / Okta) — code already exists in `praxia/auth/sso.py`.
- [ ] Set up Stripe (or invoice-only first) for billing.

### Compliance & legal
- [ ] Confirm whether the legal templates in `docs/legal/` (TERMS / PRIVACY / AUP / COOKIES)
      have been reviewed by counsel. They're marked as templates — do not rely on them
      commercially without review.
- [ ] SOC 2 Type II / ISO 27001: roadmap-only. Mention only when actively pursuing.

### Marketing / community
- [ ] Publish the 7 Zenn articles (00_overview + 01..06 domain articles) in order. Each currently
      has `published: false` in frontmatter — flip to `true` when ready.
- [ ] Decide whether to post to Hacker News / r/MachineLearning / r/LocalLLaMA. (Probably wait
      until at least the GitHub repo URL is stable so traffic doesn't 404.)
- [ ] Twitter/X launch thread once the handle is acquired.

### Tech debt / bugs (from the recent feature push)
- [ ] Some German strings in `web-publish/i18n.js` had nested unicode quotes stripped to fix
      JS parse errors. They're correct but stylistically poorer; rephrase when convenient.
- [ ] Persona p1–p4 body content (lines 407-483 of `web-publish/index.html`) is still
      English-only — translate when bandwidth allows.
- [ ] OSS-edge bottom row (3 cards: KMS / OAuth callback / A/B+eval) titles still untagged
      and untranslated.
- [ ] Examples panel (10 industries × 5 strings each) is still English-only — translation
      pending.

## ✅ Done — keep for changelog later

- 2026-05-06 — Restructure: `docs/landing` → `web-publish/`, `docs/zenn` → `zenn-publish/`.
- 2026-05-06 — Portal sign-up: stub auth replaced with self-host CTA + Tally waitlist embed.
- 2026-05-06 — `praxia.agent.AutonomousAgent` shipped with 11 built-in tools, ACL/audit hooks,
              CLI command, MCP meta-tool, 13 deterministic tests.
- 2026-05-06 — Landing translations: 18 hero chips + 36 feature-card bodies + architecture +
              flows + skills + how-it-works bodies + fit lists + 19 FAQ pairs + footer +
              contact CTA — all in 8 languages.
- 2026-05-06 — Zenn: each of the 6 domain articles got a domain-specific AutonomousAgent
              section.
