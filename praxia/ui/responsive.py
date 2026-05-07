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
/* --- Praxia UI: hide Streamlit's default chrome that's irrelevant to the
       app user (Deploy button, hamburger menu, "Made with Streamlit" footer).
       These are dev-time conveniences — Praxia is the product, not Streamlit. */
[data-testid="stToolbar"] { visibility: hidden !important; height: 0 !important; position: fixed !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { visibility: hidden !important; height: 0 !important; position: fixed !important; }
.stDeployButton { display: none !important; }
#MainMenu { visibility: hidden !important; height: 0 !important; }
header[data-testid="stHeader"] { display: none !important; height: 0 !important; }
footer { visibility: hidden !important; height: 0 !important; }

/* Push the main content to the very top now that we hid the header. */
.main .block-container {
    padding-top: 0 !important;
}

/* --- Top-bar nav: a sticky solid bar using native st.button widgets.
       The trick: wrap the columns row in #praxia-topnav-wrapper so we
       can target the immediate next sibling — the columns row — and
       make IT sticky with a solid background. */
#praxia-topnav-wrapper { display: none; }
#praxia-topnav-wrapper + div[data-testid="stHorizontalBlock"] {
    position: sticky;
    top: 0;
    z-index: 999;
    background-color: #ffffff;  /* light fallback; dark overrides below */
    padding: 0.5rem 1rem !important;
    margin: 0 -1rem 1rem -1rem !important;
    border-bottom: 1px solid rgba(127, 127, 127, 0.18);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
/* No gaps between buttons in the top nav */
#praxia-topnav-wrapper + div[data-testid="stHorizontalBlock"] [data-testid="column"] {
    gap: 0 !important;
    padding: 0 !important;
}
#praxia-topnav-wrapper + div[data-testid="stHorizontalBlock"] .stButton button {
    border-radius: 0 !important;
    border-right: none !important;
    margin: 0 !important;
}
#praxia-topnav-wrapper + div[data-testid="stHorizontalBlock"] [data-testid="column"]:first-child .stButton button {
    border-top-left-radius: 6px !important;
    border-bottom-left-radius: 6px !important;
}
#praxia-topnav-wrapper + div[data-testid="stHorizontalBlock"] [data-testid="column"]:last-child .stButton button {
    border-top-right-radius: 6px !important;
    border-bottom-right-radius: 6px !important;
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
