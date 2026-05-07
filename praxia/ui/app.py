"""Default Streamlit UI for Praxia.

Layout:
    1. Login gate    — visit-time identity + (optional) API-key auth
    2. Sidebar       — brand · current user · sign-out · option-menu nav
    3. Main          — workspace for the selected nav item

Nav items (left-to-right of priority):
    🎬 Run         workflow / skill / agent — sub-tabs with explanations
    🧠 Memory      browse personal + shared blocks
    📁 Data        manage local + connector data folders
    🌙 Consolidate trigger sleep-time consolidation
    📊 Stats       dashboard
    📝 Prompts     custom-prompt CRUD + distribution
    ⚙ Admin        settings · users · connectors · policies · exports · about

The data-scope picker (which folders / memory layers to feed into the
run) lives **inside the Run workspace**, not in the sidebar — that's
where the picker is contextually used.

Language is auto-detected from browser/OS; override lives under
Admin → Settings (rarely changed, doesn't deserve sidebar real estate).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st

from praxia import Praxia, LLM
from praxia.core.llm import DEFAULT_ALIASES
from praxia.data.scopes import DataScope, ScopeRegistry
from praxia.flows import LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow
from praxia.skills import BUSINESS_SKILLS
from praxia.ui.i18n import t, detect_language, SUPPORTED, LANG_DISPLAY
from praxia.ui.responsive import inject_mobile_css

st.set_page_config(page_title="Praxia", page_icon="🪡", layout="wide")
inject_mobile_css()

# Optional dependency: streamlit-option-menu provides the icon-driven
# vertical nav. Falls back to a selectbox if not installed.
try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False


# =====================================================================
# Login gate
# =====================================================================

def _render_login() -> None:
    """Render the login form. On submit, populate session_state and rerun."""
    st.markdown(
        "<div style='max-width:480px; margin:6vh auto 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(f"# 🪡 {t('app.title').replace('🪡 ', '')}")
    st.caption(t("app.tagline"))
    st.write("")

    with st.form("praxia_login", clear_on_submit=False):
        user_id_input = st.text_input(
            t("login.user_id"),
            value=os.getenv("PRAXIA_USER_ID", ""),
            placeholder="alice",
        )
        org_id_input = st.text_input(
            t("login.org_id"),
            value="default-org",
            placeholder="default-org",
        )
        api_key_input = st.text_input(
            t("login.api_key"),
            type="password",
            help=t("login.api_key_help"),
        )
        submit = st.form_submit_button(
            t("login.submit"), type="primary", use_container_width=True
        )

        if submit:
            if not user_id_input.strip():
                st.error(t("login.user_id_required"))
            else:
                resolved_user = user_id_input.strip()
                resolved_role = "unknown"
                # If the user provided an API key, validate against the auth
                # store. The username we trust is the one returned by auth.
                if api_key_input:
                    try:
                        from praxia.auth import AuthManager
                        auth_check = AuthManager()
                        u = auth_check.authenticate(api_key=api_key_input)
                        if u is None:
                            st.error(t("login.invalid_key"))
                            st.markdown("</div>", unsafe_allow_html=True)
                            return
                        resolved_user = u.username
                        resolved_role = u.role
                    except Exception as e:
                        st.warning(f"Auth check unavailable: {e}")

                st.session_state["logged_in"] = True
                st.session_state["user_id"] = resolved_user
                st.session_state["org_id"] = (
                    org_id_input.strip() or "default-org"
                )
                st.session_state["actor_role"] = resolved_role
                st.rerun()

    st.write("")
    st.caption(t("login.dev_hint"))
    st.markdown("</div>", unsafe_allow_html=True)


if not st.session_state.get("logged_in"):
    _render_login()
    st.stop()


user_id: str = st.session_state["user_id"]
org_id: str = st.session_state["org_id"]
actor_role: str = st.session_state.get("actor_role", "unknown")


# =====================================================================
# Sidebar: brand · user · sign-out · nav
# =====================================================================

with st.sidebar:
    st.markdown(f"### {t('app.title')}")
    st.caption(f"👤 **{user_id}** · {actor_role}")
    if st.button(t("login.sign_out"), use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.divider()

    NAV_KEYS = [
        "run", "memory", "data", "consolidate",
        "dashboard", "prompts", "admin",
    ]
    if "praxia_mode" not in st.session_state:
        st.session_state["praxia_mode"] = NAV_KEYS[0]

    if HAS_OPTION_MENU:
        # Icon-driven nav via streamlit-option-menu (optional dep).
        ICON_MAP = {
            "run": "play-circle", "memory": "brain", "data": "folder",
            "consolidate": "moon", "dashboard": "bar-chart",
            "prompts": "pencil-square", "admin": "gear",
        }
        labels = [t(f"mode.{k}") for k in NAV_KEYS]
        selected_label = option_menu(
            menu_title=None,
            options=labels,
            icons=[ICON_MAP[k] for k in NAV_KEYS],
            default_index=NAV_KEYS.index(st.session_state["praxia_mode"]),
            styles={
                "container": {"padding": "0", "background-color": "transparent"},
                "icon": {"font-size": "16px"},
                "nav-link": {
                    "font-size": "14px", "padding": "10px 12px",
                    "margin": "2px 0", "border-radius": "8px",
                    "--hover-color": "rgba(201,164,86,0.08)",
                },
                "nav-link-selected": {
                    "background-color": "rgba(201,164,86,0.18)",
                    "color": "inherit", "font-weight": "600",
                },
            },
            key="praxia_nav_om",
        )
        st.session_state["praxia_mode"] = NAV_KEYS[labels.index(selected_label)]
    else:
        # Stacked vertical buttons — always-available fallback that doesn't
        # depend on streamlit-option-menu. Active item is rendered as
        # primary; others as secondary.
        for key in NAV_KEYS:
            label = t(f"mode.{key}")
            is_active = st.session_state["praxia_mode"] == key
            if st.button(
                label,
                use_container_width=True,
                type="primary" if is_active else "secondary",
                key=f"nav_btn_{key}",
            ):
                st.session_state["praxia_mode"] = key
                st.rerun()

    mode = st.session_state["praxia_mode"]


# =====================================================================
# Resolve runtime LLM + memory backend (set via Admin → Settings)
# =====================================================================

_default_model = list(DEFAULT_ALIASES.keys())[0]
model_choice: str = st.session_state.get("praxia_model", _default_model)
backend_choice: str = st.session_state.get("praxia_backend", "json")
os.environ["PRAXIA_MEMORY_BACKEND"] = backend_choice


@st.cache_resource(show_spinner=False)
def get_loom(_user_id: str, _org_id: str, _model: str) -> Praxia:
    return Praxia(user_id=_user_id, org_id=_org_id, default_model=_model)


loom = get_loom(user_id, org_id, model_choice)


# =====================================================================
# Data scope: registry + reusable picker / context-gather
# =====================================================================

scope_registry = ScopeRegistry(loom.config.memory_dir / "data")
user_scopes = scope_registry.list_for_user(user_id)


def render_scope_picker(key_prefix: str) -> list[str]:
    """Render a Data-scope multi-select inside an expander.

    Returns the list of selected custom-scope ids. Built-in scopes
    (personal/org/frozen) are reflected in session_state for callers
    that want to read them.
    """
    selected_ids: list[str] = []
    builtin: list[str] = []
    with st.expander(f"📁 {t('scope.section_h')}", expanded=False):
        st.caption(t("scope.section_intro"))
        col_b, col_c = st.columns(2)
        with col_b:
            st.markdown(f"**{t('scope.builtin_h')}**")
            if st.checkbox(t("scope.personal_memory"), value=True,
                           key=f"{key_prefix}_b_pm"):
                builtin.append("personal_memory")
            if st.checkbox(t("scope.org_memory"), value=True,
                           key=f"{key_prefix}_b_om"):
                builtin.append("org_memory")
            if st.checkbox(t("scope.frozen"), value=False,
                           key=f"{key_prefix}_b_fz"):
                builtin.append("frozen")
        with col_c:
            st.markdown(f"**{t('scope.custom_h')}**")
            if user_scopes:
                for s in user_scopes:
                    label = (
                        f"📁 {s.name}" if s.kind == "local"
                        else f"🔌 {s.name} ({s.connector})"
                    )
                    if st.checkbox(label, value=False,
                                   key=f"{key_prefix}_c_{s.id}"):
                        selected_ids.append(s.id)
            else:
                st.caption(t("scope.empty_hint"))
    st.session_state[f"praxia_scope_{key_prefix}_builtin"] = builtin
    return selected_ids


def gather_scope_context(scope_ids: list[str], max_chars: int = 20000) -> str:
    """Concatenate selected custom-scope contents as additional context.

    Local scopes: parse all files via the unified parser.
    Connector scopes: pull live at execution time.
    Truncates per-file at 5000 chars and total at max_chars.
    """
    if not scope_ids:
        return ""
    parts: list[str] = []
    used = 0
    for sid in scope_ids:
        scope = scope_registry.get(user_id, sid)
        if scope is None:
            continue
        if scope.kind == "local":
            from praxia.io.parsers import parse_file
            for f in scope_registry.list_local_files(scope):
                if used >= max_chars:
                    break
                try:
                    parsed = parse_file(f.read_bytes(), filename=f.name)
                    chunk = (
                        f"## File [{scope.name}/{f.name}]\n"
                        f"{parsed.content[:5000]}\n"
                    )
                except Exception as exc:
                    chunk = (
                        f"## File [{scope.name}/{f.name}] "
                        f"(parse error: {exc})\n"
                    )
                parts.append(chunk)
                used += len(chunk)
        elif scope.kind == "connector" and scope.connector and scope.connector_path:
            from praxia.connectors import get_connector
            cfg_prefix = f"PRAXIA_CONN_{scope.connector.upper()}_"
            cfg = {
                k.replace(cfg_prefix, "").lower(): v
                for k, v in os.environ.items()
                if k.startswith(cfg_prefix)
            }
            try:
                items = get_connector(scope.connector, **cfg).pull(
                    scope.connector_path, limit=10
                )
                for it in items:
                    if used >= max_chars:
                        break
                    body = (
                        it.content if isinstance(it.content, str)
                        else f"<binary {len(it.content)} bytes>"
                    )
                    chunk = (
                        f"## {scope.connector}:{scope.connector_path}/{it.name}\n"
                        f"{body[:5000]}\n"
                    )
                    parts.append(chunk)
                    used += len(chunk)
            except Exception as exc:
                parts.append(f"## Connector {scope.name} pull error: {exc}\n")
    return "\n\n".join(parts)


# =====================================================================
# Mode: Run (Workflow / Skill / Agent)
# =====================================================================

if mode == "run":
    st.header(t("run.h"))
    st.caption(t("run.intro"))

    tab_workflow, tab_skill, tab_agent = st.tabs([
        t("run.tab.workflow"),
        t("run.tab.skill"),
        t("run.tab.agent"),
    ])

    # ---- Workflow (multi-agent flows) -------------------------------
    with tab_workflow:
        st.markdown(t("run.workflow.what"))
        flow_name = st.selectbox(
            t("flow.pick"),
            options=["sales-agent", "logic-checker", "rag-optimizer"],
            key="wf_pick",
        )

        from praxia.io.parsers import parse_file as _parse, supported_extensions as _exts
        SUPPORTED_EXT = _exts()

        def _parse_uploaded(file) -> tuple[str, dict]:
            try:
                parsed = _parse(
                    file.getvalue() if hasattr(file, "getvalue") else file.read(),
                    filename=file.name,
                )
                return parsed.content, parsed.metadata
            except Exception as e:
                return f"[Failed to parse {file.name}: {e}]", {"error": str(e)}

        flow_inputs: dict[str, Any] = {}
        if flow_name == "sales-agent":
            flow_inputs["customer_name"] = st.text_input(
                t("flow.sales.customer_name"), placeholder="Acme Inc.",
            )
            flow_inputs["product"] = st.text_input(
                t("flow.sales.product"), placeholder="BizFlow",
            )
            flow_inputs["additional_context"] = st.text_area(
                t("flow.sales.context"), height=100,
            )
            sales_files = st.file_uploader(
                t("flow.sales.files").format(exts=", ".join(SUPPORTED_EXT)),
                type=SUPPORTED_EXT,
                accept_multiple_files=True,
                key="sales_files",
            )
            if sales_files:
                extra_text = []
                for f in sales_files:
                    content, meta = _parse_uploaded(f)
                    extra_text.append(f"## File: {f.name}\n{content[:12000]}")
                    st.caption(
                        f"📄 {f.name} · parsed {len(content):,} chars · {meta}"
                    )
                flow_inputs["additional_context"] += "\n\n" + "\n\n".join(extra_text)
                st.success(t("flow.sales.attached").format(n=len(sales_files)))
            flow_cls: Any = SalesAgentFlow

        elif flow_name == "logic-checker":
            upload_mode = st.radio(
                t("flow.input_method"),
                options=["text", "file", "voice"],
                format_func=lambda v: t(f"flow.input_method.{v}"),
                horizontal=True,
                key="lc_input_mode",
            )
            if upload_mode == "file":
                uploaded = st.file_uploader(
                    t("flow.logic.file").format(exts=", ".join(SUPPORTED_EXT)),
                    type=SUPPORTED_EXT,
                    key="logic_file",
                )
                if uploaded:
                    content, meta = _parse_uploaded(uploaded)
                    flow_inputs["document"] = content
                    st.caption(
                        f"📄 {uploaded.name} · parsed {len(content):,} chars · {meta}"
                    )
                else:
                    flow_inputs["document"] = ""
            elif upload_mode == "voice":
                audio = st.audio_input(
                    t("flow.logic.audio_record"), key="lc_audio",
                )
                if audio:
                    from praxia.io.audio import STT
                    with st.spinner(t("common.transcribing")):
                        try:
                            flow_inputs["document"] = STT().transcribe(
                                audio.getvalue(),
                                filename="recording.wav",
                                language="ja",
                            )
                            st.success(
                                t("common.transcribed").format(
                                    n=len(flow_inputs["document"])
                                )
                            )
                            st.text(flow_inputs["document"][:500])
                        except Exception as e:
                            st.error(f"STT failed: {e}")
                            flow_inputs["document"] = ""
                else:
                    flow_inputs["document"] = ""
            else:  # text
                flow_inputs["document"] = st.text_area(
                    t("flow.logic.text_input"), height=300, key="lc_text",
                )
            flow_cls = LogicCheckerFlow

        else:  # rag-optimizer
            flow_inputs["question"] = st.text_input(
                t("flow.rag.question"), key="rag_q",
            )
            st.info(t("flow.rag.retriever_note"))

            def _personal_memory_retriever(q: str) -> list[dict]:
                try:
                    hits = loom.personal_memory.search(q, limit=10)
                except Exception:
                    hits = []
                return [{"id": i, "text": h} for i, h in enumerate(hits)]

            flow_inputs["retriever"] = _personal_memory_retriever
            flow_cls = RAGOptimizationFlow

        # Data scope picker (in the Run workspace, where it's actually used)
        wf_scope_ids = render_scope_picker("workflow")
        if wf_scope_ids:
            scope_ctx = gather_scope_context(wf_scope_ids)
            if scope_ctx:
                current = flow_inputs.get("additional_context", "") or ""
                flow_inputs["additional_context"] = (
                    current + ("\n\n" if current else "") + scope_ctx
                )
                st.caption(t("data.injected").format(n=len(wf_scope_ids)))

        if st.button(
            t("flow.run_btn"), type="primary",
            disabled=not any(flow_inputs.values()),
            key="wf_run",
        ):
            with st.spinner(f"Running {flow_cls.name}…"):
                result = loom.run(flow_cls, inputs=flow_inputs)

            st.success(t("common.done"))
            st.subheader("Final Output")
            st.markdown(result.final_output)

            with st.expander(t("flow.steps_h"), expanded=False):
                for name, step_result in result.step_outputs.items():
                    st.markdown(f"### `{name}`")
                    st.markdown(step_result.output)
                    st.divider()

            st.caption(
                f"input tokens: {result.total_usage['input_tokens']} | "
                f"output tokens: {result.total_usage['output_tokens']}"
            )

    # ---- Skill (single domain skill) --------------------------------
    with tab_skill:
        st.markdown(t("run.skill.what"))

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

        # Data scope picker
        sk_scope_ids = render_scope_picker("skill")
        if sk_scope_ids and user_input:
            scope_ctx = gather_scope_context(sk_scope_ids)
            if scope_ctx:
                user_input = (
                    user_input
                    + "\n\n--- Reference data from selected Data scopes ---\n"
                    + scope_ctx
                )
                st.caption(t("data.injected").format(n=len(sk_scope_ids)))

        if st.button(
            t("flow.run_btn"), key="skill_run", type="primary",
            disabled=not user_input,
        ):
            llm = LLM(model_choice)
            skill_obj = skill_cls(llm=llm)
            with st.spinner(f"Running {skill_obj.manifest.name}…"):
                output = skill_obj.run(user_input)
            st.markdown(output)
            if loom.skill_registry:
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

    # ---- Agent (LLM-driven tool-use loop) ---------------------------
    with tab_agent:
        st.markdown(t("run.agent.what"))
        st.info(t("run.agent.coming_soon"))
        st.code('praxia agent run "your task here" --max-steps 10', language="bash")


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


# =====================================================================
# Mode: Data folders (manage local + connector scopes)
# =====================================================================

elif mode == "data":
    st.header(t("mode.data"))
    st.markdown(t("data.intro"))

    local_scopes = [s for s in user_scopes if s.kind == "local"]
    connector_scopes = [s for s in user_scopes if s.kind == "connector"]

    sub_local, sub_connector, sub_browse = st.tabs([
        t("data.tab.local"),
        t("data.tab.connector"),
        t("data.tab.browse"),
    ])

    with sub_local:
        st.caption(t("data.local.intro"))
        if local_scopes:
            for s in local_scopes:
                files = scope_registry.list_local_files(s)
                with st.expander(f"📁 {s.name} · {len(files)} files",
                                 expanded=False):
                    if s.description:
                        st.caption(s.description)
                    st.caption(f"id: `{s.id}`  ·  path: `{s.path}`")

                    for f in files:
                        col_n, col_s, col_d = st.columns([6, 2, 1])
                        col_n.text(f.name)
                        col_s.caption(f"{f.stat().st_size:,} B")
                        if col_d.button("🗑", key=f"delf_{s.id}_{f.name}"):
                            scope_registry.delete_file(s, f.name)
                            st.rerun()

                    st.divider()
                    new_files = st.file_uploader(
                        t("data.local.add_files"),
                        accept_multiple_files=True,
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
        else:
            st.info(t("data.local.empty"))

        st.divider()
        st.subheader(t("data.local.create_h"))
        with st.form("data_local_create_form", clear_on_submit=True):
            new_name = st.text_input(t("data.local.create_name"))
            new_desc = st.text_input(t("data.local.create_desc"))
            init_files = st.file_uploader(
                t("data.local.create_files"),
                accept_multiple_files=True,
                key="create_local_files",
            )
            if st.form_submit_button(t("data.local.create_btn"), type="primary"):
                if not new_name:
                    st.warning(t("data.local.create_name_required"))
                else:
                    s = scope_registry.create_local(user_id, new_name, new_desc)
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
# Mode: Consolidate
# =====================================================================

elif mode == "consolidate":
    st.header(t("consolidate.h"))
    st.markdown(t("consolidate.intro"))
    threshold = st.slider(t("consolidate.threshold"), 0.0, 1.0, 0.75, 0.05)
    dry_run = st.checkbox(t("consolidate.dry_run"), value=True)

    if st.button(t("consolidate.run")):
        loom.config.consolidation_threshold = threshold
        with st.spinner("Consolidating…"):
            report = loom.consolidate(dry_run=dry_run)
        st.json(report)


# =====================================================================
# Mode: Dashboard
# =====================================================================

elif mode == "dashboard":
    st.header(t("dashboard.h"))
    from praxia.analytics import Dashboard

    d = Dashboard(memory_dir=loom.config.memory_dir)
    scope = st.radio("Scope", ["personal", "org"], horizontal=True)
    if scope == "personal":
        s = d.personal_summary(user_id)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Flow runs", s.flow_runs)
        c2.metric("Skill runs", s.skill_runs)
        c3.metric("Memory entries", s.memory_entries)
        c4.metric("Success rate", f"{s.success_rate:.0%}")
        c5, c6, c7 = st.columns(3)
        c5.metric("Episodes", s.episodes)
        c6.metric("Outcomes", s.outcomes_recorded)
        c7.metric(
            "Tokens (in/out)",
            f"{s.total_input_tokens:,} / {s.total_output_tokens:,}",
        )
        if s.top_skills:
            st.subheader("Top skills")
            st.table([{"skill": n, "count": c} for n, c in s.top_skills])
        if s.recent_episodes:
            st.subheader("Recent episodes")
            for ep in s.recent_episodes:
                st.text(ep)
    else:
        s = d.org_summary(org_id)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Active users", s.active_users)
        c2.metric("Flow runs", s.total_flow_runs)
        c3.metric("Skill runs", s.total_skill_runs)
        c4.metric("Org success rate", f"{s.org_success_rate:.0%}")
        c5, c6, c7 = st.columns(3)
        c5.metric("Promoted blocks", s.promoted_blocks)
        c6.metric("Frozen MD files", s.frozen_files)
        c7.metric(
            "Distributed (skills/prompts)",
            f"{s.distributed_skills}/{s.distributed_prompts}",
        )
        if s.top_users:
            st.subheader("Top users")
            st.table([{"user_id": u, "events": c} for u, c in s.top_users])
        if s.top_skills:
            st.subheader("Top skills")
            st.table([{"skill": n, "count": c} for n, c in s.top_skills])


# =====================================================================
# Mode: Prompts
# =====================================================================

elif mode == "prompts":
    st.header(t("prompts.h"))
    st.caption(t("prompts.intro"))
    from praxia.skills.prompts import PromptStore

    store = PromptStore(storage_dir=loom.config.memory_dir / "prompts")
    sub_generate, sub_browse, sub_distribute = st.tabs([
        t("prompts.tab.generate"),
        t("prompts.tab.browse"),
        t("prompts.tab.distribute"),
    ])

    # ---- Generate (PromptDesigner) ---------------------------------
    with sub_generate:
        st.markdown(t("prompts.generate.intro"))

        with st.form("prompt_designer_form"):
            pd_task = st.text_area(
                t("prompts.generate.task_label"),
                placeholder=t("prompts.generate.task_placeholder"),
                height=120,
            )
            pd_col1, pd_col2 = st.columns(2)
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
                pd_output_format = st.selectbox(
                    t("prompts.generate.output_format"),
                    options=["text", "json", "markdown", "xml"],
                    index=1,
                    key="pd_output_format",
                )
            with pd_col2:
                pd_include_examples = st.checkbox(
                    t("prompts.generate.include_examples"),
                    value=True, key="pd_include_examples",
                )
                pd_constraint = st.selectbox(
                    t("prompts.generate.constraint"),
                    options=["strict", "loose"],
                    key="pd_constraint",
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

    # ---- Browse & edit (with Create-new at bottom) ------------------
    with sub_browse:
        prompts = store.list_for_user(user_id=user_id, role="member")
        if prompts:
            for p in prompts:
                with st.expander(f"📄 {p.name} [{p.scope}]", expanded=False):
                    st.caption(p.description or "—")
                    st.caption(f"tags: {', '.join(p.tags) or '—'}  ·  owner: {p.owner}")

                    if p.scope == "personal" and p.owner == user_id:
                        # Editable: render fields + save/delete
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
                        # Read-only for org / distributed scopes
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

    # ---- Distribute (admin) -----------------------------------------
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
            submit = st.form_submit_button(t("prompts.distribute.btn"), type="primary")
            if submit and d_name and d_body and (d_target_users or d_target_roles):
                saved = store.distribute(
                    name=d_name, body=d_body,
                    target_users=[u.strip() for u in d_target_users.split(",") if u.strip()] or None,
                    target_roles=d_target_roles or None,
                )
                st.success(t("prompts.distribute.saved").format(n=len(saved)))


# =====================================================================
# Mode: Admin (Settings · Users · Connectors · Policies · Exports · About)
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

    # Access gate: if users exist, only admin role can open Admin.
    if users_exist and actor_role != "admin":
        st.error(t("admin.gate.denied").format(user=user_id, role=actor_role))
        st.markdown(t("admin.gate.howto"))
        st.stop()
    if not users_exist:
        st.warning(t("admin.gate.dev_mode"))

    tab_settings, tab_users, tab_connectors, tab_policies, tab_exports, tab_about = st.tabs([
        t("admin.settings.subtab"),
        t("admin.users.subtab"),
        t("admin.connectors.subtab"),
        t("admin.policies.subtab"),
        t("admin.downloads.subtab"),
        t("admin.about.subtab"),
    ])

    # ---- Settings: language, runtime LLM/backend, persistent keys ---
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

        # Language picker (moved here from sidebar — rarely changed)
        st.subheader(t("admin.settings.language_h"))
        st.caption(t("admin.settings.language_intro"))
        current_lang = st.session_state.get("praxia_lang", detect_language())
        if current_lang not in SUPPORTED:
            current_lang = "en"
        new_lang = st.selectbox(
            t("admin.settings.language_label"),
            options=SUPPORTED,
            index=SUPPORTED.index(current_lang),
            format_func=lambda c: LANG_DISPLAY[c],
            key="settings_lang_pick",
        )
        if new_lang != current_lang:
            st.session_state["praxia_lang"] = new_lang
            st.rerun()

        st.divider()

        # Runtime: LLM model + memory backend
        st.subheader(t("admin.settings.runtime_h"))
        st.caption(t("admin.settings.runtime_intro"))

        col_m, col_b = st.columns(2)
        with col_m:
            model_options = list(DEFAULT_ALIASES.keys()) + ["custom"]
            current_model = st.session_state.get("praxia_model", _default_model)
            preset_index = (
                model_options.index(current_model)
                if current_model in DEFAULT_ALIASES
                else len(model_options) - 1
            )
            picked_model = st.selectbox(
                t("admin.settings.model_label"),
                options=model_options,
                index=preset_index,
                key="settings_model_pick",
            )
            if picked_model == "custom":
                picked_model = st.text_input(
                    t("admin.settings.model_custom"),
                    value=(
                        current_model if current_model not in DEFAULT_ALIASES
                        else "anthropic/claude-opus-4-7"
                    ),
                    key="settings_model_custom_input",
                )
        with col_b:
            backend_options = ["json", "mem0", "langmem", "letta", "zep"]
            current_backend = st.session_state.get("praxia_backend", "json")
            picked_backend = st.selectbox(
                t("admin.settings.backend_label"),
                options=backend_options,
                index=(
                    backend_options.index(current_backend)
                    if current_backend in backend_options else 0
                ),
                key="settings_backend_pick",
            )

        if st.button(
            t("admin.settings.runtime_apply"), type="primary",
            key="settings_runtime_apply",
        ):
            st.session_state["praxia_model"] = picked_model
            st.session_state["praxia_backend"] = picked_backend
            try:
                st.cache_resource.clear()
            except Exception:
                pass
            st.success(t("admin.settings.runtime_saved"))
            st.rerun()

        st.divider()

        # Persistent: KNOWN_KEYS by category
        st.subheader(t("admin.settings.persistent_h"))
        st.caption(t("admin.settings.precedence_hint"))

        def _mask_for_display(value: str) -> str:
            if len(value) <= 12:
                return "****"
            return f"{value[:4]}…{value[-4:]}"

        from collections import OrderedDict
        grouped: "OrderedDict[str, list[tuple[str, bool]]]" = OrderedDict()
        for _key, (_cat, _is_secret) in KNOWN_KEYS.items():
            grouped.setdefault(_cat, []).append((_key, _is_secret))

        for category, keys in grouped.items():
            with st.expander(
                f"**{category}**  ·  {len(keys)} {t('admin.settings.keys_label')}",
                expanded=(category == "LLM"),
            ):
                with st.form(f"settings_form_{category}", clear_on_submit=True):
                    pending: dict[str, str] = {}
                    for key, is_secret in keys:
                        current = PraxiaConfig.get(key)
                        if current is None:
                            help_text = t("admin.settings.help.unset")
                        elif is_secret:
                            help_text = t("admin.settings.help.secret_set").format(
                                masked=_mask_for_display(current)
                            )
                        else:
                            help_text = t("admin.settings.help.value_set").format(
                                value=current
                            )
                        new_val = st.text_input(
                            key, value="",
                            type="password" if is_secret else "default",
                            placeholder=t("admin.settings.placeholder.unchanged"),
                            help=help_text,
                            key=f"setting_input_{category}_{key}",
                        )
                        if new_val:
                            pending[key] = new_val
                    submit = st.form_submit_button(t("admin.settings.save_btn"))
                    if submit:
                        if actor_role not in ("admin", "unknown"):
                            st.error(t("admin.settings.role_required"))
                        elif not pending:
                            st.info(t("admin.settings.no_changes"))
                        else:
                            for k, v in pending.items():
                                PraxiaConfig.set_persistent(k, v)
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
                            st.success(t("admin.settings.saved").format(count=len(pending)))
                            st.info(t("admin.settings.restart_hint"))

    # ---- Users -----------------------------------------------------
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

    # ---- Connectors ------------------------------------------------
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

    # ---- Policies --------------------------------------------------
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
                        placeholder="box:/Confidential/*  or  kintone:42  or  salesforce:*",
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

    # ---- Exports ---------------------------------------------------
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

    # ---- About -----------------------------------------------------
    with tab_about:
        st.header(t("about.h"))
        st.markdown(t("about.body"))
