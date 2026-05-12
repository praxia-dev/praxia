// Google Analytics 4 — opt-in gated via consent.js.
//
// Privacy model:
//   - gtag.js is NOT loaded on initial page render
//   - It loads only after the visitor opts into "Analytics" in the
//     consent banner (or has previously opted in via localStorage)
//   - IP anonymization on; cookies SameSite=Lax;Secure
//
// Wiring:
//   - consent.js defines window.praxiaEnableAnalytics() hook
//   - When user opts in, consent.js calls our loadGA()
//   - On subsequent page loads (prior opt-in already stored),
//     we self-trigger via the DOMContentLoaded check below
//
// Tracking surface:
//   - Standard pageview (gtag config)
//   - "click_github"  — outbound clicks to github.com/praxia-dev/*
//   - "click_youtube" — outbound clicks to YouTube (demo video etc.)
//
// To change Measurement ID, update GA_ID below and redeploy.

(function () {
  const GA_ID = "G-2128CCW5WP";

  function loadGA() {
    if (window.__praxiaGAReady) return;
    window.__praxiaGAReady = true;

    // 1. Inject the gtag.js loader
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
    document.head.appendChild(s);

    // 2. Initialize gtag
    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    window.gtag = gtag;
    gtag("js", new Date());
    gtag("config", GA_ID, {
      anonymize_ip: true,                 // GDPR-friendly
      cookie_flags: "SameSite=Lax;Secure", // cookie hardening
    });

    // 3. Outbound click tracking — fires before the page navigates away
    document.addEventListener("click", function (e) {
      const a = e.target.closest("a[href]");
      if (!a) return;
      const href = a.href || "";

      if (href.includes("github.com/praxia-dev")) {
        gtag("event", "click_github", {
          event_category: "outbound",
          event_label: href,
          transport_type: "beacon",
        });
      } else if (href.includes("youtu.be/") || href.includes("youtube.com/")) {
        gtag("event", "click_youtube", {
          event_category: "outbound",
          event_label: href,
          transport_type: "beacon",
        });
      } else if (href.includes("x.com/praxia") || href.includes("twitter.com/praxia")) {
        gtag("event", "click_x", {
          event_category: "outbound",
          event_label: href,
          transport_type: "beacon",
        });
      }
    });
  }

  // Expose the activation hook consent.js looks for
  window.praxiaEnableAnalytics = loadGA;

  // Auto-enable if the visitor opted in on a previous visit
  // (consent.js sets window.praxiaConsent.analytics from localStorage)
  function autoEnable() {
    if (window.praxiaConsent && window.praxiaConsent.analytics) {
      loadGA();
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoEnable);
  } else {
    autoEnable();
  }
})();
