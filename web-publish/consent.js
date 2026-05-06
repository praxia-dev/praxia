// Cookie / analytics consent banner — GDPR + CCPA compliant.
//
// Categories:
//   - "essential" : always on (language preference, consent record itself)
//   - "analytics" : default off; only set after explicit opt-in
//
// Storage:
//   - localStorage["praxia-consent"] = JSON
//       {"essential": true, "analytics": bool, "ts": <epoch>, "v": "1"}
//
// Show conditions:
//   - First visit (no stored consent) → show banner
//   - Stored consent exists → no banner; provide "Cookie preferences" link
//     in footer to re-open it
//
// Translation: uses keys from i18n.js (consent.*). Re-render on language
// change.
//
// Analytics activation:
//   - When user opts in, calls window.praxiaEnableAnalytics() if defined.
//     Operators wire this to their actual analytics call (Cloudflare
//     Insights, Plausible, GoatCounter, etc.).
//   - When user opts out / on first load with no opt-in, analytics is NOT
//     loaded. Operators must check window.praxiaConsent.analytics before
//     loading any analytics script.

(function () {
  const STORAGE_KEY = "praxia-consent";
  const VERSION = "1";

  // ---- Public API surface --------------------------------------------------
  window.praxiaConsent = {
    essential: true,    // always
    analytics: false,   // determined by user choice
    ready: false,
  };

  // ---- Storage helpers -----------------------------------------------------
  function loadConsent() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (data.v !== VERSION) return null;  // version mismatch → re-prompt
      return data;
    } catch {
      return null;
    }
  }

  function saveConsent(prefs) {
    const data = {
      v: VERSION,
      essential: true,
      analytics: !!prefs.analytics,
      ts: Date.now(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    applyConsent(data);
  }

  function applyConsent(data) {
    window.praxiaConsent.essential = true;
    window.praxiaConsent.analytics = !!data.analytics;
    window.praxiaConsent.ready = true;
    // Fire activation hook only when analytics is enabled
    if (data.analytics && typeof window.praxiaEnableAnalytics === "function") {
      try {
        window.praxiaEnableAnalytics();
      } catch (e) {
        console.warn("praxiaEnableAnalytics failed:", e);
      }
    }
    // Notify any listeners
    document.dispatchEvent(new CustomEvent("praxia-consent-changed", {detail: data}));
  }

  // ---- DOM construction ----------------------------------------------------
  function buildBanner() {
    if (document.getElementById("praxia-consent-banner")) return;

    const overlay = document.createElement("div");
    overlay.id = "praxia-consent-banner";
    overlay.className = "consent-banner";
    overlay.innerHTML = `
      <div class="consent-card" role="dialog" aria-labelledby="consent-title" aria-describedby="consent-body">
        <h3 id="consent-title" data-i18n="consent.title">We use cookies</h3>
        <p id="consent-body" data-i18n="consent.body">…</p>
        <div class="consent-categories" hidden id="consent-detail">
          <label class="consent-row">
            <input type="checkbox" checked disabled>
            <span data-i18n="consent.cat_essential">Essential</span>
          </label>
          <label class="consent-row">
            <input type="checkbox" id="consent-analytics-cb">
            <span data-i18n="consent.cat_analytics">Analytics</span>
          </label>
        </div>
        <div class="consent-actions">
          <button class="btn btn-ghost btn-sm" id="consent-customize" data-i18n="consent.customize">Customize</button>
          <button class="btn btn-ghost btn-sm" id="consent-essential" data-i18n="consent.essential_only">Essential only</button>
          <button class="btn btn-primary btn-sm" id="consent-accept" data-i18n="consent.accept_all">Accept all</button>
          <button class="btn btn-primary btn-sm" id="consent-save" hidden data-i18n="consent.save">Save preferences</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    // Re-translate the newly-injected nodes (i18n.js may already have run)
    if (window.praxiaApplyI18n) {
      window.praxiaApplyI18n();
    }

    // Wire interactions
    document.getElementById("consent-accept").addEventListener("click", () => {
      saveConsent({analytics: true});
      hideBanner();
    });
    document.getElementById("consent-essential").addEventListener("click", () => {
      saveConsent({analytics: false});
      hideBanner();
    });
    document.getElementById("consent-customize").addEventListener("click", () => {
      const detail = document.getElementById("consent-detail");
      const save = document.getElementById("consent-save");
      detail.hidden = false;
      save.hidden = false;
      document.getElementById("consent-accept").hidden = true;
      document.getElementById("consent-essential").hidden = true;
      document.getElementById("consent-customize").hidden = true;
    });
    document.getElementById("consent-save").addEventListener("click", () => {
      const cb = document.getElementById("consent-analytics-cb");
      saveConsent({analytics: cb.checked});
      hideBanner();
    });
  }

  function hideBanner() {
    const el = document.getElementById("praxia-consent-banner");
    if (el) el.remove();
  }

  function showBanner() {
    if (document.getElementById("praxia-consent-banner")) return;
    buildBanner();
  }

  // ---- Footer "Cookie preferences" link ------------------------------------
  function injectFooterLink() {
    const footer = document.querySelector(".footer");
    if (!footer || document.getElementById("consent-manage-link")) return;
    const a = document.createElement("a");
    a.id = "consent-manage-link";
    a.href = "#";
    a.className = "consent-manage-link";
    a.setAttribute("data-i18n", "consent.manage");
    a.textContent = "Cookie preferences";
    a.addEventListener("click", e => {
      e.preventDefault();
      showBanner();
    });
    // Find the existing footer-bottom row and prepend the link
    const bottom = footer.querySelector(".footer-bottom");
    if (bottom) bottom.appendChild(a);
    else footer.appendChild(a);
  }

  // ---- Init ----------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    injectFooterLink();
    const stored = loadConsent();
    if (stored) {
      // Apply stored prefs without showing banner
      applyConsent(stored);
    } else {
      // First visit — show banner (translations applied on the fly)
      showBanner();
    }
  });

  // Re-translate on language switch
  document.addEventListener("praxia-lang-changed", () => {
    if (window.praxiaApplyI18n) window.praxiaApplyI18n();
  });
})();
