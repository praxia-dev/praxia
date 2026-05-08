"""Streamlit responsive helpers.

Streamlit doesn't have native mobile awareness, so we improve the
mobile experience via:

    1. Injected CSS that adjusts spacing, fonts, and layout under common
       breakpoints (≤768px tablet, ≤480px phone)
    2. A `compact_mode` session-state flag the user can flip for tighter
       spacing on slow connections / small screens
    3. Helpers that wrap `st.dataframe` / `st.tabs` / `st.expander` with
       sensible mobile defaults

Usage:
    from praxia.ui.responsive import inject_mobile_css, mobile_friendly_table

    inject_mobile_css()              # at top of app.py, after st.set_page_config
    mobile_friendly_table(df)        # auto-uses container width, scrolls on small
"""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


_MOBILE_CSS = """
<style>
/* --- Praxia UI: enterprise visual tone — restrained typography, square-ish
       widgets, calm interactions. Goal: looks like business software, not a
       consumer SaaS landing. */

/* Sober, neutral font stack. No stylistic-alternate font-feature-settings
   (those gave a "designy" feel). Slightly smaller global base size for
   denser, business-app feel. */
html, .stApp, body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto",
                 "Inter", "Helvetica Neue", "Hiragino Sans", "Noto Sans JP",
                 system-ui, sans-serif !important;
    font-size: 14px !important;  /* default is 16px */
}
.stMarkdown p, .stMarkdown li, label, [data-testid="stMarkdownContainer"] p {
    font-size: 0.9rem !important;
    line-height: 1.5 !important;
}
code, pre, [data-testid="stCode"], .stCode {
    font-family: "SF Mono", "JetBrains Mono", "Cascadia Code", "Consolas",
                 "Menlo", monospace !important;
    font-size: 0.825rem !important;
}

/* Calm heading hierarchy — slightly smaller across the board. */
.stMarkdown h1, h1 { font-size: 1.6rem !important; font-weight: 600 !important; letter-spacing: -0.005em !important; line-height: 1.25 !important; }
.stMarkdown h2, h2 { font-size: 1.3rem !important; font-weight: 600 !important; letter-spacing: -0.003em !important; line-height: 1.3 !important; }
.stMarkdown h3, h3 { font-size: 1.1rem !important; font-weight: 600 !important; }
.stMarkdown h4, h4 { font-size: 1rem !important; font-weight: 600 !important; }

/* Captions — denser. */
[data-testid="stCaptionContainer"], .stCaption,
small, [data-testid="stCaption"] {
    font-size: 0.78rem !important;
    line-height: 1.4 !important;
}

/* Buttons: square-ish, no lift, no shadow. Color change on hover only. */
.stButton button, .stDownloadButton button,
[data-testid="stFormSubmitButton"] button {
    border-radius: 4px !important;
    font-weight: 500 !important;
    transition: background-color 120ms ease, border-color 120ms ease !important;
    border-width: 1px !important;
}
.stButton button:hover, .stDownloadButton button:hover,
[data-testid="stFormSubmitButton"] button:hover {
    background-color: rgba(127, 127, 127, 0.06) !important;
}

/* Form inputs: square corners, solid borders. */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] div[role="combobox"],
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {
    border-radius: 4px !important;
    font-size: 0.9rem !important;
}

/* Checkbox + radio: align labels nicely */
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label {
    font-size: 0.9rem !important;
}

/* Metrics: square card, subdued border. */
[data-testid="stMetric"] {
    background: rgba(127, 127, 127, 0.03);
    border-radius: 4px;
    padding: 0.85rem 1rem !important;
    border: 1px solid rgba(127, 127, 127, 0.14);
}
[data-testid="stMetricValue"] {
    font-weight: 600 !important;
    letter-spacing: -0.005em !important;
}

/* Expanders: squared-off, conservative. */
[data-testid="stExpander"] {
    border-radius: 4px !important;
    border: 1px solid rgba(127, 127, 127, 0.16) !important;
    background: transparent;
}
[data-testid="stExpander"] summary {
    padding: 0.6rem 1rem !important;
    font-weight: 500 !important;
}

/* Tabs: thin underline, neutral indigo accent (replaces gold). */
[data-testid="stTabs"] [role="tablist"] {
    gap: 0 !important;
    border-bottom: 1px solid rgba(127, 127, 127, 0.22);
}
[data-testid="stTabs"] [role="tab"] {
    padding: 0.55rem 1rem !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    background: transparent !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #1e3a8a !important;
    border-bottom-color: #1e3a8a !important;
    font-weight: 600 !important;
}

/* Sidebar: subtle border on the right, slightly less heavy */
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(127, 127, 127, 0.08);
    padding-top: 1rem !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    margin-top: 0 !important;
    font-size: 1.1rem !important;
}

/* Chat messages: square, restrained bubble. */
[data-testid="stChatMessage"] {
    padding: 0.85rem 1rem !important;
    border-radius: 4px !important;
    border: 1px solid rgba(127, 127, 127, 0.12);
    background: rgba(127, 127, 127, 0.025);
    margin-bottom: 0.6rem !important;
}

/* Dividers: thinner, calmer */
hr { margin: 1.25rem 0 !important; opacity: 0.6 !important; }

/* Alerts: less shouty */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-width: 1px !important;
}

/* --- Praxia UI: hide Streamlit's default chrome that's irrelevant to the
       app user (Deploy button, hamburger menu, "Made with Streamlit" footer).
       These are dev-time conveniences — Praxia is the product, not Streamlit. */
[data-testid="stToolbar"] { visibility: hidden !important; height: 0 !important; position: fixed !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { visibility: hidden !important; height: 0 !important; position: fixed !important; }
.stDeployButton { display: none !important; }
#MainMenu { visibility: hidden !important; height: 0 !important; }
/* stHeader handling — DO NOT display:none it, otherwise the
   sidebar-reopen chevron (a child of stHeader) disappears too.
   But also DO NOT raise its z-index globally, otherwise it covers
   our fixed top-nav and hides the Run/Prompts/etc. buttons.
   Compromise: collapse the header to 0 height + invisible, and
   selectively un-hide and z-index-bump *only* the controls inside
   it that we actually need (the sidebar chevron). visibility:
   visible on a child overrides visibility: hidden on the parent. */
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
    min-height: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
}
/* Re-show + boost the sidebar collapse/expand chevron specifically.
   Force position:fixed so `top` actually applies (Streamlit's
   natural style on this element is sometimes static — the parent
   stHeader's height:0 + absolute children + Streamlit's negative
   top conspired to clip the chevron's top half). Pinning at
   top:0.75rem; left:0.6rem matches the y-position of the in-
   sidebar chevron when the sidebar is expanded, so the icon
   doesn't seem to "jump" between the two states. */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"] [data-testid*="ollapse"],
header[data-testid="stHeader"] [data-testid*="idebar" i],
header[data-testid="stHeader"] button[kind="header"] {
    visibility: visible !important;
    pointer-events: auto !important;
    z-index: 100001 !important;
    position: fixed !important;
    top: 0.75rem !important;
    left: 0.6rem !important;
    margin: 0 !important;
    transform: none !important;       /* defeat any Streamlit translate */
}

/* Reserve a left gutter in the top-nav when the sidebar is
   collapsed so the chevron at left:0.6rem doesn't visually overlap
   the Run button. When the sidebar is expanded the chevron lives
   inside the sidebar (different DOM node) so no gutter is needed. */
.st-key-praxia_topnav {
    padding-left: 3rem !important;
}
body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-praxia_topnav {
    padding-left: 1rem !important;
}

/* Aggressively hide every other button inside the header — Deploy,
   Settings/dev menu, share, Streamlit's own toolbar buttons —
   without taking out the sidebar chevron. Streamlit shuffles the
   testids between releases, so target by what to KEEP rather than
   what to drop. */
header[data-testid="stHeader"] button:not([kind="header"]):not([data-testid*="ollapse"]):not([data-testid*="idebar" i]),
header[data-testid="stHeader"] [data-testid*="eploy" i],
[data-testid="stDeploymentButton"],
[data-testid="stAppDeployButton"],
button[data-testid*="eploy" i] {
    display: none !important;
}
footer { visibility: hidden !important; height: 0 !important; }

/* Push main content to the very top — no padding above the nav bar. */
.main .block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
section.main, [data-testid="stMain"] { padding-top: 0 !important; }

/* --- Top-bar nav: locked to the viewport top via position: fixed.
   Sticky was unreliable across Streamlit DOM revisions because
   intermediate containers occasionally apply overflow rules that
   break the sticky's scroll context. Fixed is brute-force but
   bullet-proof. The sidebar's higher z-index naturally overlays the
   left edge of our bar, so the user never sees the bar bleed under
   the sidebar even though we span the full viewport width. */
.st-key-praxia_topnav {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 9999 !important;
    background-color: #ffffff;  /* light; dark overrides below */
    padding: 0.5rem 1rem !important;
    margin: 0 !important;
    border-bottom: 1px solid rgba(127, 127, 127, 0.18);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

/* When the sidebar is expanded, push the top-nav left edge to the
   right of it so the leftmost nav button (Run) isn't covered. CSS
   :has() (Chrome 105+ / Safari 15.4+ / Firefox 121+ — universally
   supported in the browsers Streamlit users hit). 21rem is
   Streamlit's default expanded sidebar width; resizable users may
   see a small gap or overlap, the buttons stay reachable either
   way. */
body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-praxia_topnav {
    left: 21rem !important;
}

/* (Sidebar chevron z-index/visibility handling moved below into the
   stHeader block — see further down. Forcing position:fixed + top:0
   + left:0 here was making the chevron appear over the Run button
   when the sidebar was open, which is why this rule got removed.) */

/* Reserve clearance at top + bottom of the main content so the
   fixed top-nav doesn't cover the first item, and the fixed chat
   input doesn't cover the last message. ~3.5rem matches the nav
   height; ~8rem is generous for the chat input + attached files. */
[data-testid="stMain"] [data-testid="stMainBlockContainer"] {
    padding-top: 3.5rem !important;
    padding-bottom: 8rem !important;
}

/* Pin the chat input to the viewport bottom. st.chat_input's
   default behavior is "stick to the bottom of its container," but
   inside a tab it pins to the tab's bottom rather than the
   viewport's. Force viewport-fixed positioning so the user always
   has the input visible. */
[data-testid="stChatInput"],
[data-testid="stBottomBlockContainer"] {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 9000 !important;
    background-color: var(--background-color, #ffffff) !important;
    padding: 0.5rem 1rem !important;
    border-top: 1px solid rgba(127, 127, 127, 0.18);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
}

/* No gaps between buttons + flush button radii so the bar reads as
   one continuous strip. Square corners on the strip ends to match the
   enterprise tone. */
.st-key-praxia_topnav .stButton button {
    border-radius: 0 !important;
    border-right: none !important;
    margin: 0 !important;
}
.st-key-praxia_topnav [data-testid="column"]:first-child .stButton button {
    border-top-left-radius: 3px !important;
    border-bottom-left-radius: 3px !important;
}
.st-key-praxia_topnav [data-testid="column"]:last-child .stButton button {
    border-top-right-radius: 3px !important;
    border-bottom-right-radius: 3px !important;
    border-right: 1px solid rgba(127, 127, 127, 0.18) !important;
}

/* --- Praxia UI mobile / responsive overrides --- */

/* 1. Tablet & phone: tighter padding, scrollable tabs */
@media (max-width: 1024px) {
    .main .block-container {
        padding: 1rem 1rem 6rem 1rem !important;
        max-width: 100% !important;
    }
    [data-testid="stSidebar"] {
        min-width: 240px !important;
        max-width: 280px !important;
    }
}

@media (max-width: 768px) {
    /* Reduce heading sizes */
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.3rem !important; }
    h3 { font-size: 1.1rem !important; }

    /* Tabs: scroll horizontally instead of wrapping awkwardly */
    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        scrollbar-width: thin;
    }
    [data-testid="stTabs"] [role="tab"] {
        white-space: nowrap !important;
        flex-shrink: 0 !important;
        padding: 0.5rem 0.75rem !important;
        font-size: 0.85rem !important;
    }

    /* Sidebar: full-width when expanded; collapsible */
    [data-testid="stSidebar"] {
        min-width: 90% !important;
        max-width: 100% !important;
    }

    /* Buttons: minimum 44px touch target (WCAG AAA) */
    .stButton button {
        min-height: 44px;
        font-size: 0.9rem;
    }

    /* Tables / dataframes: horizontal scroll instead of overflow */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        overflow-x: auto;
    }

    /* Code blocks: smaller font */
    pre, code { font-size: 12px !important; }

    /* Expanders: keep content readable */
    [data-testid="stExpander"] {
        margin-bottom: 0.75rem;
    }

    /* Metric cards: avoid horizontal overflow */
    [data-testid="stMetric"] { padding: 0.5rem 0.75rem; }

    /* Columns: stack on mobile */
    .row-widget.stHorizontal {
        flex-wrap: wrap !important;
    }
}

/* Phones (≤480px): even tighter */
@media (max-width: 480px) {
    h1 { font-size: 1.4rem !important; }
    .main .block-container { padding: 0.75rem !important; }
    .stButton button { width: 100%; }
}

/* Compact mode (user-toggled, regardless of screen size) */
body[data-praxia-compact="true"] .main .block-container {
    padding: 0.75rem 1rem !important;
}
body[data-praxia-compact="true"] h1 { font-size: 1.5rem !important; margin-top: 0.5rem !important; }
body[data-praxia-compact="true"] h2 { font-size: 1.2rem !important; margin-top: 0.5rem !important; }
body[data-praxia-compact="true"] [data-testid="stMetric"] { padding: 0.4rem 0.6rem; }

/* Reduced-motion accessibility */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
</style>
"""


