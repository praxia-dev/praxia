"""Default Streamlit UI for Praxia.

Layout:

    1. Login   — username only (single-user dev OR auth-store username).
                 No API-key field — for real auth, run `praxia serve`.
    2. Top bar — horizontal navigation: Run / Memory / Prompts / Data /
                 Stats / (Consolidate, Admin if admin role)
    3. Sidebar — Active data scopes (always visible). The primary
                 sidebar role: pick which folders / memory layers to
                 feed into the current run. Plus brand · user · sign-out.
    4. Main    — workspace for the selected nav view.

Per-user preferences (language, color theme, default LLM model) are
persisted to .praxia/preferences/<user_id>.json, so they survive
browser reloads / new sessions.

Run is the high-frequency view (Skill + Agent sub-tabs). Workflows are
still available via SDK / CLI but aren't a top-level UI item — most
users invoke workflows via the autonomous Agent or via direct Skill
calls. This keeps the UI focused on the two paths users actually use
day-to-day.
"""
from __future__ import annotations

import base64
import json
import os
import re as _re
from pathlib import Path
from typing import Any

import streamlit as st

from praxia import Praxia, LLM
from praxia.core.llm import DEFAULT_ALIASES, LLM_PROVIDERS, provider_for_model
from praxia.data.scopes import DataScope, ScopeRegistry
from praxia.data.threads import ChatMessage, ChatThread, ThreadStore
from praxia.flows import LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow
from praxia.skills import BUSINESS_SKILLS
from praxia.ui.i18n import t, detect_language, SUPPORTED, LANG_DISPLAY
from praxia.ui.responsive import inject_mobile_css

st.set_page_config(page_title="Praxia", page_icon="🪡", layout="wide")
inject_mobile_css()


# =====================================================================
# Hydrate os.environ from .env + .praxia/config.toml so third-party
# libraries (LiteLLM, OpenAI SDK, Mem0, etc.) actually see API keys
# saved via Admin → Settings. PraxiaConfig.get() reads env first then
# falls back to TOML; we mirror the TOML values into env so libraries
# that read os.environ directly (LiteLLM does) can find them. Real
# env vars set in the shell are never overwritten — only missing
# slots get filled.
# =====================================================================
try:
    from praxia.config import KNOWN_KEYS as _KNOWN_KEYS
    from praxia.config import PraxiaConfig as _PraxiaConfig
    _PraxiaConfig.load_dotenv()
    for _ck in _KNOWN_KEYS:
        if _ck not in os.environ:
            _cv = _PraxiaConfig.get(_ck)
            if _cv:
                os.environ[_ck] = _cv

    # Some LLM providers (notably Azure OpenAI via LiteLLM → openai
    # SDK) read *different* env-var names than what we expose in
    # KNOWN_KEYS. The openai SDK strictly requires
    #   AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT / OPENAI_API_VERSION
    # whereas LiteLLM's docs use AZURE_API_KEY / AZURE_API_BASE /
    # AZURE_API_VERSION. Mirror them so the user only configures one
    # set in the UI and either path resolves.
    _ENV_MIRRORS = {
        "AZURE_API_KEY":     "AZURE_OPENAI_API_KEY",
        "AZURE_API_BASE":    "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_VERSION": "OPENAI_API_VERSION",
    }
    for _src, _dst in _ENV_MIRRORS.items():
        if os.environ.get(_src) and not os.environ.get(_dst):
            os.environ[_dst] = os.environ[_src]
except Exception:
    pass

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False


# =====================================================================
# Per-user persistent preferences (.praxia/preferences/<user>.json)
# =====================================================================

_PREFS_DIR = Path(".praxia") / "preferences"


