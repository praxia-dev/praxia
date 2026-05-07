# Praxia Landing Page & Portal

Static, dependency-free landing page (`index.html`) and sign-in portal
(`portal/index.html`). Inspired by [Hermes Agent](https://hermes-agent.nousresearch.com/)
and modern SaaS marketing sites.

## Layout

```
web-publish/
├── index.html        — main landing page (hero / features / pricing)
├── styles.css        — shared theme (dark + warm-gold accent)
├── 404.html          — branded 404 page (used by both mirrors)
├── robots.txt        — search-engine crawl directives
├── sitemap.xml       — URL list for search engines
├── _redirects        — Cloudflare Pages convenience aliases
├── _headers          — Cloudflare Pages security headers + caching
├── .nojekyll         — disables Jekyll on GitHub Pages
├── DEPLOY.md         — full deployment walkthrough (CF + GH Pages)
└── portal/
    ├── index.html    — sign-in + sign-up portal
    └── portal.css    — portal-specific styles
```

## Deployment

We run both **Cloudflare Pages** (primary, fast) and **GitHub Pages** (secondary, integrated). See **[DEPLOY.md](DEPLOY.md)** for the full walkthrough.

## Local preview

```bash
cd web-publish
python -m http.server 8000
# then open http://localhost:8000
```

## Customization

If you forked the repo to a different GitHub org, replace `praxia-dev` in HTML/href links accordingly. A bulk find-replace works:

```bash
find web-publish -type f \( -name "*.html" -o -name "*.md" \) \
  -exec sed -i 's|praxia-dev|your-org|g' {} +
```

For the **portal**, the SSO buttons and forms are wired with placeholder
JavaScript that calls `/auth/sso/<provider>/start` and `/auth/signin`.
Connect them to your backend endpoints (FastAPI / Django / Next.js API)
that delegate to `praxia.auth`.

A minimal FastAPI integration sketch is in `docs/portal-backend.md` (TODO).

## Brand notes

- **Mark**: ▣ (small filled square, hint at "shared block")
- **Color palette**:
  - Background: `#0a0a0f` (deep navy-black)
  - Accent: `#c9a456` (warm gold — "applied wisdom")
  - Text: `#ecedf0`
- **Typography**: system font stack with JetBrains Mono for code
- **Vibe**: serious / professional / dark — appropriate for B2B AI tooling
