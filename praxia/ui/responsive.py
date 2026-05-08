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

/* Calm heading hierarchy — slightly smaller across the board, with
   tightened top/bottom margins so the page header sits close to the
   first content row instead of leaving the browser's default ~0.83em
   gap. */
.stMarkdown h1, h1 { font-size: 1.6rem !important; font-weight: 600 !important; letter-spacing: -0.005em !important; line-height: 1.25 !important; margin: 0.25rem 0 0.5rem 0 !important; padding: 0 !important; }
.stMarkdown h2, h2 { font-size: 1.3rem !important; font-weight: 600 !important; letter-spacing: -0.003em !important; line-height: 1.3 !important; margin: 0.5rem 0 0.4rem 0 !important; padding: 0 !important; }
.stMarkdown h3, h3 { font-size: 1.1rem !important; font-weight: 600 !important; margin: 0.5rem 0 0.35rem 0 !important; padding: 0 !important; }
.stMarkdown h4, h4 { font-size: 1rem !important; font-weight: 600 !important; margin: 0.4rem 0 0.3rem 0 !important; padding: 0 !important; }
/* Streamlit wraps headings in [data-testid="stHeading"] which has its
   own padding-bottom — zero it out so our margin rules above are the
   single source of truth for vertical rhythm under a heading. */
[data-testid="stHeading"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    margin-bottom: 0 !important;
}
/* The very first heading on each page (right after the fixed topnav)
   shouldn't have a top margin — the topnav clearance padding already
   gives enough breathing room. */
[data-testid="stMainBlockContainer"] [data-testid="stHeading"]:first-child h1,
[data-testid="stMainBlockContainer"] [data-testid="stHeading"]:first-child h2,
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child h1,
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child h2 {
    margin-top: 0 !important;
}

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
       These are dev-time conveniences — Praxia is the product, not Streamlit.

       NOTE: stToolbar uses `visibility: hidden`, not `display: none`. The
       sidebar reopen chevron is rendered as a descendant of either stToolbar
       or stHeader depending on Streamlit version, and `visibility: visible`
       on a descendant CAN override `visibility: hidden` on an ancestor — but
       it CANNOT override `display: none` on an ancestor. Using display:none
       here would make the chevron unreachable when the sidebar is collapsed.
       The chevron's explicit re-show rule lives further down. */
[data-testid="stToolbar"] {
    visibility: hidden !important;
    height: 0 !important;
    position: fixed !important;
}
/* The "Running... STOP" indicator that pops over the top-nav during a
   rerun. Unlike stToolbar this has no children we want to keep visible,
   so we can safely use `display: none` to prevent any leak-through. */
[data-testid="stStatusWidget"],
[data-testid="stAppRunningIcon"],
[data-testid="stAppRunningMan"],
[class*="StatusWidget"],
[class*="RunningMan"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
}
[data-testid="stDecoration"] { display: none !important; }
.stDeployButton { display: none !important; }
#MainMenu { visibility: hidden !important; height: 0 !important; }
/* The sidebar is permanently expanded — no collapse / reopen chevron.
   Hide the entire stHeader (which holds the chevron, the deploy button,
   and the dev menu) outright. The sidebar still has its own internal
   navigation; the user just can't shrink it to a 0-width strip. This
   is much simpler than trying to keep the chevron visible in some DOM
   states and not others, and it lets the topnav assume a fixed left
   offset of 21rem at all times. */
header[data-testid="stHeader"] {
    display: none !important;
}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[data-testid*="ollapse" i],
button[data-testid*="idebarCollapse" i] {
    display: none !important;
}
/* Belt-and-suspenders: prevent Streamlit from EVER rendering the
   sidebar at width 0, AND tighten its width to 15rem so the main
   content has more room — Streamlit's default 21rem leaves a lot of
   wasted whitespace below the sidebar widgets. */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
    transform: none !important;
    visibility: visible !important;
    min-width: 15rem !important;
    max-width: 15rem !important;
    width: 15rem !important;
}
[data-testid="stSidebar"][aria-expanded="false"] {
    transform: none !important;
    visibility: visible !important;
    margin-left: 0 !important;
}

/* Reserve a small left gutter in the topnav for breathing room. */
.st-key-praxia_topnav {
    padding-left: 1rem !important;
}

/* Aggressively hide leftover Deploy / dev menu chrome that sometimes
   renders outside the (now-hidden) stHeader. */
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