def _scrub_secrets(text: str) -> str:
    """Mask anything in ``text`` that looks like a leaked API key.

    Third-party error messages (OpenAI / Anthropic / etc.) sometimes
    echo back partial key material — e.g. OpenAI's
    ``Incorrect API key provided: 50b65c14********************e652``.
    Scrub before showing to the end user so we don't accidentally surface
    a fragment that helps attackers confirm a stolen key.
    """
    if not text:
        return text
    out = text
    # 1) Partial-mask patterns: <chars>****<chars>, <chars>……<chars>, etc.
    out = _re.sub(
        r"[A-Za-z0-9_\-]{4,}[\*…\.]{3,}[A-Za-z0-9_\-]{4,}", "****", out,
    )
    # 2) Raw OpenAI-style keys (sk-...)
    out = _re.sub(r"\bsk-[A-Za-z0-9_\-]{20,}\b", "sk-****", out)
    # 3) Raw Anthropic-style (sk-ant-...)
    out = _re.sub(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b", "sk-ant-****", out)
    # 4) Generic 32+ char hex tokens (often raw keys)
    out = _re.sub(r"\b[A-Fa-f0-9]{32,}\b", "****", out)
    return out


def _prefs_path(user_id: str) -> Path:
    return _PREFS_DIR / f"{user_id}.json"


def _load_user_prefs(user_id: str) -> dict[str, Any]:
    p = _prefs_path(user_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_user_pref(user_id: str, key: str, value: Any) -> None:
    """Persist a single preference key. Creates the file if needed."""
    prefs = _load_user_prefs(user_id)
    prefs[key] = value
    p = _prefs_path(user_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# =====================================================================
# Persistent login (server-side session + browser cookie)
# =====================================================================
#
# Streamlit's `st.session_state` lives in memory and dies on every page
# reload (the WebSocket closes). We mint an opaque random token at
# login, hand it to the browser as a cookie, and store the actual
# user_id / org_id / role on disk under `.praxia/sessions/<token>.json`
# with a 30-minute TTL. On every rerun we read the cookie back via
# `st.context.cookies` and rehydrate `st.session_state` if the token
# resolves to a live session — survives refreshes, doesn't survive
# cookie expiry / explicit signout / server purge.

from praxia.auth.sessions import SessionStore as _SessionStore

_SESSION_COOKIE_NAME = "praxia_session"
_SESSION_TTL_SECONDS = 30 * 60  # 30 min sliding window

_session_store = _SessionStore(
    Path(".praxia") / "sessions",
    ttl_seconds=_SESSION_TTL_SECONDS,
)


def _read_session_cookie() -> str | None:
    """Best-effort read of the praxia_session cookie."""
    try:
        cookies = getattr(st.context, "cookies", None) or {}
        token = cookies.get(_SESSION_COOKIE_NAME)
    except Exception:
        token = None
    return token if isinstance(token, str) and token else None


def _write_session_cookie(token: str) -> None:
    """Set the cookie via a same-origin srcdoc iframe so the `<script>`
    actually runs.

    `st.markdown(unsafe_allow_html=True)` inserts HTML via innerHTML,
    and per HTML spec **`<script>` tags inserted via innerHTML never
    execute** — the browser doesn't run them. We instead use
    `components.v1.html()`, which spawns a `srcdoc` iframe that the
    browser parses normally. The iframe inherits the parent's origin
    (per the HTML spec), so writing to `window.parent.document.cookie`
    sets a cookie on Streamlit's main page origin."""
    safe_token = "".join(c for c in token if c in "0123456789abcdef")
    if not safe_token:
        return
    import streamlit.components.v1 as components
    js = f"""
    <script>
    (function() {{
        try {{
            var p = '{_SESSION_COOKIE_NAME}={safe_token};path=/;max-age={_SESSION_TTL_SECONDS};samesite=lax';
            if (location.protocol === 'https:') p += ';secure';
            // Set cookie on the parent document (Streamlit main page).
            // Same-origin srcdoc lets us reach window.parent.
            try {{ window.parent.document.cookie = p; }} catch(e) {{}}
            // Also set on the iframe doc as a belt-and-suspenders.
            try {{ document.cookie = p; }} catch(e) {{}}
        }} catch(e) {{ console.error('praxia: cookie set failed', e); }}
    }})();
    </script>
    """
    components.html(js, height=0, width=0)


def _clear_session_cookie() -> None:
    """Drop the cookie client-side via the same iframe trick as the
    write path. Server-side record is removed separately via
    `_session_store.delete(token)`."""
    import streamlit.components.v1 as components
    js = f"""
    <script>
    (function() {{
        try {{
            var p = '{_SESSION_COOKIE_NAME}=;path=/;max-age=0;samesite=lax';
            try {{ window.parent.document.cookie = p; }} catch(e) {{}}
            try {{ document.cookie = p; }} catch(e) {{}}
        }} catch(e) {{ console.error('praxia: cookie clear failed', e); }}
    }})();
    </script>
    """
    components.html(js, height=0, width=0)


def _restore_session_from_cookie() -> bool:
    """If a valid session cookie exists, rehydrate session_state.
    Returns True if a session was restored. Idempotent — safe to call
    on every rerun."""
    if st.session_state.get("logged_in"):
        return True  # already hydrated this WebSocket
    token = _read_session_cookie()
    if not token:
        return False
    rec = _session_store.touch(token)  # extends TTL on activity
    if rec is None:
        return False
    st.session_state["logged_in"] = True
    st.session_state["user_id"] = rec.user_id
    st.session_state["org_id"] = rec.org_id or "default-org"
    st.session_state["actor_role"] = rec.role or "unknown"
    st.session_state["_praxia_session_token"] = token
    # Re-load persisted user prefs (lang, theme) for this rehydrated user
    for k, v in _load_user_prefs(rec.user_id).items():
        if k not in st.session_state:
            st.session_state[k] = v
    return True


def _ensure_session_cookie() -> None:
    """Re-emit the cookie-set <script> on every render so the JS actually
    ships to the browser. (st.rerun() *discards* anything queued during
    the current run, so writing the cookie inline at login + rerunning
    means the JS never reaches the browser. We instead store the token
    in session_state at login and let this function paint the cookie on
    the post-rerun render.)"""
    token = st.session_state.get("_praxia_session_token")
    if token:
        _write_session_cookie(token)


# Best-effort housekeeping — run once per process start.
if not st.session_state.get("_session_purge_done"):
    try:
        _session_store.purge_expired()
    except Exception:
        pass
    st.session_state["_session_purge_done"] = True


# =====================================================================
# Login gate
# =====================================================================

def _build_sso_provider():
    """Return an SSO provider instance if env vars are configured, else None."""
    if not os.getenv("PRAXIA_SSO_PROVIDER"):
        return None
    try:
        from praxia.auth.sso import provider_from_env
        return provider_from_env("PRAXIA_SSO")
    except Exception:
        return None


def _render_login() -> None:
    st.markdown(
        "<div style='max-width:480px; margin:6vh auto 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(f"# {t('app.title')}")
    st.caption(t("app.tagline"))
    st.write("")

    # Detect auth-store state: if any users exist, an API key is required
    # because there's nothing else stopping a non-admin from typing 'alice'
    # and being treated as alice.
    users_exist = False
    try:
        from praxia.auth import AuthManager
        _probe_auth = AuthManager()
        users_exist = bool(_probe_auth.users.list_all())
    except Exception:
        pass

    # ---- SSO button ----
    # If PRAXIA_SSO_PROVIDER (+ client id/secret/redirect) is set, mint a
    # PKCE state, persist verifier to disk so the callback can recover it
    # after the IdP redirect, and present a "Sign in with <provider>" CTA
    # above the API-key form. The form below remains for service accounts
    # / CLI-issued keys.
    _sso = _build_sso_provider()
    if _sso is not None:
        from praxia.auth.sso_state import SSOPendingStore
        import secrets as _sec
        _sso_store = SSOPendingStore(Path(".praxia") / "sso_pending")
        _sso_store.purge_expired()
        _provider_label = (_sso.config.provider_name or "SSO").title()
        if st.button(
            t("login.sso_button").format(provider=_provider_label),
            type="primary",
            use_container_width=True,
            key="login_sso_btn",
        ):
            try:
                _state = _sec.token_urlsafe(24)
                _auth_url = _sso.authorization_url(state=_state)
                # The provider stashes the verifier in its in-memory dict
                # — pull it out and put it on disk so the callback (which
                # may run in a fresh process) can recover.
                _verifier = _sso._pkce_store.pop(_state, "")
                if _verifier:
                    _sso_store.put(
                        _state, _verifier,
                        _sso.config.redirect_uri,
                        _sso.config.provider_name,
                    )
                # Streamlit doesn't expose a server-side redirect, so
                # bounce via meta-refresh (works without JS execution).
                st.markdown(
                    f"<meta http-equiv='refresh' content='0; url={_auth_url}'>",
                    unsafe_allow_html=True,
                )
                st.info(t("login.sso_redirecting"))
                st.stop()
            except Exception as e:
                st.error(t("login.sso_failed").format(error=str(e)))
        st.markdown(
            "<div style='text-align:center; margin:0.6rem 0; opacity:0.6;'>"
            f"— {t('login.sso_or')} —"
            "</div>",
            unsafe_allow_html=True,
        )

    if users_exist:
        st.info(t("login.users_exist_hint"))
    else:
        st.warning(t("login.dev_mode_hint"))

    with st.form("praxia_login", clear_on_submit=False):
        user_id_input = st.text_input(
            t("login.user_id"),
            value=os.getenv("PRAXIA_USER_ID", ""),
            placeholder="alice",
            help=t("login.user_id_help"),
        )
        api_key_input = st.text_input(
            t("login.api_key"),
            type="password",
            placeholder=t("login.api_key_placeholder"),
            help=t("login.api_key_help"),
        )
        with st.expander(t("login.advanced"), expanded=False):
            org_id_input = st.text_input(
                t("login.org_id"), value="default-org",
            )
        submit = st.form_submit_button(
            t("login.submit"), type="primary", use_container_width=True,
        )

        if submit:
            uid = user_id_input.strip()
            api_key = api_key_input.strip()

            # Resolve identity. Priority:
            #   1. If API key provided → must validate. The username we
            #      trust is the one returned by auth, NOT the text input.
            #   2. If no API key but users exist → reject (auth required).
            #   3. If no API key and no users exist → single-user dev mode,
            #      allow whatever username they typed.
            if api_key:
                try:
                    from praxia.auth import AuthManager
                    _auth = AuthManager()
                    u = _auth.authenticate(api_key=api_key)
                    if u is None:
                        st.error(t("login.invalid_key"))
                        st.markdown("</div>", unsafe_allow_html=True)
                        return
                    resolved_user = u.username
                    resolved_role = u.role
                except Exception as e:
                    st.error(f"Auth check failed: {e}")
                    st.markdown("</div>", unsafe_allow_html=True)
                    return
            elif users_exist:
                # Auth store has users but caller didn't provide a key.
                # Refuse — typing a username alone is not authentication.
                st.error(t("login.api_key_required"))
                st.markdown("</div>", unsafe_allow_html=True)
                return
            else:
                # No users registered → single-user dev mode.
                if not uid:
                    st.error(t("login.user_id_required"))
                    st.markdown("</div>", unsafe_allow_html=True)
                    return
                resolved_user = uid
                resolved_role = "unknown"

            st.session_state["logged_in"] = True
            st.session_state["user_id"] = resolved_user
            st.session_state["org_id"] = (
                org_id_input.strip() or "default-org"
            )
            st.session_state["actor_role"] = resolved_role

            for k, v in _load_user_prefs(resolved_user).items():
                if k not in st.session_state:
                    st.session_state[k] = v

            # Mint a server-side session token. The cookie itself is
            # written by `_ensure_session_cookie()` *after* the rerun —
            # writing it here inline would be discarded by `st.rerun()`.
            try:
                _new_token = _session_store.create(
                    user_id=resolved_user,
                    org_id=st.session_state["org_id"],
                    role=resolved_role,
                )
                st.session_state["_praxia_session_token"] = _new_token
            except Exception:
                # If session minting fails, login still works — just no
                # cross-reload persistence on this turn.
                pass

            st.rerun()

    st.write("")
    st.caption(t("login.security_note"))
    st.markdown("</div>", unsafe_allow_html=True)


def _handle_sso_callback() -> bool:
    """If the URL has ?code=... &state=... query params and a matching
    pending PKCE record exists, complete the SSO exchange and log the
    user in. Returns True iff a session was created."""
    try:
        params = st.query_params  # Streamlit 1.30+
    except Exception:
        return False
    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        return False
    # Streamlit returns lists for some query-param values; flatten.
    if isinstance(code, list):
        code = code[0] if code else ""
    if isinstance(state, list):
        state = state[0] if state else ""
    if not code or not state:
        return False
    try:
        from praxia.auth.sso_state import SSOPendingStore
        from praxia.auth import AuthManager
        _sso = _build_sso_provider()
        if _sso is None:
            return False
        _store = SSOPendingStore(Path(".praxia") / "sso_pending")
        rec = _store.consume(state)
        if rec is None:
            st.error(t("login.sso_invalid_state"))
            return False
        # Re-prime the provider's PKCE dict so exchange_code finds the
        # verifier (it pops it back out internally).
        _sso._pkce_store[state] = rec.verifier
        info = _sso.exchange_code(code, state=state)
        if not info.email:
            st.error(t("login.sso_no_email"))
            return False
        _auth = AuthManager()
        _auth.attach_sso(_sso)
        user = _auth.upsert_sso_user(info, provider_name=_sso.config.provider_name)

        # Populate session_state — same shape as the API-key path.
        st.session_state["logged_in"] = True
        st.session_state["user_id"] = user.username
        st.session_state["org_id"] = "default-org"
        st.session_state["actor_role"] = user.role
        for k, v in _load_user_prefs(user.username).items():
            if k not in st.session_state:
                st.session_state[k] = v
        try:
            _new_token = _session_store.create(
                user_id=user.username,
                org_id=st.session_state["org_id"],
                role=user.role,
            )
            st.session_state["_praxia_session_token"] = _new_token
        except Exception:
            pass
        # Drop the OAuth params from the URL so a refresh doesn't try to
        # re-exchange the (now consumed) code.
        try:
            st.query_params.clear()
        except Exception:
            pass
        return True
    except Exception as exc:
        st.error(t("login.sso_callback_failed").format(error=str(exc)))
        return False


if not st.session_state.get("logged_in"):
    # 1) IdP redirect with ?code=...&state=... → finish SSO login.
    # 2) Browser cookie from a previous session → rehydrate.
    # 3) Otherwise show the login form.
    if not _handle_sso_callback() and not _restore_session_from_cookie():
        _render_login()
        st.stop()

# Re-emit the session cookie on every authenticated render. Has to be
# here (not inside _render_login before st.rerun) — st.rerun() discards
# the current run's output, so an inline cookie write at login never
# reaches the browser.
_ensure_session_cookie()


user_id: str = st.session_state["user_id"]
org_id: str = st.session_state.get("org_id", "default-org")
actor_role: str = st.session_state.get("actor_role", "unknown")


# =====================================================================
# Theme injection (per-user color theme)
# =====================================================================

theme_choice = st.session_state.get("praxia_theme", "auto")
if theme_choice == "dark":
    st.markdown(
        """
<style>
  :root {
    --background-color: #0a0a0f;
    --secondary-background-color: #15171f;
    --text-color: #ecedf0;
  }
  .stApp { background-color: #0a0a0f !important; color: #ecedf0 !important; }
  [data-testid="stSidebar"] { background-color: #15171f !important; }
  [data-testid="stHeader"] { background-color: transparent !important; }

  /* Generic text */
  .stMarkdown, .stText, p, span, label, h1, h2, h3, h4, h5, h6 { color: #ecedf0 !important; }
  [data-testid="stCaption"], small { color: #a8acb8 !important; }
  code { background-color: rgba(255,255,255,0.08) !important; color: #e9c378 !important; }

  /* Inputs */
  [data-testid="stTextInput"] input,
  [data-testid="stTextArea"] textarea,
  [data-testid="stSelectbox"] div[role="combobox"],
  [data-testid="stNumberInput"] input,
  [data-testid="stDateInput"] input {
    background-color: #1a1d28 !important; color: #ecedf0 !important;
    border-color: rgba(255,255,255,0.1) !important;
  }
  [data-testid="stTextInput"] input::placeholder,
  [data-testid="stTextArea"] textarea::placeholder { color: #6c7080 !important; }

  /* Buttons — readable contrast on dark bg */
  .stButton button,
  .stDownloadButton button,
  [data-testid="stFormSubmitButton"] button {
    background-color: #1a1d28 !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  .stButton button:hover,
  .stDownloadButton button:hover,
  [data-testid="stFormSubmitButton"] button:hover {
    background-color: #252834 !important;
    border-color: rgba(255,255,255,0.2) !important;
  }
  /* Primary action — restrained navy on dark, white text. */
  .stButton button[kind="primary"],
  .stDownloadButton button[kind="primary"],
  [data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: #1e3a8a !important;
    color: #ffffff !important;
    border-color: #1e3a8a !important;
    font-weight: 600 !important;
  }
  .stButton button[kind="primary"]:hover,
  .stDownloadButton button[kind="primary"]:hover,
  [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background-color: #2547a8 !important;
    color: #ffffff !important;
  }
  /* Secondary buttons */
  .stButton button[kind="secondary"],
  .stDownloadButton button[kind="secondary"] {
    background-color: rgba(255,255,255,0.05) !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
  }
  .stButton button[kind="secondary"]:hover,
  .stDownloadButton button[kind="secondary"]:hover {
    background-color: rgba(255,255,255,0.1) !important;
  }

  /* Containers / structure */
  [data-testid="stExpander"] { background-color: rgba(255,255,255,0.02) !important; border-color: rgba(255,255,255,0.06) !important; }
  [data-testid="stTabs"] [data-testid="stMarkdownContainer"] { color: #ecedf0 !important; }
  [data-testid="stTabs"] button[role="tab"] { color: #a8acb8 !important; }
  [data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: #93c5fd !important; border-color: #93c5fd !important; }
  [data-testid="stForm"] { background-color: rgba(255,255,255,0.02) !important; border: 1px solid rgba(255,255,255,0.06) !important; }
  [data-testid="stMetric"] { background-color: rgba(255,255,255,0.03) !important; padding: 0.5rem; border-radius: 6px; }
  hr { border-color: rgba(255,255,255,0.08) !important; }

  /* Alerts */
  [data-testid="stAlert"] { background-color: rgba(255,255,255,0.04) !important; }

  /* Sticky top nav — solid dark bg with subtle navy underline */
  .st-key-praxia_topnav {
    background-color: #15171f !important;
    border-bottom: 1px solid rgba(147,197,253,0.22) !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35) !important;
  }

  /* File uploader — dropzone background + instruction text + size limit
     ("Limit 200MB per file") all default to white-on-white otherwise. */
  [data-testid="stFileUploader"],
  [data-testid="stFileUploader"] section,
  [data-testid="stFileUploaderDropzone"] {
    background-color: #1a1d28 !important;
    border: 1px dashed rgba(255,255,255,0.18) !important;
    color: #ecedf0 !important;
  }
  [data-testid="stFileUploader"] label,
  [data-testid="stFileUploader"] span,
  [data-testid="stFileUploader"] p,
  [data-testid="stFileUploader"] div,
  [data-testid="stFileUploaderDropzoneInstructions"],
  [data-testid="stFileUploaderDropzoneInstructions"] * {
    color: #ecedf0 !important;
  }
  [data-testid="stFileUploader"] small,
  [data-testid="stFileUploaderDropzoneInstructions"] small {
    color: #a8acb8 !important;
  }
  [data-testid="stFileUploader"] button {
    background-color: rgba(255,255,255,0.08) !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
  }
  [data-testid="stFileUploader"] button:hover {
    background-color: rgba(255,255,255,0.14) !important;
  }
  /* Already-uploaded file rows + their X-remove icons */
  [data-testid="stFileUploaderFile"],
  [data-testid="stFileUploaderFileName"],
  [data-testid="stFileUploaderDeleteBtn"] {
    color: #ecedf0 !important;
  }

  /* Chat-input file uploader (📎 attach in st.chat_input) — separate
     DOM tree from stFileUploader, so the rules above don't reach it.
     "Upload or drag and drop files (PNG, JPG, GIF, WEBP)" text was
     rendering white-on-white in dark mode. */
  [data-testid="stChatInput"],
  [data-testid="stChatInputContainer"],
  [data-testid="stChatInputFileUploadDropzone"],
  [data-testid="stChatInputFileUploadDropzoneInstructions"] {
    background-color: #1a1d28 !important;
    color: #ecedf0 !important;
    border-color: rgba(255,255,255,0.12) !important;
  }
  [data-testid="stChatInput"] *,
  [data-testid="stChatInputFileUploadDropzone"] *,
  [data-testid="stChatInputFileUploadDropzoneInstructions"] * {
    color: #ecedf0 !important;
  }
  [data-testid="stChatInput"] small,
  [data-testid="stChatInputFileUploadDropzoneInstructions"] small {
    color: #a8acb8 !important;
  }
  /* The 📎 / send buttons */
  [data-testid="stChatInputFileUploadButton"],
  [data-testid="stChatInputSubmitButton"],
  [data-testid="stChatInput"] button {
    background-color: rgba(255,255,255,0.06) !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  [data-testid="stChatInputFileUploadButton"]:hover,
  [data-testid="stChatInputSubmitButton"]:hover,
  [data-testid="stChatInput"] button:hover {
    background-color: rgba(255,255,255,0.12) !important;
  }
  /* Already-attached file pill in the chat input */
  [data-testid="stChatInputFile"],
  [data-testid="stChatInputFileName"],
  [data-testid="stChatInputDeleteBtn"] {
    color: #ecedf0 !important;
    background-color: rgba(147,197,253,0.12) !important;
  }
  /* Chat input textarea itself */
  [data-testid="stChatInput"] textarea,
  [data-testid="stChatInputTextArea"] {
    background-color: #0f111a !important;
    color: #ecedf0 !important;
    border-color: rgba(255,255,255,0.1) !important;
  }
  [data-testid="stChatInput"] textarea::placeholder {
    color: #6c7080 !important;
  }

  /* Popover trigger ("会話履歴 (N)" button) — Streamlit's popover button
     uses a different DOM than .stButton, so override explicitly. */
  [data-testid="stPopover"] > div > button,
  [data-testid="stPopover"] button,
  button[data-testid="stPopoverButton"] {
    background-color: #1a1d28 !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  [data-testid="stPopover"] > div > button:hover,
  [data-testid="stPopover"] button:hover,
  button[data-testid="stPopoverButton"]:hover {
    background-color: #252834 !important;
    border-color: rgba(255,255,255,0.2) !important;
  }

  /* Popover panel — rendered in a BaseWeb portal at <body> level, so
     none of our `.stApp` rules cascade. Target the BaseWeb attribute
     directly. */
  [data-baseweb="popover"],
  [data-baseweb="popover"] > div,
  [data-testid="stPopoverBody"] {
    background-color: #15171f !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5) !important;
  }
  [data-baseweb="popover"] *,
  [data-testid="stPopoverBody"] * {
    color: #ecedf0 !important;
  }
  [data-baseweb="popover"] [data-testid="stCaption"],
  [data-baseweb="popover"] small,
  [data-testid="stPopoverBody"] small {
    color: #a8acb8 !important;
  }
  /* Buttons inside the popover */
  [data-baseweb="popover"] button,
  [data-testid="stPopoverBody"] button {
    background-color: #1a1d28 !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  [data-baseweb="popover"] button[kind="primary"],
  [data-testid="stPopoverBody"] button[kind="primary"] {
    background-color: #1e3a8a !important;
    color: #ffffff !important;
    border-color: #1e3a8a !important;
  }
  [data-baseweb="popover"] button:hover,
  [data-testid="stPopoverBody"] button:hover {
    background-color: #252834 !important;
  }
  /* Text inputs inside the popover (rename field) */
  [data-baseweb="popover"] input,
  [data-testid="stPopoverBody"] input {
    background-color: #0f111a !important;
    color: #ecedf0 !important;
    border-color: rgba(255,255,255,0.1) !important;
  }

  /* ===== BaseWeb portal widgets (selectbox dropdown, multiselect,
          datepicker, tooltip) — rendered at <body> level outside .stApp,
          so .stApp-scoped rules never reach them. White-on-white in dark
          mode otherwise. ===== */

  /* Selectbox / multiselect dropdown menu */
  [role="listbox"],
  [data-baseweb="menu"],
  ul[data-baseweb="menu"],
  div[data-baseweb="select"] [role="listbox"] {
    background-color: #15171f !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    box-shadow: 0 6px 18px rgba(0,0,0,0.5) !important;
  }
  [role="option"],
  [data-baseweb="menu"] li,
  li[role="option"] {
    background-color: #15171f !important;
    color: #ecedf0 !important;
  }
  [role="option"]:hover,
  [data-baseweb="menu"] li:hover,
  li[role="option"]:hover {
    background-color: rgba(147,197,253,0.12) !important;
    color: #ffffff !important;
  }
  [role="option"][aria-selected="true"],
  li[role="option"][aria-selected="true"] {
    background-color: rgba(30,58,138,0.55) !important;
    color: #ffffff !important;
  }

  /* Multiselect chips (selected-tag pills inside the input) */
  [data-baseweb="tag"] {
    background-color: rgba(147,197,253,0.18) !important;
    color: #ecedf0 !important;
    border-color: rgba(147,197,253,0.35) !important;
  }

  /* Datepicker calendar */
  [data-baseweb="calendar"],
  [data-baseweb="datepicker"] {
    background-color: #15171f !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  [data-baseweb="calendar"] *,
  [data-baseweb="datepicker"] * {
    color: #ecedf0 !important;
  }
  [data-baseweb="calendar"] button[aria-pressed="true"] {
    background-color: #1e3a8a !important;
    color: #ffffff !important;
  }

  /* Tooltips */
  [data-baseweb="tooltip"] {
    background-color: #1a1d28 !important;
    color: #ecedf0 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
  }
  [data-baseweb="tooltip"] * { color: #ecedf0 !important; }
</style>
        """,
        unsafe_allow_html=True,
    )
elif theme_choice == "light":
    # No overrides needed — Streamlit's default light is fine.
    pass
# theme_choice == "auto" → no override; Streamlit's default follows OS pref.


# Suppress Streamlit's developer keyboard shortcuts ('C' = Clear caches,
# 'R' = Rerun, '?' = shortcut list). `toolbarMode = "viewer"` hides the
# toolbar but Streamlit still binds the keydown handler globally, so the
# cache-clear modal pops on a stray 'c' keystroke. We install a capture-
# phase listener that swallows those bare keys *before* Streamlit sees
# them, while leaving Ctrl+C / Cmd+C copy and shortcuts inside form
# inputs untouched.
#
# Must use components.html() (srcdoc iframe) instead of st.markdown
# because <script> tags inserted via innerHTML don't execute — same
# limitation that broke the cookie write earlier. The iframe is
# same-origin, so attaching the listener to window.parent.document
# correctly intercepts keys hitting the main Streamlit page.
import streamlit.components.v1 as _components
# The previous attempt attached the listener directly from the iframe
# to window.parent.document. That works once but the listener function
# lives in the iframe's JS context — when Streamlit reruns and our
# iframe gets replaced, the function reference can become orphaned in
# some browsers and stop firing. Worse, if Streamlit's own keydown
# listener was registered after ours (no guarantee of ordering between
# capture-phase listeners on the same target), it can still see the
# event despite our stopPropagation.
#
# Belt-and-suspenders fix: from the iframe, *inject a real <script>
# element into the parent document*. Once appended, the parent's HTML
# parser executes it, the listener is registered in the parent's own
# JS context, and it survives every iframe lifecycle. We attach to
# both `document` and `window` capture phase to win against whatever
# target Streamlit uses.
_components.html(
    """
<script>
(function() {
  try {
    var pdoc = (window.parent && window.parent.document) ? window.parent.document : null;
    if (!pdoc) return;
    if (pdoc.__praxiaShortcutGuardInstalled) return;
    pdoc.__praxiaShortcutGuardInstalled = true;
    var s = pdoc.createElement('script');
    s.textContent =
      "(function(){" +
        "var SK=new Set(['c','C','r','R','?','/']);" +
        "var handler=function(e){" +
          "if(e.ctrlKey||e.metaKey||e.altKey)return;" +
          "var t=e.target;" +
          "if(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable))return;" +
          "if(SK.has(e.key)){" +
            "e.stopPropagation();e.stopImmediatePropagation();e.preventDefault();" +
          "}" +
        "};" +
        // Bind on every conceivable target: window, document, body,
        // documentElement, both capture and bubble phases. Streamlit
        // 1.57's listener target isn't documented and varies between
        // releases.
        "var attach=function(t){if(!t)return;" +
          "t.addEventListener('keydown',handler,true);" +
          "t.addEventListener('keydown',handler,false);" +
          "t.addEventListener('keypress',handler,true);" +
          "t.addEventListener('keyup',handler,true);" +
        "};" +
        "attach(window);attach(document);" +
        "attach(document.documentElement);attach(document.body);" +
        // Also remove the modal if it slips through — MutationObserver
        // watches for any dialog containing 'Clear caches' and clicks
        // its Cancel/No button (or remove()s it).
        "var killModal=function(){" +
          "var dialogs=document.querySelectorAll('div[role=\\\"dialog\\\"], [data-testid=\\\"stDialog\\\"]');" +
          "for(var i=0;i<dialogs.length;i++){" +
            "var d=dialogs[i];" +
            "if(d&&/Clear caches|Rerun/i.test(d.textContent||'')){" +
              "var btns=d.querySelectorAll('button');" +
              "var clicked=false;" +
              "for(var j=0;j<btns.length;j++){" +
                "var lbl=(btns[j].textContent||'').trim().toLowerCase();" +
                "if(lbl==='cancel'||lbl==='no'||lbl==='close'){btns[j].click();clicked=true;break;}" +
              "}" +
              "if(!clicked)d.remove();" +
            "}" +
          "}" +
        "};" +
        "var mo=new MutationObserver(function(){killModal();});" +
        "mo.observe(document.body||document.documentElement,{childList:true,subtree:true});" +
        // First-pass kill in case the modal is already there.
        "killModal();" +
        "console.log('praxia: shortcut guard active (multi-target + modal observer)');" +
      "})();";
    pdoc.head.appendChild(s);
  } catch(err) { console.error('praxia: shortcut guard install failed', err); }
})();
</script>
    """,
    height=0,
    width=0,
)


# =====================================================================
# Resolve runtime LLM + memory backend
# =====================================================================
# The LLM model is persisted to `.praxia/admin/runtime.json` so the
# choice applies to every user/session, not just the admin's browser.
# Memory backend is no longer set here — it lives entirely under the
# Memory policy section (.praxia/admin/memory_policy.json) which has
# the same persistence + per-process precedence.

_RUNTIME_CONFIG_PATH = Path(".praxia") / "admin" / "runtime.json"


def _load_runtime_default_model() -> str | None:
    try:
        if _RUNTIME_CONFIG_PATH.exists():
            data = json.loads(_RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
            v = data.get("default_model")
            if isinstance(v, str) and v.strip():
                return v
    except Exception:
        pass
    return None


def _save_runtime_default_model(model: str) -> None:
    _RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if _RUNTIME_CONFIG_PATH.exists():
        try:
            payload = json.loads(_RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload["default_model"] = model
    _RUNTIME_CONFIG_PATH.write_text(
        json.dumps(payload, indent=2), encoding="utf-8",
    )


_persistent_default_model = _load_runtime_default_model()
_default_model = _persistent_default_model or list(DEFAULT_ALIASES.keys())[0]
model_choice: str = st.session_state.get("praxia_model", _default_model)
# Memory backend resolution now flows entirely through admin policy +
# Personal/Shared memory's own resolver. We don't override env here —
# previously this line clobbered admin policy with whatever the
# session had picked, which was wrong now that it's not user-pickable.
backend_choice: str = os.getenv("PRAXIA_MEMORY_BACKEND", "json")


@st.cache_resource(show_spinner=False)
def get_loom(_user_id: str, _org_id: str, _model: str) -> Praxia:
    return Praxia(user_id=_user_id, org_id=_org_id, default_model=_model)


# Construct the orchestrator. Most failures here mean a misconfigured
# backend (e.g. mem0 picked but OPENAI_API_KEY missing — Mem0 defaults
# its embedder to OpenAI). Surface a clean message + offer a one-click
# fallback to the safe JSON backend instead of dumping a traceback.
try:
    loom = get_loom(user_id, org_id, model_choice)
except Exception as _loom_exc:
    st.error(t("loom.init_failed").format(
        backend=backend_choice,
        error=str(_loom_exc),
    ))
    st.caption(t("loom.init_failed_hint"))
    if st.button(t("loom.fallback_to_json"), type="primary", key="_loom_fallback_json"):
        st.session_state["praxia_backend"] = "json"
        os.environ["PRAXIA_MEMORY_BACKEND"] = "json"
        try:
            st.cache_resource.clear()
        except Exception:
            pass
        st.rerun()
    st.stop()


# =====================================================================
# Data-scope registry + helpers
# =====================================================================

scope_registry = ScopeRegistry(loom.config.memory_dir / "data")
user_scopes = scope_registry.list_for_user(user_id)
local_scopes = [s for s in user_scopes if s.kind == "local"]
connector_scopes = [s for s in user_scopes if s.kind == "connector"]

thread_store = ThreadStore(loom.config.memory_dir / "chats")


def _grep_relevant(text: str, query: str, max_chars: int = 5000) -> str:
    """Return chunks of ``text`` that look relevant to ``query``.

    Splits the query into keywords (length >= 3), greps each line,
    then includes ±2 lines of context around each match. Merges
    overlapping ranges. Falls back to the first ``max_chars`` of
    ``text`` if nothing matches or no usable keywords.
    """
    import re

    keywords = [w.lower() for w in re.findall(r"\w{3,}", query or "")]
    if not keywords:
        return text[:max_chars]

    lines = text.split("\n")
    matches: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        ll = line.lower()
        if any(kw in ll for kw in keywords):
            matches.append((max(0, i - 2), min(len(lines), i + 3)))

    if not matches:
        return text[:max_chars]

    # Merge overlapping ranges
    merged: list[list[int]] = []
    for s, e in sorted(matches):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    out: list[str] = []
    used = 0
    for s, e in merged:
        chunk = "\n".join(lines[s:e]) + "\n──\n"
        if used + len(chunk) > max_chars:
            break
        out.append(chunk)
        used += len(chunk)
    return "".join(out) if out else text[:max_chars]


def gather_scope_context(
    scope_ids: list[str],
    query: str = "",
    max_chars: int = 20000,
) -> str:
    """Concatenate selected custom-scope contents as additional context.

    Behaviour:
      - If everything fits in ``max_chars``: include all of it.
      - If too big AND ``query`` is non-empty: grep relevant lines
        (keyword-based) and return only matching chunks with context.
      - If too big and no query: include the first 5000 chars of each
        file as a best-effort sample.

    For Agent mode the agent calls this iteratively (current message
    is the query); for Skill mode the user input is the query.
    """
    if not scope_ids:
        return ""

    # First pass: collect (label, full_content) per file.
    items: list[tuple[str, str]] = []
    for sid in scope_ids:
        scope = scope_registry.get(user_id, sid)
        if scope is None:
            continue
        if scope.kind == "local":
            from praxia.io.parsers import parse_file
            for f in scope_registry.list_local_files(scope):
                try:
                    parsed = parse_file(f.read_bytes(), filename=f.name)
                    items.append(
                        (f"File [{scope.name}/{f.name}]", parsed.content)
                    )
                except Exception as exc:
                    items.append(
                        (f"File [{scope.name}/{f.name}]",
                         f"(parse error: {exc})")
                    )
        elif scope.kind == "connector" and scope.connector and scope.connector_path:
            from praxia.connectors import get_connector
            cfg_prefix = f"PRAXIA_CONN_{scope.connector.upper()}_"
            cfg = {
                k.replace(cfg_prefix, "").lower(): v
                for k, v in os.environ.items()
                if k.startswith(cfg_prefix)
            }
            try:
                pulled = get_connector(scope.connector, **cfg).pull(
                    scope.connector_path, limit=10,
                )
                for it in pulled:
                    body = (
                        it.content if isinstance(it.content, str)
                        else f"<binary {len(it.content)} bytes>"
                    )
                    items.append(
                        (f"{scope.connector}:{scope.connector_path}/{it.name}",
                         body)
                    )
            except Exception as exc:
                items.append(
                    (f"Connector {scope.name}", f"pull error: {exc}")
                )

    if not items:
        return ""

    total_chars = sum(len(c) for _, c in items)

    # Path 1 — everything fits comfortably; include verbatim.
    if total_chars <= max_chars:
        return "\n\n".join(f"## {label}\n{content}\n" for label, content in items)

    # Path 2 — too big AND we have a query; grep relevant chunks per file.
    if query.strip():
        per_file_budget = max(2000, max_chars // max(1, len(items)))
        out: list[str] = []
        used = 0
        for label, content in items:
            if used >= max_chars:
                break
            relevant = _grep_relevant(content, query, max_chars=per_file_budget)
            if not relevant.strip():
                continue
            chunk = f"## {label} (relevant excerpts)\n{relevant}\n"
            out.append(chunk)
            used += len(chunk)
        if out:
            return "\n\n".join(out)

    # Path 3 — fallback: first 5000 chars of each file (best-effort sample).
    out = []
    used = 0
    per_file = 5000
    for label, content in items:
        if used >= max_chars:
            break
        snippet = content[:per_file]
        marker = " (truncated)" if len(content) > per_file else ""
        chunk = f"## {label}{marker}\n{snippet}\n"
        out.append(chunk)
        used += len(chunk)
    return "\n\n".join(out)


def gather_scope_images(
    scope_ids: list[str],
    *,
    max_images: int = 10,
    max_total_bytes: int = 20 * 1024 * 1024,
) -> list[dict[str, str]]:
    """Pull image attachments out of selected local-folder scopes.

    Returns the same shape consumed by ``AutonomousAgent.run(images=...)``:
    ``[{"data": "<base64>", "mime": "image/png"}, ...]``. Connector-kind
    scopes are skipped (their image bytes would have to be pulled and
    decoded too — TODO if a real connector demands it).

    Caps to ``max_images`` images and ``max_total_bytes`` of decoded
    payload to keep the LLM call from blowing up the context budget.
    """
    if not scope_ids:
        return []
    out: list[dict[str, str]] = []
    total = 0
    from praxia.io.parsers import parse_file
    for sid in scope_ids:
        if len(out) >= max_images or total >= max_total_bytes:
            break
        scope = scope_registry.get(user_id, sid)
        if scope is None or scope.kind != "local":
            continue
        for f in scope_registry.list_local_files(scope):
            if len(out) >= max_images or total >= max_total_bytes:
                break
            ext = f.suffix.lower().lstrip(".")
            if ext not in {"png", "jpg", "jpeg", "gif", "webp"}:
                continue
            try:
                parsed = parse_file(f.read_bytes(), filename=f.name)
                img = (parsed.metadata or {}).get("image")
                if not img or not img.get("data"):
                    continue
                size = int(img.get("size_bytes") or 0)
                if size and total + size > max_total_bytes:
                    continue
                out.append({"data": img["data"], "mime": img.get("mime", "image/png")})
                total += size
            except Exception:
                continue
    return out


# =====================================================================
# Sidebar — brand · sign-out · ALWAYS-VISIBLE data-scope picker
# =====================================================================

with st.sidebar:
    st.markdown(f"### {t('app.title')}")
    st.caption(f"👤 {user_id} · {actor_role}")
    if st.button(t("login.sign_out"), use_container_width=True, key="signout"):
        # Drop the server-side session record + clear the browser cookie
        # so reload after sign-out doesn't auto-rehydrate.
        _signout_token = st.session_state.get("_praxia_session_token")
        if _signout_token:
            try:
                _session_store.delete(_signout_token)
            except Exception:
                pass
        _clear_session_cookie()
        st.session_state.clear()
        st.rerun()

    st.divider()
    st.markdown(f"**📁 {t('scope.section_h')}**")

    # Built-in scopes
    st.markdown(f"_{t('scope.builtin_h')}_")
    if st.checkbox(t("scope.personal_memory"), value=True, key="scope_personal"):
        pass
    if st.checkbox(t("scope.org_memory"), value=True, key="scope_org"):
        pass
    if st.checkbox(t("scope.frozen"), value=False, key="scope_frozen"):
        pass

    # Custom scopes (local folders + connector folders)
    selected_custom_ids: list[str] = []
    if local_scopes:
        st.markdown(f"_{t('sidebar.scope.local_h')}_")
        # Render in tree order: parents before children, child names
        # show their full path so the hierarchy is visible.
        rendered: set[str] = set()
        def _render_scope_checkbox(s: DataScope, depth: int) -> None:
            n_files = len(scope_registry.list_local_files(s))
            indent = "　" * depth
            if st.checkbox(
                f"{indent}📁 {s.name} ({n_files})",
                value=False, key=f"scope_local_{s.id}",
            ):
                selected_custom_ids.append(s.id)
            rendered.add(s.id)
            for child in [c for c in local_scopes if c.parent_id == s.id]:
                _render_scope_checkbox(child, depth + 1)
        for s in [r for r in local_scopes if r.parent_id is None]:
            _render_scope_checkbox(s, depth=0)
        # Orphans (parent missing): render them at root level for safety.
        for s in local_scopes:
            if s.id not in rendered:
                n_files = len(scope_registry.list_local_files(s))
                if st.checkbox(
                    f"📁 {s.name} ({n_files})",
                    value=False, key=f"scope_local_{s.id}",
                ):
                    selected_custom_ids.append(s.id)
    if connector_scopes:
        st.markdown(f"_{t('sidebar.scope.connector_h')}_")
        for s in connector_scopes:
            if st.checkbox(
                f"🔌 {s.name} ({s.connector})",
                value=False, key=f"scope_conn_{s.id}",
            ):
                selected_custom_ids.append(s.id)

    # If no custom scopes, just show the built-ins; no extra hint needed.


# =====================================================================
# Top-bar navigation (horizontal, role-aware)
# =====================================================================

BASE_NAV = ["run", "memory", "prompts", "data", "dashboard", "preferences"]
ADMIN_NAV = ["admin"]  # Consolidate moved into Admin's sub-tabs.
NAV_KEYS = (
    BASE_NAV + ADMIN_NAV
    if actor_role in ("admin", "unknown")
    else BASE_NAV
)
if st.session_state.get("praxia_mode") not in NAV_KEYS:
    st.session_state["praxia_mode"] = NAV_KEYS[0]

nav_labels = [t(f"mode.{k}") for k in NAV_KEYS]

# Top nav: wrapped in a keyed container so CSS can target it reliably
# via the .st-key-praxia_topnav class that Streamlit auto-generates.
with st.container(key="praxia_topnav"):
    cols = st.columns(len(NAV_KEYS))
    for col, key in zip(cols, NAV_KEYS):
        is_active = st.session_state["praxia_mode"] == key
        if col.button(
            t(f"mode.{key}"),
            use_container_width=True,
            type="primary" if is_active else "secondary",
            key=f"top_nav_{key}",
        ):
            st.session_state["praxia_mode"] = key
            st.rerun()

mode = st.session_state["praxia_mode"]


# =====================================================================
# Mode: Run (Skill / Agent — Workflow dropped from top-level UI)
# =====================================================================

if mode == "run":
    st.header(t("run.h"))

    # Ephemeral mode — applies to both Agent and Skill sub-tabs. When
    # checked, this run does NOT accumulate to personal memory (read_only
    # mode) and does NOT log skill usage to the registry. Default OFF so
    # normal use builds memory + skill stats.
    ephemeral = st.checkbox(
        ("🔒 " if st.session_state.get("run_ephemeral") else "") + t("run.ephemeral"),
        value=False,
        key="run_ephemeral",
        help=t("run.ephemeral_help"),
    )

    # Agent first (default tab) — the user's primary entry point.
    tab_agent, tab_skill = st.tabs([
        t("run.tab.agent"),
        t("run.tab.skill"),
    ])

    # ---- Agent (LLM-driven chat with tool use) ----------------------
    with tab_agent:

        # ----- Thread management ---------------------------------------
        # Persistent threads live on disk (.praxia/chats/<user>/<id>.json).
        # In ephemeral mode we keep messages purely in session_state so
        # they vanish on reload — no disk writes.
        threads = thread_store.list_for_user(user_id)

        # Resolve which thread is currently active. If the user has just
        # arrived (no active id) and threads exist, pick the most-recent.
        active_id = st.session_state.get("active_thread_id")
        if not ephemeral and active_id not in {th.id for th in threads}:
            active_id = threads[0].id if threads else None
            st.session_state["active_thread_id"] = active_id

        if ephemeral:
            st.caption("ℹ️ " + t("run.threads.ephemeral_note"))
            # Ephemeral conversation is in-memory only.
            if "ephemeral_chat" not in st.session_state:
                st.session_state["ephemeral_chat"] = []
            messages_view: list[dict[str, Any]] = st.session_state["ephemeral_chat"]
            active_thread: ChatThread | None = None
        else:
            active_thread = (
                thread_store.load(user_id, st.session_state["active_thread_id"])
                if st.session_state.get("active_thread_id") else None
            )
            messages_view = (
                [
                    {"role": m.role, "content": m.content, "trace": m.trace}
                    for m in active_thread.messages
                ]
                if active_thread else []
            )

            # Single-row top bar: popover button on the left holds the
            # full thread list + rename/delete; caption on the right
            # shows what's currently loaded. Total height ≈ one line.
            bar_left, bar_right = st.columns([1, 3])
            with bar_left:
                pop_label = (
                    f"{t('run.threads.h')} ({len(threads)})"
                    if threads else t("run.threads.h")
                )
                with st.popover(pop_label, use_container_width=True):
                    if st.button(
                        t("run.threads.new"),
                        key="thread_new",
                        use_container_width=True,
                        type="primary",
                    ):
                        new_thread = thread_store.create(user_id)
                        st.session_state["active_thread_id"] = new_thread.id
                        st.session_state.pop("thread_delete_pending", None)
                        st.rerun()
                    st.divider()
                    if not threads:
                        st.caption(t("run.threads.empty"))
                    else:
                        for th in threads:
                            is_active = th.id == (active_thread.id if active_thread else None)
                            label = ("✅ " if is_active else "") + (th.title or "(untitled)")
                            if st.button(
                                label,
                                key=f"th_pick_{th.id}",
                                use_container_width=True,
                                type="tertiary" if is_active else "secondary",
                            ):
                                st.session_state["active_thread_id"] = th.id
                                st.session_state.pop("thread_delete_pending", None)
                                st.rerun()
                    if active_thread is not None:
                        st.divider()
                        new_title = st.text_input(
                            t("run.threads.rename_label"),
                            value=active_thread.title,
                            key=f"thread_rename_{active_thread.id}",
                        )
                        rn_col, del_col = st.columns(2)
                        if rn_col.button(
                            t("run.threads.rename_btn"),
                            key=f"thread_rename_btn_{active_thread.id}",
                            use_container_width=True,
                        ):
                            if new_title.strip() and new_title.strip() != active_thread.title:
                                thread_store.rename(user_id, active_thread.id, new_title.strip())
                                st.rerun()
                        pending_delete = st.session_state.get("thread_delete_pending") == active_thread.id
                        del_label = (
                            t("run.threads.delete_confirm") if pending_delete
                            else t("run.threads.delete_btn")
                        )
                        if del_col.button(
                            del_label,
                            key=f"thread_del_{active_thread.id}",
                            use_container_width=True,
                        ):
                            if pending_delete:
                                thread_store.delete(user_id, active_thread.id)
                                st.session_state.pop("thread_delete_pending", None)
                                st.session_state.pop("active_thread_id", None)
                                st.rerun()
                            else:
                                st.session_state["thread_delete_pending"] = active_thread.id
                                st.rerun()
            with bar_right:
                if active_thread is not None:
                    st.caption(f"💬 {active_thread.title}")

        # ----- Render messages -----------------------------------------
        for msg in messages_view:
            with st.chat_message(msg["role"]):
                if msg.get("content"):
                    st.markdown(msg["content"])
                # Vision attachments — render inline thumbnails.
                for img in msg.get("images") or []:
                    data = img.get("data")
                    mime = img.get("mime", "image/png")
                    if not data:
                        continue
                    try:
                        st.image(
                            f"data:{mime};base64,{data}",
                            width=320,
                        )
                    except Exception:
                        pass
                if msg.get("trace"):
                    with st.expander(t("run.agent.trace"), expanded=False):
                        for step in msg["trace"]:
                            tc = step if isinstance(step, dict) else {}
                            tn = tc.get("tool_name", str(step))
                            ta = tc.get("tool_args", {})
                            tr = tc.get("tool_result", "")
                            st.markdown(f"**🔧 {tn}** `{ta}`")
                            st.text(str(tr)[:600])
                            st.divider()

        # ----- Chat input ----------------------------------------------
        # accept_file=True turns the chat input into an "attach + send"
        # control. When `accept_file` is set, the return value is a
        # ChatInputValue object with `.text` and `.files` (UploadedFile
        # list) instead of a plain string.
        chat_value = st.chat_input(
            t("run.agent.placeholder"),
            accept_file="multiple",
            file_type=["png", "jpg", "jpeg", "gif", "webp"],
        )
        if chat_value:
            # Streamlit returns a ChatInputValue when accept_file is set,
            # else a plain str. Defensive unpacking either way.
            if hasattr(chat_value, "text"):
                prompt = chat_value.text or ""
                uploaded_files = chat_value.files or []
            else:  # pragma: no cover — fallback for older Streamlit
                prompt = str(chat_value)
                uploaded_files = []

            # Encode uploaded images to base64 for the agent + persistence.
            images_payload: list[dict[str, str]] = []
            for f in uploaded_files:
                try:
                    raw = f.getvalue() if hasattr(f, "getvalue") else f.read()
                    mime = getattr(f, "type", None) or "image/png"
                    if not mime.startswith("image/"):
                        continue
                    images_payload.append({
                        "data": base64.b64encode(raw).decode("ascii"),
                        "mime": mime,
                    })
                except Exception as exc:
                    st.warning(f"Could not read attachment: {exc}")

            if not prompt and not images_payload:
                st.stop()

            if not ephemeral and active_thread is None:
                active_thread = thread_store.create(user_id)
                st.session_state["active_thread_id"] = active_thread.id

            user_msg = ChatMessage(role="user", content=prompt, images=images_payload)
            if ephemeral:
                st.session_state["ephemeral_chat"].append({
                    "role": "user",
                    "content": prompt,
                    "trace": [],
                    "images": images_payload,
                })
            else:
                active_thread.messages.append(user_msg)

            # Inject selected scopes as additional reference data —
            # text via gather_scope_context() (greppable string), images
            # via gather_scope_images() which reuses the ImageParser to
            # extract base64 + mime from any png/jpg/gif/webp in the
            # selected local folders. The two streams are combined
            # below: text concatenated to the prompt, images merged
            # with the chat-attached images_payload.
            scope_ctx = (
                gather_scope_context(selected_custom_ids, query=prompt)
                if selected_custom_ids and prompt else ""
            )
            scope_imgs = (
                gather_scope_images(selected_custom_ids)
                if selected_custom_ids else []
            )
            combined_images = (images_payload or []) + scope_imgs
            full_task = (prompt or "(image)") + (
                f"\n\n--- Reference data ---\n{scope_ctx}" if scope_ctx else ""
            )

            # Build a short conversation history for context (last 3 turns
            # before this latest user message). Stored images from prior
            # turns get re-shaped into the multi-content vision format.
            def _prior_to_history_entry(role: str, text: str, imgs: list[dict[str, str]]) -> dict[str, Any]:
                if not imgs:
                    return {"role": role, "content": text}
                parts: list[dict[str, Any]] = [{"type": "text", "text": text or ""}]
                for im in imgs:
                    d, m = im.get("data"), im.get("mime", "image/png")
                    if d:
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{m};base64,{d}"},
                        })
                return {"role": role, "content": parts}

            if ephemeral:
                prior_msgs = st.session_state["ephemeral_chat"][:-1]
                prior = [
                    _prior_to_history_entry(m["role"], m.get("content", ""), m.get("images") or [])
                    for m in prior_msgs
                ]
            else:
                prior = [
                    _prior_to_history_entry(m.role, m.content, m.images)
                    for m in active_thread.messages[:-1]
                ]
            history = prior[-6:]

            # Ephemeral mode: drop personal-memory writes via env flag.
            _saved_mem_mode = os.environ.get("PRAXIA_MEMORY_MODE")
            if ephemeral:
                os.environ["PRAXIA_MEMORY_MODE"] = "read_only"
            try:
                from praxia.agent import AutonomousAgent
                agent = AutonomousAgent(
                    user_id=user_id,
                    role=actor_role if actor_role != "unknown" else "member",
                    org_id=org_id,
                    llm=LLM(model_choice),
                )
                with st.spinner(t("run.agent.thinking")):
                    result = agent.run(
                        full_task,
                        history=history or None,
                        images=combined_images or None,
                    )
                response_text = result.final_text or "(no response)"
                trace = getattr(result, "tool_calls", None) or []
            except Exception as exc:
                # Scrub any leaked key fragments before displaying the
                # third-party error (OpenAI / Anthropic / etc. sometimes
                # echo partial key material in their responses).
                response_text = "❌ " + _scrub_secrets(str(exc))
                trace = []
            finally:
                if ephemeral:
                    if _saved_mem_mode is None:
                        os.environ.pop("PRAXIA_MEMORY_MODE", None)
                    else:
                        os.environ["PRAXIA_MEMORY_MODE"] = _saved_mem_mode

            if ephemeral:
                st.session_state["ephemeral_chat"].append(
                    {"role": "assistant", "content": response_text, "trace": trace}
                )
            else:
                active_thread.messages.append(
                    ChatMessage(role="assistant", content=response_text, trace=trace)
                )
                thread_store.save(active_thread)
            st.rerun()

    # ---- Skill (single domain skill) --------------------------------
    with tab_skill:
        skill_options = {
            f"{s.manifest.domain} — {s.manifest.name}": s
            for s in BUSINESS_SKILLS
        }
        label = st.selectbox(
            t("skill.pick"), options=list(skill_options.keys()), key="sk_pick",
        )
        skill_cls = skill_options[label]
        st.caption(skill_cls.manifest.description)

        from praxia.io.parsers import parse_file as _parse2, supported_extensions as _exts2
        SKILL_EXTS = _exts2()

        skill_input_mode = st.radio(
            t("flow.input_method"),
            options=["text", "file", "voice"],
            format_func=lambda v: (
                t(f"skill.input_method.{v}") if v != "voice"
                else t("flow.input_method.voice")
            ),
            horizontal=True,
            key="skill_input_mode",
        )

        # Optional: load a saved prompt template into the input field.
        if skill_input_mode in ("text", "file"):
            try:
                from praxia.skills.prompts import PromptStore as _PS
                _ps = _PS(storage_dir=loom.config.memory_dir / "prompts")
                _saved = _ps.list_for_user(user_id=user_id, role=actor_role or "member")
            except Exception:
                _saved = []
            if _saved:
                with st.expander(t("skill.use_saved_prompt"), expanded=False):
                    _names = [""] + [p.name for p in _saved]
                    _picked_name = st.selectbox(
                        t("skill.pick_saved_prompt"),
                        options=_names,
                        format_func=lambda n: (
                            t("skill.no_template") if n == ""
                            else f"📄 {n}"
                        ),
                        key="skill_load_pick",
                    )
                    if _picked_name and st.button(
                        t("skill.load_btn"), key="skill_load_btn",
                    ):
                        _picked = next(
                            (p for p in _saved if p.name == _picked_name),
                            None,
                        )
                        if _picked is not None:
                            st.session_state["skill_text"] = _picked.body
                            st.rerun()

        user_input = ""
        if skill_input_mode in ("text", "file"):
            user_input = st.text_area(
                t("skill.input"), height=200,
                placeholder=t("skill.input_placeholder"),
                key="skill_text",
            )

        if skill_input_mode == "file":
            skill_files = st.file_uploader(
                t("skill.attach_label").format(exts=", ".join(SKILL_EXTS)),
                type=SKILL_EXTS,
                accept_multiple_files=True,
                key="skill_files",
            )
            if skill_files:
                attached_text: list[str] = []
                for f in skill_files:
                    try:
                        parsed = _parse2(f.getvalue(), filename=f.name)
                        attached_text.append(
                            f"## Attached file: {f.name}\n{parsed.content[:12000]}"
                        )
                        st.caption(
                            f"📄 {f.name} · {len(parsed.content):,} chars · "
                            f"{parsed.metadata}"
                        )
                    except Exception as e:
                        st.error(f"Failed to parse {f.name}: {e}")
                user_input = (user_input or "") + "\n\n" + "\n\n".join(attached_text)

        if skill_input_mode == "voice":
            audio = st.audio_input(t("skill.audio_record"), key="skill_audio")
            if audio:
                from praxia.io.audio import STT
                with st.spinner(t("common.transcribing")):
                    try:
                        user_input = STT().transcribe(
                            audio.getvalue(),
                            filename="skill_input.wav",
                            language="ja",
                        )
                        st.success(t("common.transcribed").format(n=len(user_input)))
                        st.text_area(
                            t("skill.audio_edit"), value=user_input,
                            height=120, key="stt_edit",
                        )
                    except Exception as e:
                        st.error(f"STT failed: {e}")

        enable_tts = st.checkbox(
            t("skill.tts_toggle"), value=False, key="skill_tts",
        )

        # Sidebar data-scope picker drives this; the user's input is
        # the query for grep-filtering large folders.
        if selected_custom_ids and user_input:
            scope_ctx = gather_scope_context(selected_custom_ids, query=user_input)
            if scope_ctx:
                user_input = (
                    user_input
                    + "\n\n--- Reference data from selected scopes ---\n"
                    + scope_ctx
                )
                st.caption(t("data.injected").format(n=len(selected_custom_ids)))

        if st.button(
            t("flow.run_btn"), key="skill_run", type="primary",
            disabled=not user_input,
        ):
            llm = LLM(model_choice)
            skill_obj = skill_cls(llm=llm)
            with st.spinner(f"Running {skill_obj.manifest.name}…"):
                output = skill_obj.run(user_input)
            st.markdown(output)
            # Ephemeral mode: skip the skill_registry usage log + the
            # promotion-engine signals it feeds. Default mode logs as usual.
            if loom.skill_registry and not ephemeral:
                loom.skill_registry.log_usage(
                    skill_name=skill_obj.manifest.name, user_id=user_id,
                )
            if enable_tts:
                from praxia.io.audio import TTS
                try:
                    with st.spinner(t("skill.tts_synthesizing")):
                        audio_bytes = TTS().synthesize(
                            output[:4000], voice="alloy", format="mp3",
                        )
                    st.audio(audio_bytes, format="audio/mp3")
                except Exception as e:
                    st.warning(f"TTS unavailable: {e}")


# =====================================================================
# Mode: Memory
# =====================================================================

elif mode == "memory":
    st.header(t("memory.h"))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(t("memory.personal_h"))
        if loom.personal_memory:
            entries = loom.personal_memory.all_entries()
            st.metric(t("memory.entries_total"), len(entries))
            search_q = st.text_input(t("memory.search"), key="personal_search")
            shown = (
                loom.personal_memory.search(search_q, limit=20)
                if search_q else [e.text for e in entries[-20:]]
            )
            for s in shown:
                st.text(s)
                st.divider()

    with col2:
        st.subheader(t("memory.shared_h"))
        if loom.shared_memory:
            blocks = loom.shared_memory.list_all()
            st.metric(t("memory.blocks_total"), len(blocks))
            for block in blocks:
                with st.expander(f"📦 {block.label}", expanded=False):
                    st.caption(block.description)
                    st.text(block.value)
                    st.caption(
                        f"contributors: {', '.join(block.promoted_from)}"
                    )

    st.divider()
    st.subheader(t("memory.skills_h"))
    st.caption(t("memory.skills_intro"))
    if loom.skill_registry:
        my_skills = loom.skill_registry.list_personal(user_id)
        org_skills = loom.skill_registry.list_org()
        scol1, scol2 = st.columns(2)
        with scol1:
            st.markdown(f"**{t('memory.skills_personal')}**")
            st.metric(t("memory.skills_count"), len(my_skills))
            if my_skills:
                for sk in my_skills:
                    st.text(f"📄 {sk.name}")
            else:
                st.caption(t("memory.skills_empty"))
        with scol2:
            st.markdown(f"**{t('memory.skills_org')}**")
            st.metric(t("memory.skills_count"), len(org_skills))
            if org_skills:
                for sk in org_skills:
                    st.text(f"⭐ {sk.name}")
            else:
                st.caption(t("memory.skills_empty_org"))


# =====================================================================
# Mode: Data folders
# =====================================================================

elif mode == "data":
    st.header(t("mode.data"))
    st.markdown(t("data.intro"))

    sub_local, sub_connector, sub_browse = st.tabs([
        t("data.tab.local"),
        t("data.tab.connector"),
        t("data.tab.browse"),
    ])

    with sub_local:
        st.caption(t("data.local.intro"))

        # Build a quick lookup: scope_id → list of children (only
        # visible local scopes — owned + shared-in). A shared-in scope
        # whose parent isn't visible to the viewer (because the parent
        # wasn't shared) becomes a root in the viewer's tree.
        _visible_ids = {s.id for s in local_scopes}
        children_of: dict[str | None, list[DataScope]] = {}
        for s in local_scopes:
            effective_parent = s.parent_id if s.parent_id in _visible_ids else None
            children_of.setdefault(effective_parent, []).append(s)

        def _render_local_node(s: DataScope, depth: int = 0) -> None:
            indent = "　" * depth  # full-width space gives visible indent
            files = scope_registry.list_local_files(s)
            kid_count = len(children_of.get(s.id, []))
            is_owned = (s.user_id == user_id)
            owner_badge = "" if is_owned else f"  ·  🤝 {t('data.local.shared_by').format(owner=s.user_id)}"
            share_count = len(s.shared_with or [])
            share_badge = f"  ·  👥 {share_count}" if (is_owned and share_count) else ""
            label = f"{indent}📁 {s.name}  ·  {len(files)} files{share_badge}{owner_badge}"
            if kid_count:
                label += f"  ·  {kid_count} sub"
            with st.expander(label, expanded=False):
                if s.description:
                    st.caption(s.description)
                st.caption(f"id: `{s.id}`  ·  path: `{s.path}`")
                if not is_owned:
                    st.info(
                        t("data.local.shared_in_notice").format(owner=s.user_id)
                    )

                for f in files:
                    col_n, col_s, col_d = st.columns([6, 2, 1])
                    col_n.text(f.name)
                    col_s.caption(f"{f.stat().st_size:,} B")
                    # Read-only when viewing a folder shared from another
                    # owner — only the owner can mutate files.
                    if is_owned and col_d.button("🗑", key=f"delf_{s.id}_{f.name}"):
                        scope_registry.delete_file(s, f.name)
                        st.rerun()

                if is_owned:
                    st.divider()
                    from praxia.io.parsers import supported_extensions as _data_exts
                    new_files = st.file_uploader(
                        t("data.local.add_files"),
                        accept_multiple_files=True,
                        type=_data_exts(),
                        key=f"upload_more_{s.id}",
                    )
                    col_save, col_del = st.columns(2)
                    if col_save.button(t("data.local.save_uploads"),
                                       key=f"save_{s.id}"):
                        if new_files:
                            saved = scope_registry.save_uploaded_files(s, new_files)
                            st.success(t("data.local.saved").format(n=len(saved)))
                            st.rerun()
                        else:
                            st.warning(t("data.local.no_files_to_save"))
                    if col_del.button(t("data.local.delete_folder"),
                                      type="secondary", key=f"delfol_{s.id}"):
                        scope_registry.delete(user_id, s.id)
                        st.success(t("data.local.folder_deleted").format(name=s.name))
                        st.rerun()

                    # ---- Share / unshare section (owner-only) ----
                    st.divider()
                    st.markdown(f"**{t('data.local.share_h')}**")
                    st.caption(t("data.local.share_intro"))
                    # Build user picker. The auth UserStore is authoritative
                    # for valid user_ids; we deliberately exclude the owner
                    # and inactive users.
                    _picker_options: list[str] = []
                    try:
                        if auth is not None:
                            for u in auth.users.list_all():
                                if u.username == user_id:
                                    continue
                                if not getattr(u, "is_active", True):
                                    continue
                                _picker_options.append(u.username)
                    except Exception:
                        pass
                    # Fallback for dev mode (no users registered yet) — let
                    # the admin still type a user_id by hand below.
                    selected = st.multiselect(
                        t("data.local.share_select_label"),
                        options=sorted(set(_picker_options + (s.shared_with or []))),
                        default=s.shared_with or [],
                        key=f"share_pick_{s.id}",
                        help=t("data.local.share_select_help"),
                    )
                    extra_uid = st.text_input(
                        t("data.local.share_addhoc_label"),
                        value="",
                        key=f"share_extra_{s.id}",
                        placeholder=t("data.local.share_addhoc_placeholder"),
                    )
                    final = list(selected)
                    if extra_uid.strip():
                        final.append(extra_uid.strip())
                    col_apply, col_clear = st.columns(2)
                    if col_apply.button(
                        t("data.local.share_apply"),
                        type="primary",
                        key=f"share_apply_{s.id}",
                    ):
                        if scope_registry.set_shared_with(user_id, s.id, final):
                            try:
                                if auth is not None:
                                    auth.audit.record(
                                        actor_id=user_id,
                                        actor_role=actor_role,
                                        action="data.share",
                                        resource=f"scope:{s.id}",
                                        metadata={
                                            "scope_name": s.name,
                                            "shared_with": final,
                                        },
                                    )
                            except Exception:
                                pass
                            st.success(t("data.local.share_saved"))
                            st.rerun()
                        else:
                            st.info(t("data.local.share_no_changes"))
                    if (s.shared_with or []) and col_clear.button(
                        t("data.local.share_clear"),
                        type="secondary",
                        key=f"share_clear_{s.id}",
                    ):
                        if scope_registry.set_shared_with(user_id, s.id, []):
                            try:
                                if auth is not None:
                                    auth.audit.record(
                                        actor_id=user_id,
                                        actor_role=actor_role,
                                        action="data.unshare_all",
                                        resource=f"scope:{s.id}",
                                        metadata={"scope_name": s.name},
                                    )
                            except Exception:
                                pass
                            st.success(t("data.local.share_cleared"))
                            st.rerun()

            # Recurse into sub-folders (after parent's expander closes)
            for child in children_of.get(s.id, []):
                _render_local_node(child, depth + 1)

        if local_scopes:
            for root in children_of.get(None, []):
                _render_local_node(root, depth=0)
        else:
            st.info(t("data.local.empty"))

        st.divider()
        st.subheader(t("data.local.create_h"))
        with st.form("data_local_create_form", clear_on_submit=True):
            new_name = st.text_input(t("data.local.create_name"))
            new_desc = st.text_input(t("data.local.create_desc"))

            # Parent-folder picker — empty string == top-level
            parent_options: list[str] = [""]
            parent_labels: dict[str, str] = {"": t("data.local.parent_root")}
            for s in local_scopes:
                parent_options.append(s.id)
                parent_labels[s.id] = "📁 " + scope_registry.full_path(user_id, s.id)
            new_parent = st.selectbox(
                t("data.local.parent_label"),
                options=parent_options,
                format_func=lambda x: parent_labels.get(x, x),
                key="create_local_parent",
            )

            from praxia.io.parsers import supported_extensions as _data_exts2
            init_files = st.file_uploader(
                t("data.local.create_files"),
                accept_multiple_files=True,
                type=_data_exts2(),
                key="create_local_files",
            )
            if st.form_submit_button(t("data.local.create_btn"), type="primary"):
                if not new_name:
                    st.warning(t("data.local.create_name_required"))
                else:
                    s = scope_registry.create_local(
                        user_id, new_name, new_desc,
                        parent_id=new_parent or None,
                    )
                    if init_files:
                        scope_registry.save_uploaded_files(s, init_files)
                    st.success(t("data.local.created").format(name=new_name))
                    st.rerun()

    with sub_connector:
        st.caption(t("data.connector.intro"))
        if connector_scopes:
            for s in connector_scopes:
                with st.expander(
                    f"🔌 {s.name} ({s.connector}: {s.connector_path})",
                    expanded=False,
                ):
                    if s.description:
                        st.caption(s.description)
                    st.caption(f"id: `{s.id}`")
                    if st.button(t("data.connector.delete"),
                                 key=f"delcon_{s.id}"):
                        scope_registry.delete(user_id, s.id)
                        st.success(t("data.local.folder_deleted").format(name=s.name))
                        st.rerun()
        else:
            st.info(t("data.connector.empty"))

        st.divider()
        st.subheader(t("data.connector.create_h"))
        from praxia.connectors.registry import list_builtin
        with st.form("data_connector_create_form", clear_on_submit=True):
            cn_name = st.text_input(
                t("data.connector.create_name"), placeholder="Customer Acme",
            )
            cn_desc = st.text_input(t("data.connector.create_desc"))
            cn_connector = st.selectbox(
                t("data.connector.create_connector"),
                options=list_builtin(),
            )
            cn_path = st.text_input(
                t("data.connector.create_path"),
                placeholder="/Customers/Acme  ·  https://… ·  app:42",
            )
            if st.form_submit_button(t("data.connector.create_btn"), type="primary"):
                if not (cn_name and cn_path):
                    st.warning(t("data.connector.create_required"))
                else:
                    scope_registry.create_connector(
                        user_id, cn_name, cn_connector, cn_path, cn_desc,
                    )
                    st.success(t("data.local.created").format(name=cn_name))
                    st.rerun()

    with sub_browse:
        if not user_scopes:
            st.info(t("data.browse.empty"))
        else:
            picked_id = st.selectbox(
                t("data.browse.pick"),
                options=[s.id for s in user_scopes],
                format_func=lambda i: next(
                    (f"📁 {s.name}" if s.kind == "local" else f"🔌 {s.name}")
                    for s in user_scopes if s.id == i
                ),
            )
            picked = scope_registry.get(user_id, picked_id)
            if picked is None:
                st.warning(t("data.browse.not_found"))
            elif picked.kind == "local":
                files = scope_registry.list_local_files(picked)
                st.markdown(f"**{picked.name}** · {len(files)} files")
                for f in files:
                    with st.expander(f.name, expanded=False):
                        try:
                            from praxia.io.parsers import parse_file
                            parsed = parse_file(f.read_bytes(), filename=f.name)
                            st.text(parsed.content[:5000])
                            st.caption(f"parsed {len(parsed.content):,} chars")
                        except Exception as exc:
                            st.text(f"<could not parse: {exc}>")
            else:
                st.markdown(
                    f"**{picked.name}** "
                    f"({picked.connector}: `{picked.connector_path}`)"
                )
                if st.button(t("data.browse.connector_pull"),
                             key=f"prev_{picked.id}"):
                    from praxia.connectors import get_connector
                    cfg_prefix = f"PRAXIA_CONN_{picked.connector.upper()}_"
                    cfg = {
                        k.replace(cfg_prefix, "").lower(): v
                        for k, v in os.environ.items()
                        if k.startswith(cfg_prefix)
                    }
                    try:
                        items = get_connector(picked.connector, **cfg).pull(
                            picked.connector_path, limit=10,
                        )
                        st.success(f"Pulled {len(items)} items")
                        for it in items:
                            with st.expander(f"📥 {it.name}", expanded=False):
                                if isinstance(it.content, str):
                                    st.text(it.content[:2000])
                                else:
                                    st.text(f"<binary, {len(it.content)} bytes>")
                    except Exception as exc:
                        st.error(str(exc))


# =====================================================================
# Mode: Preferences (per-user, persisted)
# =====================================================================

elif mode == "preferences":
    st.header(t("preferences.h"))

    # Language
    current_lang = st.session_state.get("praxia_lang", detect_language())
    if current_lang not in SUPPORTED:
        current_lang = "en"
    new_lang = st.selectbox(
        t("preferences.language_h"),
        options=SUPPORTED,
        index=SUPPORTED.index(current_lang),
        format_func=lambda c: LANG_DISPLAY[c],
        key="pref_lang_pick",
        help=t("preferences.language_intro"),
    )
    if new_lang != current_lang:
        st.session_state["praxia_lang"] = new_lang
        save_user_pref(user_id, "praxia_lang", new_lang)
        st.rerun()

    # Color theme
    current_theme = st.session_state.get("praxia_theme", "auto")
    THEME_OPTIONS = ["auto", "light", "dark"]
    new_theme = st.selectbox(
        t("preferences.theme_h"),
        options=THEME_OPTIONS,
        index=THEME_OPTIONS.index(current_theme) if current_theme in THEME_OPTIONS else 0,
        format_func=lambda c: t(f"preferences.theme.{c}"),
        key="pref_theme_pick",
        help=t("preferences.theme_intro"),
    )
    if new_theme != current_theme:
        st.session_state["praxia_theme"] = new_theme
        save_user_pref(user_id, "praxia_theme", new_theme)
        st.rerun()

    st.caption(t("preferences.llm_moved_hint"))


# =====================================================================
# Mode: Dashboard
# =====================================================================

elif mode == "dashboard":
    st.header(t("dashboard.h"))
    from praxia.analytics import Dashboard

    try:
        import plotly.express as _px
        _HAS_PLOTLY = True
    except ImportError:
        _HAS_PLOTLY = False

    d = Dashboard(memory_dir=loom.config.memory_dir)
    scope = st.radio(
        t("dashboard.scope_label"),
        options=["personal", "org"],
        format_func=lambda x: t(f"dashboard.scope.{x}"),
        horizontal=True,
        key="dash_scope",
        label_visibility="collapsed",
    )

    if scope == "personal":
        s = d.personal_summary(user_id)

        # Headline KPIs only (3 most-watched)
        c1, c2, c3 = st.columns(3)
        c1.metric(t("dashboard.runs_total"), s.flow_runs + s.skill_runs)
        c2.metric(t("dashboard.success_rate"), f"{s.success_rate:.0%}")
        c3.metric(t("dashboard.memory_entries"), s.memory_entries)

        # Chart: top skills (the actual signal worth visualising)
        if s.top_skills:
            st.subheader(t("dashboard.top_skills"))
            data = sorted(
                [{"skill": n, "count": c} for n, c in s.top_skills],
                key=lambda x: x["count"],
                reverse=True,
            )[:8]
            if _HAS_PLOTLY:
                fig = _px.bar(
                    data, x="count", y="skill",
                    orientation="h",
                    color="count",
                    color_continuous_scale=[[0, "#8b6f30"], [1, "#e9c378"]],
                    height=max(220, 36 * len(data) + 80),
                )
                fig.update_layout(
                    showlegend=False,
                    yaxis=dict(autorange="reversed", title=""),
                    xaxis=dict(title=""),
                    margin=dict(l=10, r=10, t=10, b=10),
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.table(data)
        else:
            st.caption(t("dashboard.empty"))

    else:  # org
        s = d.org_summary(org_id)

        c1, c2, c3 = st.columns(3)
        c1.metric(t("dashboard.active_users"), s.active_users)
        c2.metric(t("dashboard.org_runs_total"), s.total_flow_runs + s.total_skill_runs)
        c3.metric(t("dashboard.success_rate"), f"{s.org_success_rate:.0%}")

        cols = st.columns(2)

        # Top users (left)
        with cols[0]:
            st.subheader(t("dashboard.top_users"))
            if s.top_users:
                tu = sorted(
                    [{"user_id": u, "events": c} for u, c in s.top_users],
                    key=lambda x: x["events"], reverse=True,
                )[:8]
                if _HAS_PLOTLY:
                    fig = _px.bar(
                        tu, x="events", y="user_id",
                        orientation="h",
                        color="events",
                        color_continuous_scale=[[0, "#3a4a6e"], [1, "#7895d6"]],
                        height=max(220, 36 * len(tu) + 80),
                    )
                    fig.update_layout(
                        showlegend=False,
                        yaxis=dict(autorange="reversed", title=""),
                        xaxis=dict(title=""),
                        margin=dict(l=10, r=10, t=10, b=10),
                        coloraxis_showscale=False,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.table(tu)
            else:
                st.caption(t("dashboard.empty"))

        # Top skills (right)
        with cols[1]:
            st.subheader(t("dashboard.top_skills"))
            if s.top_skills:
                ts = sorted(
                    [{"skill": n, "count": c} for n, c in s.top_skills],
                    key=lambda x: x["count"], reverse=True,
                )[:8]
                if _HAS_PLOTLY:
                    fig = _px.bar(
                        ts, x="count", y="skill",
                        orientation="h",
                        color="count",
                        color_continuous_scale=[[0, "#8b6f30"], [1, "#e9c378"]],
                        height=max(220, 36 * len(ts) + 80),
                    )
                    fig.update_layout(
                        showlegend=False,
                        yaxis=dict(autorange="reversed", title=""),
                        xaxis=dict(title=""),
                        margin=dict(l=10, r=10, t=10, b=10),
                        coloraxis_showscale=False,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.table(ts)
            else:
                st.caption(t("dashboard.empty"))


# =====================================================================
# Mode: Prompts
# =====================================================================

elif mode == "prompts":
    st.header(t("prompts.h"))
    st.caption(t("prompts.intro"))
    from praxia.skills.prompts import PromptStore

    store = PromptStore(storage_dir=loom.config.memory_dir / "prompts")
    # Distribute is admin-only; hide the tab entirely for non-admin
    # users instead of rendering it with a denied error inside.
    is_admin_or_dev = actor_role in ("admin", "unknown")
    if is_admin_or_dev:
        sub_generate, sub_browse, sub_distribute = st.tabs([
            t("prompts.tab.generate"),
            t("prompts.tab.browse"),
            t("prompts.tab.distribute"),
        ])
    else:
        sub_generate, sub_browse = st.tabs([
            t("prompts.tab.generate"),
            t("prompts.tab.browse"),
        ])
        sub_distribute = None

    with sub_generate:
        st.markdown(t("prompts.generate.intro"))

        with st.form("prompt_designer_form"):
            pd_task = st.text_area(
                t("prompts.generate.task_label"),
                placeholder=t("prompts.generate.task_placeholder"),
                height=120,
            )
            pd_col1, pd_col2, pd_col3 = st.columns(3)
            with pd_col1:
                pd_target_llm = st.selectbox(
                    t("prompts.generate.target_llm"),
                    options=["", "claude", "gpt-5", "gpt-4o", "gemini",
                             "deepseek-r1", "deepseek", "mistral",
                             "codestral", "grok", "llama", "phi", "qwen",
                             "gemma", "command-r", "perplexity"],
                    format_func=lambda x: t("prompts.generate.target_llm_auto") if x == "" else x,
                    key="pd_target_llm",
                )
            with pd_col2:
                pd_output_format = st.selectbox(
                    t("prompts.generate.output_format"),
                    options=["text", "json", "markdown", "xml"],
                    index=1, key="pd_output_format",
                )
            with pd_col3:
                pd_constraint = st.selectbox(
                    t("prompts.generate.constraint"),
                    options=["strict", "loose"], key="pd_constraint",
                )
            pd_include_examples = st.checkbox(
                t("prompts.generate.include_examples"),
                value=True, key="pd_include_examples",
            )
            generate_clicked = st.form_submit_button(
                t("prompts.generate.btn"), type="primary",
            )

        if generate_clicked:
            if not pd_task.strip():
                st.warning(t("prompts.generate.task_required"))
            else:
                from praxia.skills import PromptDesignerSkill
                designer = PromptDesignerSkill(llm=LLM(model_choice))
                with st.spinner(t("prompts.generate.designing")):
                    try:
                        result = designer.design(
                            task=pd_task,
                            target_llm=pd_target_llm,
                            output_format=pd_output_format,
                            include_examples=pd_include_examples,
                            constraint_level=pd_constraint,
                        )
                        st.session_state["pd_result"] = result
                        st.session_state["pd_task"] = pd_task
                        st.session_state["pd_target_llm"] = pd_target_llm
                    except Exception as e:
                        st.error(f"Generation failed: {e}")

        if "pd_result" in st.session_state:
            from praxia.skills import PromptDesignerSkill
            st.divider()
            result = st.session_state["pd_result"]
            primary = result.prompts[0] if hasattr(result, "prompts") and result.prompts else result
            md = PromptDesignerSkill().format_markdown(primary)
            st.markdown(md)

            with st.expander(t("prompts.generate.save_h"), expanded=True):
                save_name = st.text_input(
                    t("prompts.generate.save_name"), key="pd_save_name",
                    placeholder="my_contract_risk_v1",
                )
                save_desc = st.text_input(
                    t("prompts.generate.save_desc"),
                    value=f"Generated for: {st.session_state['pd_task'][:80]}",
                    key="pd_save_desc",
                )
                col_save_btn, col_clear_btn = st.columns(2)
                if col_save_btn.button(
                    t("prompts.generate.save_btn"),
                    key="pd_save_btn", type="primary",
                    disabled=not save_name,
                ):
                    store.save_personal(
                        user_id=user_id, name=save_name, body=md,
                        description=save_desc,
                        tags=["generated", st.session_state.get("pd_target_llm") or "auto"],
                    )
                    st.success(t("prompts.generate.saved").format(name=save_name))
                    for k in ("pd_result", "pd_task", "pd_target_llm"):
                        st.session_state.pop(k, None)
                    st.rerun()
                if col_clear_btn.button(t("prompts.generate.discard_btn"), key="pd_discard_btn"):
                    for k in ("pd_result", "pd_task", "pd_target_llm"):
                        st.session_state.pop(k, None)
                    st.rerun()

    with sub_browse:
        st.caption(t("prompts.browse.scope_hint"))
        # The merged view: personal + org + distributed-to-this-user-or-role.
        # Use the actual signed-in role so distributed prompts targeting
        # admin/operator/etc. show up to those roles too. This is also
        # 'where distributed prompts go' — recipients see them here with
        # a [distributed] scope tag.
        prompts = store.list_for_user(
            user_id=user_id,
            role=actor_role if actor_role != "unknown" else "admin",
        )
        if prompts:
            for p in prompts:
                with st.expander(f"📄 {p.name} [{p.scope}]", expanded=False):
                    st.caption(p.description or "—")
                    st.caption(f"tags: {', '.join(p.tags) or '—'}  ·  owner: {p.owner}")
                    if p.scope == "personal" and p.owner == user_id:
                        new_body = st.text_area(
                            t("prompts.edit.body_label"),
                            value=p.body, height=240,
                            key=f"edit_body_{p.name}",
                        )
                        new_desc = st.text_input(
                            t("prompts.edit.desc_label"),
                            value=p.description or "",
                            key=f"edit_desc_{p.name}",
                        )
                        new_tags = st.text_input(
                            t("prompts.edit.tags_label"),
                            value=", ".join(p.tags),
                            key=f"edit_tags_{p.name}",
                        )
                        col_s, col_d = st.columns(2)
                        if col_s.button(
                            t("prompts.edit.save_btn"),
                            key=f"save_{p.name}", type="primary",
                        ):
                            store.save_personal(
                                user_id=user_id, name=p.name,
                                body=new_body, description=new_desc,
                                tags=[s.strip() for s in new_tags.split(",") if s.strip()],
                            )
                            st.success(t("prompts.edit.saved"))
                            st.rerun()
                        if col_d.button(
                            t("prompts.edit.delete_btn"),
                            key=f"del_{p.name}", type="secondary",
                        ):
                            store.delete_personal(user_id, p.name)
                            st.success(t("prompts.edit.deleted"))
                            st.rerun()
                    else:
                        st.text(
                            p.body[:1000] + ("…" if len(p.body) > 1000 else "")
                        )
                        st.caption(t("prompts.edit.readonly_hint").format(scope=p.scope))
        else:
            st.info(t("prompts.browse.empty"))

        st.divider()
        with st.expander(t("prompts.create.h"), expanded=False):
            with st.form("prompt_create_form"):
                name = st.text_input(
                    t("prompts.create.name"),
                    placeholder="my_sales_qualifier",
                )
                description = st.text_input(t("prompts.create.desc"))
                tags = st.text_input(t("prompts.create.tags"))
                body = st.text_area(t("prompts.create.body"), height=240)
                if st.form_submit_button(t("prompts.create.btn"), type="primary"):
                    if name and body:
                        store.save_personal(
                            user_id=user_id, name=name, body=body,
                            description=description,
                            tags=[s.strip() for s in tags.split(",") if s.strip()],
                        )
                        st.success(t("prompts.create.saved").format(name=name))
                        st.rerun()
                    else:
                        st.warning(t("prompts.create.required"))

    if sub_distribute is not None:
        with sub_distribute:
            st.markdown(t("prompts.distribute.intro"))
            with st.form("prompt_distribute_form"):
                d_name = st.text_input(t("prompts.create.name"), key="dn")
                d_body = st.text_area(t("prompts.create.body"), height=200, key="db")
                d_target_users = st.text_input(
                    t("prompts.distribute.target_users"), key="dtu",
                )
                d_target_roles = st.multiselect(
                    t("prompts.distribute.target_roles"),
                    ["admin", "operator", "member", "viewer"], key="dtr",
                )
                submit = st.form_submit_button(
                    t("prompts.distribute.btn"), type="primary",
                )
                if submit and d_name and d_body and (d_target_users or d_target_roles):
                    saved = store.distribute(
                        name=d_name, body=d_body,
                        target_users=[u.strip() for u in d_target_users.split(",") if u.strip()] or None,
                        target_roles=d_target_roles or None,
                    )
                    st.success(t("prompts.distribute.saved").format(n=len(saved)))

            # Show what's currently distributed (admin overview)
            st.divider()
            st.subheader(t("prompts.distribute.history_h"))
            st.caption(t("prompts.distribute.history_intro"))
            try:
                from praxia.skills.prompts import PromptStore as _PS
                _store = _PS(storage_dir=loom.config.memory_dir / "prompts")
                # Walk the distributed/ directory: each subdirectory is a target
                _dist_root = _store.root / "distributed"
                rows: list[dict[str, str]] = []
                if _dist_root.exists():
                    for tgt in sorted(_dist_root.iterdir()):
                        if not tgt.is_dir():
                            continue
                        for f in sorted(tgt.glob("*.json")):
                            p = _store._read(f)
                            if p is not None:
                                rows.append({
                                    "name": p.name,
                                    "target": tgt.name,
                                    "tags": ", ".join(p.tags) or "—",
                                    "owner": p.owner,
                                })
                if rows:
                    st.table(rows)
                else:
                    st.caption(t("prompts.distribute.history_empty"))
            except Exception as e:
                st.caption(f"({e})")


# =====================================================================
# Mode: Admin
# =====================================================================

elif mode == "admin":
    st.header(t("admin.header"))

    try:
        from praxia.auth import AuthManager
        auth = AuthManager(storage_dir=loom.config.memory_dir / "auth")
    except Exception as e:
        st.error(f"Auth not available: {e}")
        auth = None

    users_exist = False
    if auth is not None:
        try:
            users_exist = bool(auth.users.list_all())
        except Exception:
            pass

    if users_exist and actor_role != "admin":
        st.error(t("admin.gate.denied").format(user=user_id, role=actor_role))
        st.markdown(t("admin.gate.howto"))
        st.stop()
    if not users_exist:
        st.warning(t("admin.gate.dev_mode"))

    (
        tab_settings, tab_users, tab_connectors, tab_policies,
        tab_consolidate, tab_exports, tab_about,
    ) = st.tabs([
        t("admin.settings.subtab"),
        t("admin.users.subtab"),
        t("admin.connectors.subtab"),
        t("admin.policies.subtab"),
        t("admin.consolidate.subtab"),
        t("admin.downloads.subtab"),
        t("admin.about.subtab"),
    ])

    with tab_settings:
        from praxia.config import KNOWN_KEYS, PraxiaConfig

        st.markdown(t("admin.settings.intro"))

        if actor_role == "admin":
            st.success(t("admin.settings.role_ok").format(user=user_id))
        elif actor_role == "unknown":
            st.info(t("admin.settings.role_unknown").format(user=user_id))
        else:
            st.error(t("admin.settings.role_blocked").format(
                user=user_id, role=actor_role,
            ))

        # Default LLM model — persisted to .praxia/admin/runtime.json
        # so it applies to every user and survives Streamlit restarts.
        # Memory backend used to live here too but now belongs entirely
        # under the Memory policy section below (one source of truth).
        st.subheader(t("admin.settings.runtime_h"))
        col_p, col_m = st.columns(2)
        current_model = st.session_state.get("praxia_model", _default_model)
        # Resolve alias to full model id for matching against the provider map.
        _resolved_current = DEFAULT_ALIASES.get(current_model, current_model)
        current_provider = provider_for_model(current_model)
        provider_options = list(LLM_PROVIDERS.keys()) + ["Custom"]
        with col_p:
            picked_provider = st.selectbox(
                t("admin.settings.provider_label"),
                options=provider_options,
                index=(
                    provider_options.index(current_provider)
                    if current_provider in provider_options else 0
                ),
                key="settings_provider_pick",
            )
        with col_m:
            if picked_provider == "Custom":
                picked_model = st.text_input(
                    t("admin.settings.model_custom"),
                    value=(
                        _resolved_current
                        if "/" in _resolved_current
                        else "anthropic/claude-opus-4-7"
                    ),
                    key="settings_model_custom_input",
                )
            else:
                models_for_provider = LLM_PROVIDERS[picked_provider]
                labels = [m[0] for m in models_for_provider]
                ids = [m[1] for m in models_for_provider]
                # Default to current model if it sits inside this provider's
                # list; otherwise fall through to the first option.
                default_idx = ids.index(_resolved_current) if _resolved_current in ids else 0
                picked_label = st.selectbox(
                    t("admin.settings.model_label"),
                    options=labels,
                    index=default_idx,
                    key="settings_model_pick",
                )
                picked_model = ids[labels.index(picked_label)]
        if st.button(
            t("admin.settings.runtime_apply"), type="primary",
            key="settings_runtime_apply",
        ):
            try:
                _save_runtime_default_model(picked_model)
                st.session_state["praxia_model"] = picked_model
                st.cache_resource.clear()
                st.success(t("admin.settings.runtime_saved"))
                st.rerun()
            except Exception as exc:
                st.error(f"Save failed: {exc}")

        st.divider()

        # Persistent memory policy — written to .praxia/admin/memory_policy.json
        # and observed by all PersonalMemory constructions. Distinct from the
        # session-scoped runtime override above.
        st.subheader(t("admin.settings.memory_policy_h"))

        from praxia.memory.policy import MemoryAdminPolicy
        _BACKEND_CHOICES = ["json", "mem0", "langmem", "letta", "zep", "hindsight"]
        _MODE_CHOICES = ["accumulate", "read_only"]

        _admin_pol = MemoryAdminPolicy.load(loom.config.memory_dir)

        mp_col1, mp_col2 = st.columns(2)
        with mp_col1:
            mp_default_backend = st.selectbox(
                t("admin.settings.mp_default_backend"),
                options=_BACKEND_CHOICES,
                index=(
                    _BACKEND_CHOICES.index(_admin_pol.default_backend)
                    if _admin_pol.default_backend in _BACKEND_CHOICES else 0
                ),
                key="mp_default_backend",
                help=t("admin.settings.mp_default_backend_help"),
            )
            mp_enforced = st.selectbox(
                t("admin.settings.mp_enforced_backend"),
                options=["__none__"] + _BACKEND_CHOICES,
                index=(
                    _BACKEND_CHOICES.index(_admin_pol.enforced_backend) + 1
                    if _admin_pol.enforced_backend in _BACKEND_CHOICES else 0
                ),
                format_func=lambda x: (
                    t("admin.settings.mp_enforced_none") if x == "__none__" else x
                ),
                key="mp_enforced_backend",
                help=t("admin.settings.mp_enforced_backend_help"),
            )
            mp_allowed = st.multiselect(
                t("admin.settings.mp_allowed_backends"),
                options=_BACKEND_CHOICES,
                default=_admin_pol.allowed_backends,
                key="mp_allowed_backends",
                help=t("admin.settings.mp_allowed_backends_help"),
            )
        with mp_col2:
            mp_default_mode = st.selectbox(
                t("admin.settings.mp_default_mode"),
                options=_MODE_CHOICES,
                index=_MODE_CHOICES.index(_admin_pol.default_mode),
                format_func=lambda m: t(f"admin.settings.mp_mode.{m}"),
                key="mp_default_mode",
                help=t("admin.settings.mp_default_mode_help"),
            )
            # Mode-lock + role-accumulate-lock controls used to gate users
            # from changing their own preference. The user-facing memory
            # pref UI was deliberately removed (admin-only memory config),
            # so there's nothing left for these to lock against. We keep
            # the dataclass fields for CLI/SDK callers but hide them here
            # to match what's actually reachable from the UI.

        if st.button(
            t("admin.settings.mp_apply"), type="primary",
            key="mp_apply_btn",
        ):
            new_pol = MemoryAdminPolicy(
                enforced_backend=(None if mp_enforced == "__none__" else mp_enforced),
                default_backend=mp_default_backend,
                allowed_backends=mp_allowed,
                default_mode=mp_default_mode,
                mode_locked=_admin_pol.mode_locked,
                accumulate_locked_to=_admin_pol.accumulate_locked_to,
            )
            new_pol.save(loom.config.memory_dir)
            try:
                st.cache_resource.clear()
            except Exception:
                pass
            st.success(t("admin.settings.mp_saved"))
            st.rerun()

        st.divider()

        st.subheader(t("admin.settings.persistent_h"))

        def _mask_for_display(value: str) -> str:
            # Full mask. Showing first/last chars (e.g. "50b6…e652")
            # leaks information that helps an attacker confirm a stolen
            # key fragment — also fails common password-policy reviews
            # for "no partial token display". Always render `****`.
            return "****"

        from collections import OrderedDict
        grouped: "OrderedDict[str, list[tuple[str, bool]]]" = OrderedDict()
        for _key, (_cat, _is_secret) in KNOWN_KEYS.items():
            grouped.setdefault(_cat, []).append((_key, _is_secret))

        from praxia.ui.settings_guide import category_meta, section_for, TOP_LEVEL_SECTIONS

        # Bucket the categories by top-level section so the UI can
        # render section headings ("LLM Providers" / "OAuth" /
        # "Security" / "Runtime defaults" / "Other") with the
        # related sub-categories grouped underneath. Order is fixed
        # by TOP_LEVEL_SECTIONS so the layout is stable.
        _section_buckets: "OrderedDict[str, list[str]]" = OrderedDict()
        # Pre-seed with declared sections to keep the order stable
        for label_key, _pred in TOP_LEVEL_SECTIONS:
            _section_buckets.setdefault(label_key, [])
        _section_buckets.setdefault("settings.section.other", [])
        for category in grouped.keys():
            _section_buckets[section_for(category)].append(category)

        for section_key, cats in _section_buckets.items():
            if not cats:
                continue
            st.markdown(f"#### {t(section_key)}")
            for category in cats:
                keys = grouped[category]
                _meta = category_meta(category)
                _required = set(_meta.get("required") or [])
                _key_help_map = _meta.get("key_help") or {}
                _intro_key = _meta.get("intro")
                _cross_refs = _meta.get("cross_refs") or []

                # Header: set/required progress for multi-key groups.
                # Sections always start collapsed — the page would
                # otherwise paint multiple full-screen-tall forms on
                # first visit. Status icon + count in the header is
                # enough to show what needs attention.
                if _required:
                    _set_required = sum(
                        1 for k, _ in keys
                        if k in _required and PraxiaConfig.get(k) is not None
                    )
                    _progress = (
                        f"{_set_required}/{len(_required)} "
                        + t("admin.settings.keys_required_label")
                    )
                    _all_required_set = (_set_required == len(_required))
                    _icon = "✅" if _all_required_set else ("⚠️" if _set_required else "")
                else:
                    _set_count = sum(
                        1 for k, _ in keys if PraxiaConfig.get(k) is not None
                    )
                    _progress = (
                        f"{_set_count}/{len(keys)} "
                        + t("admin.settings.keys_set_label")
                    )
                    _icon = "✅" if _set_count else ""
                _hdr = f"{_icon} **{category}**  ·  {_progress}".strip()

                with st.expander(_hdr, expanded=False):
                    if _intro_key:
                        st.markdown(t(_intro_key))
                    if _required:
                        _required_md = ", ".join(f"`{k}`" for k in _required)
                        st.caption(
                            t("admin.settings.required_label") + ": " + _required_md
                        )
                    if _cross_refs:
                        _cross_md = ", ".join(f"`{k}`" for k in _cross_refs)
                        st.caption(
                            "ℹ️ " + t("admin.settings.cross_ref_label").format(keys=_cross_md)
                        )

                    with st.form(f"settings_form_{category}", clear_on_submit=True):
                        pending: dict[str, str] = {}
                        delete_keys: list[str] = []
                        for key, is_secret in keys:
                            current = PraxiaConfig.get(key)
                            is_required = key in _required
                            specific_help_key = _key_help_map.get(key)
                            if current is None:
                                label = (("✱ " if is_required else "") + key)
                                help_text = (
                                    t(specific_help_key) if specific_help_key
                                    else t("admin.settings.help.unset")
                                )
                                placeholder = t("admin.settings.placeholder.unchanged")
                            elif is_secret:
                                label = f"✓ {key}"
                                help_text = (
                                    t(specific_help_key) if specific_help_key
                                    else t("admin.settings.help.secret_set_masked")
                                )
                                placeholder = "********"
                            else:
                                label = f"✓ {key}  ({current})"
                                help_text = (
                                    t(specific_help_key) if specific_help_key
                                    else t("admin.settings.help.value_set").format(
                                        value=current
                                    )
                                )
                                placeholder = current
                            col_in, col_del = st.columns([5, 1])
                            with col_in:
                                new_val = st.text_input(
                                    label, value="",
                                    type="password" if is_secret else "default",
                                    placeholder=placeholder,
                                    help=help_text,
                                    key=f"setting_input_{category}_{key}",
                                )
                            with col_del:
                                if current is not None:
                                    st.markdown("&nbsp;", unsafe_allow_html=True)
                                    if st.checkbox(
                                        t("admin.settings.delete_checkbox"),
                                        value=False,
                                        key=f"setting_del_{category}_{key}",
                                        help=t("admin.settings.delete_checkbox_help"),
                                    ):
                                        delete_keys.append(key)
                            if new_val:
                                pending[key] = new_val
                        st.caption(t("admin.settings.save_hint"))
                        submit = st.form_submit_button(
                            "💾 " + t("admin.settings.save_btn"),
                            type="primary",
                            use_container_width=True,
                        )
                        if submit:
                            if actor_role not in ("admin", "unknown"):
                                st.error(t("admin.settings.role_required"))
                            elif not pending and not delete_keys:
                                st.info(t("admin.settings.no_changes"))
                            else:
                                _AZURE_MIRRORS = {
                                    "AZURE_API_KEY":     "AZURE_OPENAI_API_KEY",
                                    "AZURE_API_BASE":    "AZURE_OPENAI_ENDPOINT",
                                    "AZURE_API_VERSION": "OPENAI_API_VERSION",
                                }
                                for k, v in pending.items():
                                    PraxiaConfig.set_persistent(k, v)
                                    os.environ[k] = v
                                    # Mirror Azure-OpenAI-canonical env
                                    # vars so the openai SDK underneath
                                    # LiteLLM finds the credentials.
                                    if k in _AZURE_MIRRORS:
                                        os.environ[_AZURE_MIRRORS[k]] = v
                                    if auth is not None:
                                        auth.audit.record(
                                            actor_id=user_id,
                                            actor_role=actor_role,
                                            action="config.set",
                                            resource=f"config:{k}",
                                            metadata={
                                                "category": KNOWN_KEYS[k][0],
                                                "is_secret": KNOWN_KEYS[k][1],
                                            },
                                        )
                                for k in delete_keys:
                                    if PraxiaConfig.delete_persistent(k):
                                        os.environ.pop(k, None)
                                        if auth is not None:
                                            auth.audit.record(
                                                actor_id=user_id,
                                                actor_role=actor_role,
                                                action="config.delete",
                                                resource=f"config:{k}",
                                                metadata={
                                                    "category": KNOWN_KEYS[k][0],
                                                    "is_secret": KNOWN_KEYS[k][1],
                                                },
                                            )
                                try:
                                    st.cache_resource.clear()
                                except Exception:
                                    pass
                                if pending:
                                    st.success(t("admin.settings.saved").format(count=len(pending)))
                                if delete_keys:
                                    st.success(t("admin.settings.deleted").format(count=len(delete_keys)))
                                st.info(t("admin.settings.applied_immediately"))

    with tab_users:
        st.header("👥 User management (admin)")
        try:
            from praxia.auth import Role  # noqa: F401
            users_list = auth.users.list_all() if auth is not None else []
        except Exception as e:
            st.error(f"Auth not available: {e}")
            users_list = []

        sub_list, sub_create, sub_edit = st.tabs(["List", "Create", "Edit / Delete"])

        with sub_list:
            if users_list:
                st.table([
                    {
                        "username": u.username, "role": u.role,
                        "email": u.email or "—", "active": u.is_active,
                    }
                    for u in users_list
                ])
            else:
                st.info("No users yet.")

        with sub_create:
            with st.form("user_create_form"):
                new_username = st.text_input("Username")
                new_role = st.selectbox(
                    "Role", ["admin", "operator", "member", "viewer"],
                )
                new_email = st.text_input("Email")
                submit = st.form_submit_button("Create")
                if submit and new_username and auth is not None:
                    user, raw = auth.create_user(
                        new_username, role=new_role, email=new_email or None,
                    )
                    st.success(f"Created {user.username} (role={user.role})")
                    st.code(raw, language="text")
                    st.warning("Save this API key now — it will not be shown again.")

        with sub_edit:
            if users_list:
                target = st.selectbox("Select user", [u.username for u in users_list])
                user_target = next(
                    (u for u in users_list if u.username == target), None,
                )
                if user_target:
                    colA, colB = st.columns(2)
                    with colA:
                        new_role = st.selectbox(
                            "New role",
                            ["admin", "operator", "member", "viewer"],
                            index=["admin", "operator", "member", "viewer"].index(
                                user_target.role
                            ),
                        )
                        new_email = st.text_input(
                            "New email", value=user_target.email or "",
                        )
                        if st.button("Update") and auth is not None:
                            auth.update_user(
                                target, role=new_role,
                                email=new_email or None,
                            )
                            st.success("Updated")
                            st.rerun()
                    with colB:
                        if st.button("Rotate API key") and auth is not None:
                            new_key = auth.users.rotate_api_key(user_target.id)
                            st.code(new_key, language="text")
                        if st.button(
                            "Deactivate" if user_target.is_active else "Activate"
                        ) and auth is not None:
                            auth.update_user(target, is_active=not user_target.is_active)
                            st.success("Toggled")
                            st.rerun()
                        if st.button(
                            "🗑 Delete (cannot undo)", type="primary"
                        ) and auth is not None:
                            auth.delete_user(target)
                            st.success("Deleted")
                            st.rerun()

    with tab_connectors:
        st.header("🔌 External connectors")
        st.markdown(
            "Pull data from external systems for use as context, or push "
            "Praxia outputs back to your team's systems of record."
        )
        from praxia.connectors.registry import list_builtin

        connector_names = list_builtin()
        sel = st.selectbox("Connector", connector_names)
        op = st.radio("Operation", ["Pull", "Push"], horizontal=True)
        path = st.text_input("Path / folder ID / SOQL / app ID")

        st.caption(
            "Credentials are read from environment variables prefixed with "
            f"`PRAXIA_CONN_{sel.upper()}_*`."
        )

        if op == "Pull":
            limit = st.slider("Limit", 5, 200, 20)
            if st.button("Pull"):
                try:
                    from praxia.connectors import get_connector
                    cfg = {
                        k.replace(f"PRAXIA_CONN_{sel.upper()}_", "").lower(): v
                        for k, v in os.environ.items()
                        if k.startswith(f"PRAXIA_CONN_{sel.upper()}_")
                    }
                    items = get_connector(sel, **cfg).pull(path, limit=limit)
                    st.success(f"Pulled {len(items)} items")
                    for it in items[:5]:
                        with st.expander(f"📥 {it.name}"):
                            if isinstance(it.content, str):
                                st.text(it.content[:1000])
                            else:
                                st.text(f"<binary, {len(it.content)} bytes>")
                except Exception as e:
                    st.error(str(e))
        else:
            body = st.text_area("Body / payload (text or JSON)", height=200)
            if st.button("Push"):
                try:
                    from praxia.connectors import get_connector
                    from praxia.connectors.base import ConnectorItem
                    cfg = {
                        k.replace(f"PRAXIA_CONN_{sel.upper()}_", "").lower(): v
                        for k, v in os.environ.items()
                        if k.startswith(f"PRAXIA_CONN_{sel.upper()}_")
                    }
                    receipt = get_connector(sel, **cfg).push(
                        path, ConnectorItem(id="", name="praxia_output", content=body),
                    )
                    st.success(f"Pushed: {receipt}")
                except Exception as e:
                    st.error(str(e))

    with tab_policies:
        st.header("🛡 Resource Access Policies")
        st.markdown(
            "Control which users / roles can access connector paths, memory "
            "namespaces, prompts, and skills. Designed for enterprise IS departments."
        )
        sub_list, sub_add, sub_test = st.tabs(["List", "Add", "Test"])
        if auth:
            with sub_list:
                policies = auth.policies.list()
                if policies:
                    st.table([
                        {
                            "id": p.id[:8], "effect": p.effect,
                            "type": p.resource_type, "pattern": p.resource_pattern,
                            "actions": ",".join(p.actions),
                            "principals": ",".join(p.principals),
                            "description": p.description,
                        }
                        for p in policies
                    ])
                    target_id = st.selectbox(
                        "Remove policy by ID",
                        options=[""] + [p.id for p in policies],
                        format_func=lambda x: f"{x[:8]}…" if x else "(select)",
                    )
                    if target_id and st.button("🗑 Remove selected"):
                        if auth.policies.remove(target_id):
                            st.success(f"Removed {target_id[:8]}")
                            st.rerun()
                else:
                    st.info("No policies yet. Defaults to 'allow' when no policy matches.")
            with sub_add:
                with st.form("policy_add_form"):
                    pa_effect = st.selectbox("Effect", ["allow", "deny"])
                    pa_type = st.selectbox(
                        "Resource type",
                        ["connector", "memory", "prompt", "skill", "block", "*"],
                    )
                    pa_pattern = st.text_input(
                        "Resource pattern (glob)",
                        placeholder="box:/Confidential/*  or  kintone:42",
                    )
                    pa_actions = st.multiselect(
                        "Actions", ["read", "write", "list", "*"], default=["*"],
                    )
                    pa_principals = st.text_input(
                        "Principals (comma-separated user_ids and role:<name>)",
                        value="*",
                    )
                    pa_description = st.text_input("Description")
                    if st.form_submit_button("Add policy") and pa_pattern:
                        p = auth.policies.add(
                            effect=pa_effect, resource_type=pa_type,
                            resource_pattern=pa_pattern,
                            actions=pa_actions or ["*"],
                            principals=[
                                s.strip() for s in pa_principals.split(",") if s.strip()
                            ],
                            description=pa_description,
                        )
                        st.success(f"Added policy {p.id[:8]}")
                        st.rerun()
            with sub_test:
                with st.form("policy_test_form"):
                    pt_user = st.text_input("user_id", value="alice")
                    pt_role = st.selectbox(
                        "role", ["admin", "operator", "member", "viewer"],
                    )
                    pt_type = st.selectbox(
                        "resource_type",
                        ["connector", "memory", "prompt", "skill", "block"],
                    )
                    pt_id = st.text_input(
                        "resource_id", placeholder="box:/Praxia/specs",
                    )
                    pt_action = st.selectbox("action", ["read", "write", "list"])
                    if st.form_submit_button("Evaluate") and pt_id:
                        decision = auth.policies.evaluate(
                            user_id=pt_user, role=pt_role,
                            resource_type=pt_type, resource_id=pt_id,
                            action=pt_action,
                        )
                        if decision.allowed:
                            st.success(f"✅ Allowed — {decision.reason}")
                        else:
                            st.error(f"🚫 Denied — {decision.reason}")

    with tab_consolidate:
        st.markdown(t("consolidate.intro"))
        threshold = st.slider(t("consolidate.threshold"), 0.0, 1.0, 0.75, 0.05)
        dry_run = st.checkbox(t("consolidate.dry_run"), value=True)
        if st.button(t("consolidate.run"), type="primary"):
            loom.config.consolidation_threshold = threshold
            with st.spinner("Consolidating…"):
                report = loom.consolidate(dry_run=dry_run)
            st.json(report)

    with tab_exports:
        st.markdown(
            "Export audit logs, users, skill usage, memories, and policies for "
            "compliance, SIEM ingestion, or backups. Every export action is logged."
        )
        if auth:
            kind = st.selectbox(
                "What to export",
                [
                    "Audit log", "Users", "Skill usage",
                    "Personal memory (one user)", "All personal memories",
                    "Shared memory blocks", "Access policies",
                ],
            )
            fmt = st.selectbox("Format", ["csv", "json", "jsonl"])
            out_dir = Path(loom.config.memory_dir) / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)

            extra_input = None
            if kind == "Personal memory (one user)":
                extra_input = st.text_input("user_id", value="default-user")
            elif kind == "Skill usage":
                extra_input = st.text_input("Optional skill name filter")

            if st.button("Export"):
                ts = int(__import__("time").time())
                path: Path | list[Path]
                if kind == "Audit log":
                    path = auth.exports.export_audit(
                        output_path=out_dir / f"audit_{ts}.{fmt}", format=fmt,
                    )
                elif kind == "Users":
                    path = auth.exports.export_users(
                        output_path=out_dir / f"users_{ts}.{fmt}", format=fmt,
                    )
                elif kind == "Skill usage":
                    path = auth.exports.export_skill_usage(
                        output_path=out_dir / f"skill_usage_{ts}.{fmt}",
                        format=fmt, skill_name=extra_input or None,
                    )
                elif kind == "Personal memory (one user)":
                    path = auth.exports.export_personal_memory(
                        user_id=extra_input or "default-user",
                        output_path=out_dir / f"memory_{extra_input}_{ts}.{fmt}",
                        format=fmt,
                    )
                elif kind == "All personal memories":
                    path = auth.exports.export_all_personal_memory(
                        output_dir=out_dir / f"all_memory_{ts}", format=fmt,
                    )
                elif kind == "Shared memory blocks":
                    path = auth.exports.export_shared_memory(
                        output_path=out_dir / f"shared_{ts}.{fmt}", format=fmt,
                    )
                else:
                    path = auth.exports.export_policies(
                        output_path=out_dir / f"policies_{ts}.{fmt}", format=fmt,
                    )
                st.success(f"Exported → {path}")
                if isinstance(path, Path) and path.exists():
                    st.download_button(
                        "⬇️ Download",
                        data=path.read_bytes(),
                        file_name=path.name,
                        mime="application/octet-stream",
                    )

    with tab_about:
        st.header(t("about.h"))
        st.markdown(t("about.body"))
