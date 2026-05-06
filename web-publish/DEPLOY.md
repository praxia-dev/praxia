# Deploy the landing page

We run **two mirrors** in parallel:

| Mirror | URL | Role |
|---|---|---|
| **Cloudflare Pages** | `https://praxia.pages.dev/` | **Primary / canonical** — fast worldwide (320+ POPs) |
| **GitHub Pages** | `https://genarch.github.io/praxia/` | **Secondary / fallback** — official, integrated with the repo |

Both mirrors serve the same files from `web-publish/`. Search engines see Cloudflare as canonical (via `<link rel="canonical">`); the GitHub Pages mirror shows a banner nudging visitors to switch.

---

## A. Cloudflare Pages setup (primary)

### One-time

1. **Sign up**: <https://dash.cloudflare.com/sign-up> (free, no credit card).
2. **Create project**:
   - Workers & Pages → Create → **Pages** → Connect to Git → GitHub
   - Authorize Cloudflare for the `genarch` org
   - Pick `genarch/praxia`
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
5. **Default URL**: `https://praxia.pages.dev/` (or `praxia-something.pages.dev` if the name is taken).

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

If you own `praxia.dev`:

1. Cloudflare Pages → your project → **Custom domains** → Set up a custom domain
2. Enter `praxia.dev`
3. Cloudflare auto-creates DNS records (if domain is on Cloudflare DNS)
4. SSL issues automatically; live in ~5 minutes

After DNS propagates, update:
- `<link rel="canonical">` in `index.html` → `https://praxia.dev/`
- `sitemap.xml` URLs
- `robots.txt` Sitemap line

---

## B. GitHub Pages setup (secondary)

### One-time

1. Push to `genarch/praxia` (Step 4 of [PUBLISH.md](../../PUBLISH.md))
2. **Settings → Pages**:
   ```
   Source:                 Deploy from a branch
   Branch:                 main
   Folder:                 /web-publish
   ```
3. Wait ~1 minute. URL: `https://genarch.github.io/praxia/`

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
| `praxia.pages.dev` (Cloudflare) | Nav shows `🔘 GitHub Pages mirror` pill; no banner |
| `genarch.github.io/praxia` (GH Pages) | Nav shows `🔘 Faster mirror (Cloudflare)` pill **and** a banner at the top of the page nudging users to switch |
| Local file:// preview | Nav pill points at GitHub repo |

The banner is dismissable per session (uses `sessionStorage`).

The HTML `<link rel="canonical">` always points at `https://praxia.pages.dev/`, so search engines consolidate ranking on the Cloudflare mirror.

---

## D. Verifying both mirrors

After both deploys:

```bash
# Verify Cloudflare returns the page
curl -sI https://praxia.pages.dev/ | head -5
#  → HTTP/2 200
#  → cf-ray: ...

# Verify GitHub Pages returns the page
curl -sI https://genarch.github.io/praxia/ | head -5
#  → HTTP/2 200

# Sanity-check the canonical tag
curl -s https://genarch.github.io/praxia/ | grep canonical
#  → <link rel="canonical" href="https://praxia.pages.dev/" />

# Sanity-check the security headers (Cloudflare only)
curl -sI https://praxia.pages.dev/ | grep -iE 'strict-transport|x-frame|content-security'
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

## G. Analytics (optional)

For privacy-friendly analytics on the Cloudflare mirror, add Cloudflare Web Analytics (free, no cookies):

1. Dashboard → Analytics & Logs → Web Analytics → Add a site
2. Copy the snippet
3. Paste into `index.html` just before `</body>`

Or use a self-hosted analytics solution (Plausible, Umami) if you want full data sovereignty.

---

## Summary

```
Push to main
  │
  ├─► Cloudflare Pages builds → https://praxia.pages.dev/  (30 s, primary)
  └─► GitHub Pages builds      → https://genarch.github.io/praxia/  (1 min, fallback)
       │
       └─► Visitor arrives → JS detects mirror → adapts nav + banner
```

Mirrors stay in sync automatically. Set it up once, then forget about it.
