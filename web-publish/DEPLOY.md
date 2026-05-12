# Deploy the landing page

We run **two mirrors** in parallel:

| Mirror | URL | Role |
|---|---|---|
| **Cloudflare Pages** | `https://praxia.tools/` | **Primary / canonical** — fast worldwide (320+ POPs) |
| **GitHub Pages** | `https://praxia-dev.github.io/praxia/` | **Secondary / fallback** — official, integrated with the repo |

Both mirrors serve the same files from `web-publish/`. Search engines see Cloudflare as canonical (via `<link rel="canonical">`); the GitHub Pages mirror shows a banner nudging visitors to switch.

---

## A. Cloudflare Pages setup (primary)

### One-time

1. **Sign up**: <https://dash.cloudflare.com/sign-up> (free, no credit card).
2. **Create project**:
   - Workers & Pages → Create → **Pages** → Connect to Git → GitHub
   - Authorize Cloudflare for the `praxia-dev` org
   - Pick `praxia-dev/praxia`
3. **Build settings**:
   ```
   Production branch:    main
   Framework preset:     None
   Build command:        (leave empty — pure static)
   Build output dir:     web-publish
   Root directory:       (leave empty)
   Environment vars:     (none)
   ```
4. **Save and Deploy**. The first build takes ~30 s.
5. **Default URL**: `https://praxia.tools/` (or `praxia-something.pages.dev` if the name is taken).

### Built-in features (no extra config required)

- ✅ HTTPS auto-issued
- ✅ HTTP/3 + Brotli
- ✅ DDoS protection
- ✅ 320+ POP CDN
- ✅ Unlimited bandwidth
- ✅ Preview deploys on every PR

### What's already wired in this repo

| File | Purpose |
|---|---|
| `_redirects` | Convenience aliases — `/github`, `/install`, `/quickstart`, etc. |
| `_headers` | Security headers (CSP, HSTS, frame-options) + 1-year cache for static |
| `404.html` | Branded 404 page |
| `robots.txt` | Allow all + sitemap |
| `sitemap.xml` | URL list for search engines |

### Custom domain (optional, $12/yr)

If you own `praxia.tools`:

1. Cloudflare Pages → your project → **Custom domains** → Set up a custom domain
2. Enter `praxia.tools`
3. Cloudflare auto-creates DNS records (if domain is on Cloudflare DNS)
4. SSL issues automatically; live in ~5 minutes

After DNS propagates, update:
- `<link rel="canonical">` in `index.html` → `https://praxia.tools/`
- `sitemap.xml` URLs
- `robots.txt` Sitemap line

---

## B. GitHub Pages setup (secondary)

### One-time

1. Push to `praxia-dev/praxia`
2. **Settings → Pages**:
   ```
   Source:                 Deploy from a branch
   Branch:                 main
   Folder:                 /web-publish
   ```
3. Wait ~1 minute. URL: `https://praxia-dev.github.io/praxia/`

### What's already wired

- `.nojekyll` — disables Jekyll processing (we hand-write HTML)
- `404.html` — same branded 404 page

### Caveat

GitHub Pages doesn't support `_redirects` or `_headers` — those Cloudflare-specific files are ignored harmlessly. If you need redirects on GH Pages, use HTML meta-refresh in a stub page.

---

## C. Cross-mirror behaviour

The landing page detects which mirror the visitor is on and adapts:

| You're visiting… | Behaviour |
|---|---|
| `praxia.tools` (Cloudflare) | Nav shows `🔘 GitHub Pages mirror` pill; no banner |
| `praxia-dev.github.io/praxia` (GH Pages) | Nav shows `🔘 Faster mirror (Cloudflare)` pill **and** a banner at the top of the page nudging users to switch |
| Local file:// preview | Nav pill points at GitHub repo |

The banner is dismissable per session (uses `sessionStorage`).

The HTML `<link rel="canonical">` always points at `https://praxia.tools/`, so search engines consolidate ranking on the Cloudflare mirror.

---