/* --- Top-bar nav: locked to the viewport top via position: fixed,
   permanently offset by 15rem on the left to match the (now narrower)
   always-visible sidebar. The sidebar can no longer be collapsed
   (chevron is hidden, initial_sidebar_state="expanded" + width: 15rem
   on stSidebar), so we don't need :has() to swap left.
   Sticky was unreliable across Streamlit DOM revisions because
   intermediate containers occasionally apply overflow rules that
   break the sticky's scroll context. Fixed is brute-force but
   bullet-proof. */
.st-key-praxia_topnav {
    position: fixed !important;
    top: 0 !important;
    left: 15rem !important;
    right: 0 !important;
    /* CRITICAL: width: auto with both left + right set lets the browser
       compute width = viewport - left - right = 100vw - 15rem. WITHOUT
       this override, st.container(width="stretch") emits `width: 100%`
       which under position:fixed resolves to 100vw — that pushes the
       row 15rem off the right edge and hides Admin behind the viewport. */
    width: auto !important;
    max-width: none !important;
    z-index: 9999 !important;
    background-color: #ffffff;  /* light; dark overrides below */
    padding: 0.5rem 0.5rem !important;
    margin: 0 !important;
    border-bottom: 1px solid rgba(127, 127, 127, 0.18);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

/* Reserve clearance at top + bottom of the main content so the
   fixed top-nav doesn't cover the first item, and the fixed chat
   input doesn't cover the last message. 2.75rem is just enough to
   clear the nav (the buttons are ~2rem tall + 0.5rem padding); ~8rem
   is generous for the chat input + attached files. */
[data-testid="stMain"] [data-testid="stMainBlockContainer"] {
    padding-top: 2.75rem !important;
    padding-bottom: 8rem !important;
}
/* Tighten the gap that Streamlit's stVerticalBlock leaves between
   the page header and its first content row. The default is ~1rem
   per child gap, which compounds with the heading margin and looks
   like wasted whitespace below the page title. */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
    gap: 0.5rem !important;
}

/* Pin the chat input to the viewport bottom, offset to the right of
   the always-visible 15rem sidebar so it doesn't slide underneath it.
   Streamlit's default "stick to container bottom" behavior pins it to
   the active tab/container, not the viewport, which means the input
   would scroll off-screen during long conversations.

   NOTE: no background-color set here. Letting Streamlit's own theme
   provide the bar's background means light mode stays light and the
   user-picked dark theme block in app.py handles the dark case. An
   earlier attempt set `prefers-color-scheme: dark` here, which
   forced the bar dark whenever the OS was dark — even when the user
   had explicitly chosen the light theme — producing a dark outer
   ring around a still-white inner chat input that read as a "thick
   black border". */
[data-testid="stChatInput"],
[data-testid="stBottomBlockContainer"] {
    position: fixed !important;
    bottom: 0 !important;
    left: 15rem !important;
    right: 0 !important;
    z-index: 9000 !important;
    padding: 0.5rem 1rem !important;
    border-top: 1px solid rgba(127, 127, 127, 0.18);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
}

/* The topnav itself is a horizontal flex container (st.container with
   horizontal=True). Each st.button() inside is wrapped by Streamlit
   in an stElementContainer div, so the flex children of the topnav
   are 7 (or 6 for non-admins) stElementContainer divs, each holding
   one .stButton > button.

   Force EVERY direct child of the topnav to flex: 1 1 0; min-width: 0
   regardless of what testid / class it has — this is the only way to
   reliably catch whatever wrapper element Streamlit emits across DOM
   revisions. min-width: 0 is critical: without it flex items refuse
   to shrink below their content's intrinsic width, which was making
   the rightmost button (Admin) overflow before. */
.st-key-praxia_topnav {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 0 !important;
    column-gap: 0 !important;
    overflow: hidden !important;
}
.st-key-praxia_topnav > * {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    width: auto !important;
    max-width: none !important;
    margin: 0 !important;
}
.st-key-praxia_topnav .stButton {
    width: 100% !important;
    min-width: 0 !important;
    margin: 0 !important;
}
.st-key-praxia_topnav .stButton button {
    width: 100% !important;
    min-width: 0 !important;
    padding-left: 0.3rem !important;
    padding-right: 0.3rem !important;
    font-size: 0.85rem !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    border-radius: 0 !important;
    border-right: none !important;
    margin: 0 !important;
}
.st-key-praxia_topnav > *:first-child .stButton button {
    border-top-left-radius: 3px !important;
    border-bottom-left-radius: 3px !important;
}
.st-key-praxia_topnav > *:last-child .stButton button {
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
