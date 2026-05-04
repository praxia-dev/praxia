# Praxia Landing Page & Portal

Static, dependency-free landing page (`index.html`) and sign-in portal
(`portal/index.html`). Inspired by [Hermes Agent](https://hermes-agent.nousresearch.com/)
and modern SaaS marketing sites.

## Layout

```
docs/landing/
├── index.html         — main landing page (hero / features / pricing)
├── styles.css         — shared theme (dark + warm-gold accent)
└── portal/
    ├── index.html     — sign-in + sign-up portal
    └── portal.css     — portal-specific styles
```

## Local preview

```bash
cd docs/landing
python -m http.server 8000
# then open http://localhost:8000
```

## Deploying

### Option 1: GitHub Pages (zero-config)

1. Settings → Pages → Build from `main` branch, `/docs/landing` folder
2. Done — `https://<your-org>.github.io/praxia/` serves the page

### Option 2: Vercel / Netlify

Connect the GitHub repo with build directory `docs/landing` (no build step).

### Option 3: Custom CDN

Just upload the three files (`index.html`, `styles.css`, `portal/`) to any
static host (S3 + CloudFront / Cloudflare Pages / Fastly).

## Customization

Replace `your-org` in HTML/href links once the GitHub repository is created.

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