## D. Verifying both mirrors

After both deploys:

```bash
# Verify Cloudflare returns the page
curl -sI https://praxia.tools/ | head -5
#  → HTTP/2 200
#  → cf-ray: ...

# Verify GitHub Pages returns the page
curl -sI https://praxia-dev.github.io/praxia/ | head -5
#  → HTTP/2 200

# Sanity-check the canonical tag
curl -s https://praxia-dev.github.io/praxia/ | grep canonical
#  → <link rel="canonical" href="https://praxia.tools/" />

# Sanity-check the security headers (Cloudflare only)
curl -sI https://praxia.tools/ | grep -iE 'strict-transport|x-frame|content-security'
```

---

## E. Updating

Both mirrors auto-deploy from `main` on every push:

- **Cloudflare**: GitHub webhook triggers Pages build (~30 s)
- **GitHub Pages**: GitHub Actions builds and deploys (~1 min)

There is no manual deploy step. Land a PR → main updates → both mirrors update.

---

## F. When to disable one mirror

Run both mirrors permanently — there's no cost and the redundancy is free. Consider disabling GitHub Pages only if:

- You have a custom domain that points at Cloudflare (then GitHub Pages becomes confusing)
- You want to consolidate analytics in one place
- The maintenance overhead bothers you (it's near-zero)

To disable GitHub Pages: `Settings → Pages → Source: None`.

---

## G. Analytics

### Currently configured — Google Analytics 4 (opt-in gated)

`web-publish/analytics.js` loads GA4 only after the visitor opts into "Analytics" in the consent banner. Privacy posture:

- `gtag.js` is **not loaded on initial page render**
- IP anonymization on (`anonymize_ip: true`)
- Cookies hardened: `SameSite=Lax;Secure`
- Visitor can revoke at any time via the "Cookie preferences" link in the footer (handled by `consent.js`)

**Tracked events**:
- Standard page views
- `click_github` — outbound clicks to `github.com/praxia-dev/*`
- `click_youtube` — outbound clicks to the demo video / YouTube channel
- `click_x` — outbound clicks to the X / Twitter account

**Measurement ID**: stored in `web-publish/analytics.js` as `GA_ID`. To rotate, edit that constant and redeploy. Both Cloudflare and GitHub Pages mirrors pick up the change automatically.

**Where to see the data**:
- Real-time: <https://analytics.google.com/> → property `praxia.tools` → Reports → Realtime
- Acquisition: Reports → Life cycle → Acquisition (referrer / source / medium)
- Engagement: Reports → Life cycle → Engagement → Events (filter by `click_github` etc.)

### GitHub repo metrics (parallel signal, not GA)

GA cannot run inside github.com README pages. For repository-side metrics use **GitHub Insights**:

- Repo → Insights → **Traffic**: clones + visitors (14-day rolling window — bookmark the page or weekly screenshot if longer history matters)
- Repo → Insights → **Referrers**: shows `praxia.tools` and other sites that link in
- Repo → **Star history**: <https://star-history.com/#praxia-dev/praxia>

Together they give the full picture: GA on praxia.tools shows the funnel TOP, GitHub Insights shows what happened after they click through.

### Alternative analytics (not currently wired)

If you ever want to swap or supplement:

- **Cloudflare Web Analytics** — free, no cookies, no opt-in needed. Dashboard → Analytics & Logs → Web Analytics → copy snippet → paste in `index.html`.
- **Plausible / Umami** — self-hostable, GDPR-friendly. Same drop-in script pattern.

To disable GA entirely: delete the `<script src="analytics.js">` line in `index.html` + `portal/index.html`.

---

## Summary

```
Push to main
  │
  ├─► Cloudflare Pages builds → https://praxia.tools/  (30 s, primary)
  └─► GitHub Pages builds      → https://praxia-dev.github.io/praxia/  (1 min, fallback)
       │
       └─► Visitor arrives → JS detects mirror → adapts nav + banner
```

Mirrors stay in sync automatically. Set it up once, then forget about it.