def inject_mobile_css() -> None:
    """Inject responsive CSS into the Streamlit page.

    Call once after `st.set_page_config(...)`.
    """
    try:
        import streamlit as st
    except ImportError:
        return
    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)


def compact_mode_toggle_in_sidebar(label: str = "Compact mode") -> bool:
    """Show a compact-mode checkbox in the sidebar; sync to body data-attr.

    Useful for slow connections + dense layouts.
    """
    try:
        import streamlit as st
    except ImportError:
        return False
    val = st.sidebar.checkbox(label, value=st.session_state.get("praxia_compact", False))
    st.session_state.praxia_compact = val
    # Inject a tiny script to set body data-attr — Streamlit re-injects on every rerun
    state = "true" if val else "false"
    st.markdown(
        f"<script>document.body.setAttribute('data-praxia-compact', '{state}');</script>",
        unsafe_allow_html=True,
    )
    return val


def mobile_friendly_table(data: Any, **kwargs: Any) -> None:
    """`st.dataframe` with sane mobile defaults.

    - `use_container_width=True` so it fills (not overflows) the viewport
    - hide_index by default
    """
    try:
        import streamlit as st
    except ImportError:
        return
    kwargs.setdefault("use_container_width", True)
    kwargs.setdefault("hide_index", True)
    st.dataframe(data, **kwargs)


__all__ = [
    "inject_mobile_css",
    "compact_mode_toggle_in_sidebar",
    "mobile_friendly_table",
]
