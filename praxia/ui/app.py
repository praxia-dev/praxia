"""Default Streamlit UI for Praxia.

Sidebar (frequently-changed):
    - Language + compact toggle
    - User identity (user_id / org_id)
    - Mode picker — what you're doing right now
        · Flow         : run a multi-agent flow
        · Skill        : run a single business skill
        · Memory       : browse personal + shared memory
        · Consolidate  : trigger sleep-time consolidation
        · Dashboard    : personal + org statistics
        · Prompts      : create / browse / distribute custom prompts
        · Admin        : sub-tabs for setup + governance

Main area dispatches on the chosen Mode. Admin contains 6 sub-tabs:
    Settings · Users · Connectors · Policies · Exports · About

LLM model and memory backend are now under Admin → Settings (rarely
changed at runtime, so they don't deserve sidebar real-estate).
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
from praxia.ui.i18n import t, language_selector_in_sidebar
from praxia.ui.responsive import (
    compact_mode_toggle_in_sidebar,
    inject_mobile_css,
)

st.set_page_config(page_title="Praxia", page_icon="🪡", layout="wide")
inject_mobile_css()

# === Sidebar ===============================================================

# Locale + UX (top)
language_selector_in_sidebar()
compact_mode_toggle_in_sidebar(t("sidebar.compact"))

st.sidebar.title(t("app.title"))
st.sidebar.caption(t("app.tagline"))

# Identity
user_id = st.sidebar.text_input(
    t("sidebar.user"),
    value=os.getenv("PRAXIA_USER_ID", "default-user"),
)
org_id = st.sidebar.text_input(t("sidebar.org"), value="default-org")

st.sidebar.divider()

# Mode picker — operational view (replaces the previous 11-tab strip)
MODE_OPTIONS = [
    "flow",
    "skill",
    "memory",
    "data",
    "consolidate",
    "dashboard",
    "prompts",
    "admin",
]

mode = st.sidebar.radio(
    t("sidebar.mode"),
    options=MODE_OPTIONS,
    format_func=lambda m: t(f"mode.{m}"),
    key="praxia_mode",
)

st.sidebar.divider()
st.sidebar.markdown(
    f"📚 [{t('sidebar.readme')}](https://github.com/praxia-dev/praxia)  \n"
    f"🐛 [{t('sidebar.issues')}](https://github.com/praxia-dev/praxia/issues)"
)


# === Resolve runtime LLM + backend (set via Admin → Settings) ==============

_default_model = list(DEFAULT_ALIASES.keys())[0]
model_choice = st.session_state.get("praxia_model", _default_model)
backend_choice = st.session_state.get("praxia_backend", "json")
os.environ["PRAXIA_MEMORY_BACKEND"] = backend_choice


@st.cache_resource(show_spinner=False)
def get_loom(_user_id: str, _org_id: str, _model: str) -> Praxia:
    return Praxia(user_id=_user_id, org_id=_org_id, default_model=_model)


loom = get_loom(user_id, org_id, model_choice)


# === Data scope registry + sidebar selector ================================

scope_registry = ScopeRegistry(loom.config.memory_dir / "data")
user_scopes = scope_registry.list_for_user(user_id)

st.sidebar.divider()
st.sidebar.markdown(f"**📁 {t('sidebar.scope.h')}**")

# Built-in scopes — always available
selected_builtin: list[str] = []
if st.sidebar.checkbox(t("scope.personal_memory"), value=True, key="scope_personal"):
    selected_builtin.append("personal_memory")
if st.sidebar.checkbox(t("scope.org_memory"), value=True, key="scope_org"):
    selected_builtin.append("org_memory")
if st.sidebar.checkbox(t("scope.frozen"), value=False, key="scope_frozen"):
    selected_builtin.append("frozen")

# Custom scopes (local + connector folders the user has registered)
selected_custom_ids: list[str] = []
local_scopes = [s for s in user_scopes if s.kind == "local"]
connector_scopes = [s for s in user_scopes if s.kind == "connector"]

if local_scopes:
    st.sidebar.caption(t("sidebar.scope.local_h"))
    for s in local_scopes:
        n_files = len(scope_registry.list_local_files(s))
        if st.sidebar.checkbox(
            f"📁 {s.name} ({n_files})",
            value=False,
            key=f"scope_local_{s.id}",
        ):
            selected_custom_ids.append(s.id)

if connector_scopes:
    st.sidebar.caption(t("sidebar.scope.connector_h"))
    for s in connector_scopes:
        if st.sidebar.checkbox(
            f"🔌 {s.name} ({s.connector})",
            value=False,
            key=f"scope_conn_{s.id}",
        ):
            selected_custom_ids.append(s.id)

if not user_scopes:
    st.sidebar.caption(t("sidebar.scope.empty_hint"))

st.session_state["praxia_selected_scopes"] = {
    "builtin": selected_builtin,
    "custom_ids": selected_custom_ids,
}


def _gather_scope_context(scope_ids: list[str], max_chars: int = 20000) -> str:
    """Read selected custom scopes' contents as additional execution context.

    Local scopes: parse all files via the unified parser, concatenate.
    Connector scopes: pull from the configured connector path at run time.

    Truncates per-file at 5000 chars and total at max_chars to keep token use
    bounded. Errors are surfaced as inline notes rather than raised.
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
                    chunk = f"## File [{scope.name}/{f.name}] (parse error: {exc})\n"
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
                    body = it.content if isinstance(it.content, str) else f"<binary {len(it.content)} bytes>"
                    chunk = (
                        f"## {scope.connector}:{scope.connector_path}/{it.name}\n"
                        f"{body[:5000]}\n"
                    )
                    parts.append(chunk)
                    used += len(chunk)
            except Exception as exc:
                parts.append(f"## Connector {scope.name} pull error: {exc}\n")
    return "\n\n".join(parts)


# === Mode: Flow ============================================================

if mode == "flow":
    st.header("🎬 Multi-Agent Flow を実行")

    flow_name = st.selectbox(
        "Flow を選択",
        options=["sales-agent", "logic-checker", "rag-optimizer"],
    )

    # All registered parsers — drives the file_uploader type list
    from praxia.io.parsers import parse_file as _parse, supported_extensions as _exts
    SUPPORTED_EXT = _exts()

    def _parse_uploaded(file) -> tuple[str, dict]:
        """Run an uploaded Streamlit file through the unified parser."""
        try:
            parsed = _parse(file.getvalue() if hasattr(file, "getvalue") else file.read(), filename=file.name)
            return parsed.content, parsed.metadata
        except Exception as e:
            return f"[Failed to parse {file.name}: {e}]", {"error": str(e)}

    flow_inputs: dict[str, Any] = {}
    if flow_name == "sales-agent":
        flow_inputs["customer_name"] = st.text_input("顧客名", placeholder="株式会社サンプル")
        flow_inputs["product"] = st.text_input("自社製品", placeholder="BizFlow")
        flow_inputs["additional_context"] = st.text_area("追加コンテキスト (任意)", height=100)
        sales_files = st.file_uploader(
            f"📎 補助資料 (任意): IR / プレス / 議事録 などをアップロード · 対応形式: {', '.join(SUPPORTED_EXT)}",
            type=SUPPORTED_EXT,
            accept_multiple_files=True,
            key="sales_files",
        )
        if sales_files:
            extra_text = []
            for f in sales_files:
                content, meta = _parse_uploaded(f)
                extra_text.append(f"## File: {f.name}\n{content[:12000]}")
                st.caption(f"📄 {f.name} · parsed {len(content):,} chars · {meta}")
            flow_inputs["additional_context"] += "\n\n" + "\n\n".join(extra_text)
            st.success(f"📎 Attached and parsed {len(sales_files)} file(s)")
        flow_cls: Any = SalesAgentFlow
    elif flow_name == "logic-checker":
        upload_mode = st.radio(
            "入力方法",
            ["テキスト貼り付け", "ファイルアップロード", "🎙 音声入力"],
            horizontal=True,
        )
        if upload_mode == "ファイルアップロード":
            uploaded = st.file_uploader(
                f"📎 レビュー対象ファイル · 対応形式: {', '.join(SUPPORTED_EXT)}",
                type=SUPPORTED_EXT,
                key="logic_file",
            )
            if uploaded:
                content, meta = _parse_uploaded(uploaded)
                flow_inputs["document"] = content
                st.caption(f"📄 {uploaded.name} · parsed {len(content):,} chars · {meta}")
            else:
                flow_inputs["document"] = ""
        elif upload_mode == "🎙 音声入力":
            audio = st.audio_input("マイクから録音 (ブラウザ許可必須)")
            if audio:
                from praxia.io.audio import STT
                with st.spinner("音声を文字起こし中..."):
                    try:
                        flow_inputs["document"] = STT().transcribe(
                            audio.getvalue(), filename="recording.wav", language="ja"
                        )
                        st.success(f"🎙 文字起こし完了: {len(flow_inputs['document']):,} chars")
                        st.text(flow_inputs["document"][:500])
                    except Exception as e:
                        st.error(f"STT failed: {e}")
                        flow_inputs["document"] = ""
            else:
                flow_inputs["document"] = ""
        else:
            flow_inputs["document"] = st.text_area("レビュー対象の文書", height=300)
        flow_cls = LogicCheckerFlow
    else:  # rag-optimizer
        flow_inputs["question"] = st.text_input("質問")
        st.info(
            "リトリーバは個人メモリ (`PersonalMemory.search`) を使用します。"
            "他のリトリーバを使う場合は SDK から flow.run(retriever=...) で差し替えてください。"
        )
        def _personal_memory_retriever(q: str) -> list[dict]:
            try:
                hits = loom.personal_memory.search(q, limit=10)
            except Exception:
                hits = []
            return [{"id": i, "text": h} for i, h in enumerate(hits)]
        flow_inputs["retriever"] = _personal_memory_retriever
        flow_cls = RAGOptimizationFlow

    # Inject selected Data-scope content into the flow as additional context.
    if selected_custom_ids:
        scope_ctx = _gather_scope_context(selected_custom_ids)
        if scope_ctx:
            current = flow_inputs.get("additional_context", "") or ""
            flow_inputs["additional_context"] = (
                current + ("\n\n" if current else "") + scope_ctx
            )
            st.caption(t("data.injected").format(n=len(selected_custom_ids)))

    if st.button("▶ 実行", type="primary", disabled=not any(flow_inputs.values())):
        with st.spinner(f"Running {flow_cls.name}…"):
            result = loom.run(flow_cls, inputs=flow_inputs)

        st.success("完了!")
        st.subheader("Final Output")
        st.markdown(result.final_output)

        with st.expander("🔍 各ステップの出力", expanded=False):
            for name, step_result in result.step_outputs.items():
                st.markdown(f"### `{name}`")
                st.markdown(step_result.output)
                st.divider()

        st.caption(
            f"input tokens: {result.total_usage['input_tokens']} | "
            f"output tokens: {result.total_usage['output_tokens']}"
        )


# === Mode: Skill ===========================================================

elif mode == "skill":
    st.header("🛠 Business Skill を実行")

    skill_options = {f"{s.manifest.domain} — {s.manifest.name}": s for s in BUSINESS_SKILLS}
    label = st.selectbox("Skill を選択", options=list(skill_options.keys()))
    skill_cls = skill_options[label]

    st.caption(skill_cls.manifest.description)

    # Input mode: text / file / voice
    from praxia.io.parsers import parse_file as _parse2, supported_extensions as _exts2
    SKILL_EXTS = _exts2()

    skill_input_mode = st.radio(
        "入力方法",
        ["テキスト", "📎 ファイル添付 (組合せ可)", "🎙 音声入力"],
        horizontal=True,
        key="skill_input_mode",
    )

    user_input = ""
    if skill_input_mode in ("テキスト", "📎 ファイル添付 (組合せ可)"):
        user_input = st.text_area("入力", height=200, placeholder="エージェントへの依頼内容を記入")

    if skill_input_mode == "📎 ファイル添付 (組合せ可)":
        skill_files = st.file_uploader(
            f"📎 ファイル添付: PDF / Word / PowerPoint / Excel / CSV / TXT / MD / HTML 等 · 対応: {', '.join(SKILL_EXTS)}",
            type=SKILL_EXTS,
            accept_multiple_files=True,
            key="skill_files",
        )
        if skill_files:
            attached_text: list[str] = []
            for f in skill_files:
                try:
                    parsed = _parse2(f.getvalue(), filename=f.name)
                    attached_text.append(f"## Attached file: {f.name}\n{parsed.content[:12000]}")
                    st.caption(f"📄 {f.name} · {len(parsed.content):,} chars · {parsed.metadata}")
                except Exception as e:
                    st.error(f"Failed to parse {f.name}: {e}")
            user_input = (user_input or "") + "\n\n" + "\n\n".join(attached_text)

    if skill_input_mode == "🎙 音声入力":
        audio = st.audio_input("マイクから録音", key="skill_audio")
        if audio:
            from praxia.io.audio import STT
            with st.spinner("音声を文字起こし中..."):
                try:
                    user_input = STT().transcribe(
                        audio.getvalue(), filename="skill_input.wav", language="ja"
                    )
                    st.success(f"🎙 文字起こし完了: {len(user_input):,} chars")
                    st.text_area("文字起こし結果 (編集可)", value=user_input, height=120, key="stt_edit")
                except Exception as e:
                    st.error(f"STT failed: {e}")

    enable_tts = st.checkbox("🔊 出力を音声で読み上げ (任意)", value=False, key="skill_tts")

    # Inject selected Data-scope content into the skill prompt as reference data.
    if selected_custom_ids and user_input:
        scope_ctx = _gather_scope_context(selected_custom_ids)
        if scope_ctx:
            user_input = (
                user_input
                + "\n\n--- Reference data from selected Data scopes ---\n"
                + scope_ctx
            )
            st.caption(t("data.injected").format(n=len(selected_custom_ids)))

    if st.button("▶ 実行", key="skill_run", type="primary", disabled=not user_input):
        llm = LLM(model_choice)
        skill_obj = skill_cls(llm=llm)
        with st.spinner(f"Running {skill_obj.manifest.name}…"):
            output = skill_obj.run(user_input)
        st.markdown(output)
        if loom.skill_registry:
            loom.skill_registry.log_usage(skill_name=skill_obj.manifest.name, user_id=user_id)
        if enable_tts:
            from praxia.io.audio import TTS
            try:
                with st.spinner("音声合成中..."):
                    audio_bytes = TTS().synthesize(output[:4000], voice="alloy", format="mp3")
                st.audio(audio_bytes, format="audio/mp3")
            except Exception as e:
                st.warning(f"TTS unavailable: {e}")


# === Mode: Memory ==========================================================

elif mode == "memory":
    st.header("🧠 Memory ブラウザ")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("個人メモリ (Layer 1)")
        if loom.personal_memory:
            entries = loom.personal_memory.all_entries()
            st.metric("総エントリ数", len(entries))
            search_q = st.text_input("検索", key="personal_search")
            shown = (
                loom.personal_memory.search(search_q, limit=20) if search_q else [e.text for e in entries[-20:]]
            )
            for s in shown:
                st.text(s)
                st.divider()

    with col2:
        st.subheader("共有メモリ (Layer 3)")
        if loom.shared_memory:
            blocks = loom.shared_memory.list_all()
            st.metric("ブロック数", len(blocks))
            for block in blocks:
                with st.expander(f"📦 {block.label}", expanded=False):
                    st.caption(block.description)
                    st.text(block.value)
                    st.caption(f"contributors: {', '.join(block.promoted_from)}")


# === Mode: Data folders (manage local + connector scopes) ==================

elif mode == "data":
    st.header(t("mode.data"))
    st.markdown(t("data.intro"))

    sub_local, sub_connector, sub_browse = st.tabs([
        t("data.tab.local"),
        t("data.tab.connector"),
        t("data.tab.browse"),
    ])

    # ---- Local folders ---------------------------------------------------
    with sub_local:
        st.caption(t("data.local.intro"))

        if local_scopes:
            for s in local_scopes:
                files = scope_registry.list_local_files(s)
                with st.expander(f"📁 {s.name} · {len(files)} files", expanded=False):
                    if s.description:
                        st.caption(s.description)
                    st.caption(f"id: `{s.id}`  ·  path: `{s.path}`")

                    # File list with per-file delete
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
                    if col_save.button(t("data.local.save_uploads"), key=f"save_{s.id}"):
                        if new_files:
                            saved = scope_registry.save_uploaded_files(s, new_files)
                            st.success(t("data.local.saved").format(n=len(saved)))
                            st.rerun()
                        else:
                            st.warning(t("data.local.no_files_to_save"))
                    if col_del.button(t("data.local.delete_folder"), type="secondary", key=f"delfol_{s.id}"):
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

    # ---- Connector folders ----------------------------------------------
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
                    if st.button(t("data.connector.delete"), key=f"delcon_{s.id}"):
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
                t("data.connector.create_name"), placeholder="Customer Acme"
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
                        user_id, cn_name, cn_connector, cn_path, cn_desc
                    )
                    st.success(t("data.local.created").format(name=cn_name))
                    st.rerun()

    # ---- Browse: peek at one scope's contents ---------------------------
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
            else:  # connector
                st.markdown(
                    f"**{picked.name}** ({picked.connector}: `{picked.connector_path}`)"
                )
                if st.button(t("data.browse.connector_pull"), key=f"prev_{picked.id}"):
                    from praxia.connectors import get_connector
                    cfg_prefix = f"PRAXIA_CONN_{picked.connector.upper()}_"
                    cfg = {
                        k.replace(cfg_prefix, "").lower(): v
                        for k, v in os.environ.items()
                        if k.startswith(cfg_prefix)
                    }
                    try:
                        items = get_connector(picked.connector, **cfg).pull(
                            picked.connector_path, limit=10
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


# === Mode: Consolidate =====================================================

elif mode == "consolidate":
    st.header("🌙 Sleep-time Consolidation")
    st.markdown(
        "個人メモリ → 共有メモリへの自動昇格を実行します。"
        "**dry-run** で何が昇格されるかを事前確認できます。"
    )
    threshold = st.slider("Auto-promote 閾値", 0.0, 1.0, 0.75, 0.05)
    dry_run = st.checkbox("Dry run (実際の書き込みはしない)", value=True)

    if st.button("🌙 Consolidate"):
        loom.config.consolidation_threshold = threshold
        with st.spinner("Consolidating…"):
            report = loom.consolidate(dry_run=dry_run)
        st.json(report)


# === Mode: Dashboard =======================================================

elif mode == "dashboard":
    st.header("📊 Dashboard")
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
        c7.metric("Tokens (in/out)", f"{s.total_input_tokens:,} / {s.total_output_tokens:,}")
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


# === Mode: Prompts =========================================================

elif mode == "prompts":
    st.header("📝 Custom Prompts")
    from praxia.skills.prompts import PromptStore

    store = PromptStore(storage_dir=loom.config.memory_dir / "prompts")
    sub_create, sub_browse, sub_distribute = st.tabs(
        ["Create / edit", "Browse", "Admin: distribute"]
    )

    with sub_create:
        with st.form("prompt_create_form"):
            name = st.text_input("Name", placeholder="my_sales_qualifier")
            description = st.text_input("Description")
            tags = st.text_input("Tags (comma-separated)")
            body = st.text_area("Prompt body", height=240)
            submit = st.form_submit_button("Save")
            if submit and name and body:
                store.save_personal(
                    user_id=user_id,
                    name=name,
                    body=body,
                    description=description,
                    tags=[s.strip() for s in tags.split(",") if s.strip()],
                )
                st.success(f"Saved {name}")

    with sub_browse:
        prompts = store.list_for_user(user_id=user_id, role="member")
        for p in prompts:
            with st.expander(f"📄 {p.name} [{p.scope}]", expanded=False):
                st.caption(p.description)
                st.text(p.body[:1000] + ("…" if len(p.body) > 1000 else ""))
                st.caption(f"tags: {', '.join(p.tags) or '—'} | owner: {p.owner}")

    with sub_distribute:
        st.markdown("**Admin only.** Push a curated prompt to specific users or roles.")
        with st.form("prompt_distribute_form"):
            d_name = st.text_input("Name", key="dn")
            d_body = st.text_area("Body", height=200, key="db")
            d_target_users = st.text_input("Target user IDs (comma-separated)", key="dtu")
            d_target_roles = st.multiselect(
                "Target roles", ["admin", "operator", "member", "viewer"], key="dtr"
            )
            submit = st.form_submit_button("Distribute")
            if submit and d_name and d_body and (d_target_users or d_target_roles):
                saved = store.distribute(
                    name=d_name,
                    body=d_body,
                    target_users=[u.strip() for u in d_target_users.split(",") if u.strip()] or None,
                    target_roles=d_target_roles or None,
                )
                st.success(f"Distributed to {len(saved)} target(s)")


# === Mode: Admin (sub-tabs) ================================================

elif mode == "admin":
    st.header(t("admin.header"))

    # Auth manager — needed by most admin sub-tabs.
    try:
        from praxia.auth import AuthManager
        auth = AuthManager(storage_dir=loom.config.memory_dir / "auth")
    except Exception as e:
        st.error(f"Auth not available: {e}")
        auth = None

    # Resolve actor identity + role from the sidebar's user_id (advisory only —
    # UI auth is not enforced; audit log captures whoever is at the keyboard).
    actor_role = "unknown"
    if auth is not None:
        try:
            _u = auth.users.get_by_username(user_id)
            if _u is not None:
                actor_role = _u.role
        except Exception:
            pass

    tab_settings, tab_users, tab_connectors, tab_policies, tab_exports, tab_about = st.tabs([
        t("admin.settings.subtab"),
        t("admin.users.subtab"),
        t("admin.connectors.subtab"),
        t("admin.policies.subtab"),
        t("admin.downloads.subtab"),
        t("admin.about.subtab"),
    ])

    # --- Settings: runtime knobs (LLM/backend) + KNOWN_KEYS config -----
    with tab_settings:
        from praxia.config import KNOWN_KEYS, PraxiaConfig

        st.markdown(t("admin.settings.intro"))

        if actor_role == "admin":
            st.success(t("admin.settings.role_ok").format(user=user_id))
        elif actor_role == "unknown":
            st.warning(t("admin.settings.role_unknown").format(user=user_id))
        else:
            st.error(t("admin.settings.role_blocked").format(user=user_id, role=actor_role))

        # ---- Runtime: LLM model + memory backend (moved from sidebar) ----
        st.subheader(t("admin.settings.runtime_h"))
        st.caption(t("admin.settings.runtime_intro"))

        col_m, col_b = st.columns(2)
        with col_m:
            model_options = list(DEFAULT_ALIASES.keys()) + ["custom"]
            current_model = st.session_state.get("praxia_model", _default_model)
            preset_index = (
                model_options.index(current_model)
                if current_model in DEFAULT_ALIASES
                else len(model_options) - 1  # "custom"
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
                    value=current_model if current_model not in DEFAULT_ALIASES else "anthropic/claude-opus-4-7",
                    key="settings_model_custom_input",
                )
        with col_b:
            backend_options = ["json", "mem0", "langmem", "letta", "zep"]
            current_backend = st.session_state.get("praxia_backend", "json")
            picked_backend = st.selectbox(
                t("admin.settings.backend_label"),
                options=backend_options,
                index=backend_options.index(current_backend) if current_backend in backend_options else 0,
                key="settings_backend_pick",
            )

        if st.button(t("admin.settings.runtime_apply"), type="primary", key="settings_runtime_apply"):
            st.session_state["praxia_model"] = picked_model
            st.session_state["praxia_backend"] = picked_backend
            # Force loom to re-init with new model/backend on next rerun.
            try:
                st.cache_resource.clear()
            except Exception:
                pass
            st.success(t("admin.settings.runtime_saved"))
            st.rerun()

        st.divider()

        # ---- Persistent: KNOWN_KEYS by category ----
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
                            help_text = t("admin.settings.help.secret_set").format(masked=_mask_for_display(current))
                        else:
                            help_text = t("admin.settings.help.value_set").format(value=current)
                        new_val = st.text_input(
                            key,
                            value="",
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

    # --- Users (formerly Tab 7) ----------------------------------------
    with tab_users:
        st.header("👥 User management (admin)")
        try:
            from praxia.auth import Role  # noqa: F401  (re-export check)
            users_list = auth.users.list_all() if auth is not None else []
        except Exception as e:
            st.error(f"Auth not available: {e}")
            users_list = []

        sub_list, sub_create, sub_edit = st.tabs(["List", "Create", "Edit / Delete"])

        with sub_list:
            if users_list:
                st.table(
                    [
                        {
                            "username": u.username,
                            "role": u.role,
                            "email": u.email or "—",
                            "active": u.is_active,
                        }
                        for u in users_list
                    ]
                )
            else:
                st.info("No users yet.")

        with sub_create:
            with st.form("user_create_form"):
                new_username = st.text_input("Username")
                new_role = st.selectbox("Role", ["admin", "operator", "member", "viewer"])
                new_email = st.text_input("Email")
                submit = st.form_submit_button("Create")
                if submit and new_username and auth is not None:
                    user, raw = auth.create_user(new_username, role=new_role, email=new_email or None)
                    st.success(f"Created {user.username} (role={user.role})")
                    st.code(raw, language="text")
                    st.warning("Save this API key now — it will not be shown again.")

        with sub_edit:
            if users_list:
                target = st.selectbox("Select user", [u.username for u in users_list])
                user_target = next((u for u in users_list if u.username == target), None)
                if user_target:
                    colA, colB = st.columns(2)
                    with colA:
                        new_role = st.selectbox(
                            "New role",
                            ["admin", "operator", "member", "viewer"],
                            index=["admin", "operator", "member", "viewer"].index(user_target.role),
                        )
                        new_email = st.text_input("New email", value=user_target.email or "")
                        if st.button("Update") and auth is not None:
                            auth.update_user(target, role=new_role, email=new_email or None)
                            st.success("Updated")
                            st.rerun()
                    with colB:
                        if st.button("Rotate API key") and auth is not None:
                            new_key = auth.users.rotate_api_key(user_target.id)
                            st.code(new_key, language="text")
                        if st.button("Deactivate" if user_target.is_active else "Activate") and auth is not None:
                            auth.update_user(target, is_active=not user_target.is_active)
                            st.success("Toggled")
                            st.rerun()
                        if st.button("🗑 Delete (cannot undo)", type="primary") and auth is not None:
                            auth.delete_user(target)
                            st.success("Deleted")
                            st.rerun()

    # --- Connectors (formerly Tab 8) -----------------------------------
    with tab_connectors:
        st.header("🔌 External connectors")
        st.markdown(
            "Pull data from external systems for use as context, or push Praxia "
            "outputs back to your team's systems of record."
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
                        path, ConnectorItem(id="", name="praxia_output", content=body)
                    )
                    st.success(f"Pushed: {receipt}")
                except Exception as e:
                    st.error(str(e))

    # --- Policies (formerly Tab 9) -------------------------------------
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
                    st.table(
                        [
                            {
                                "id": p.id[:8],
                                "effect": p.effect,
                                "type": p.resource_type,
                                "pattern": p.resource_pattern,
                                "actions": ",".join(p.actions),
                                "principals": ",".join(p.principals),
                                "description": p.description,
                            }
                            for p in policies
                        ]
                    )
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
                        "Resource type", ["connector", "memory", "prompt", "skill", "block", "*"]
                    )
                    pa_pattern = st.text_input(
                        "Resource pattern (glob)",
                        placeholder="box:/Confidential/*  or  kintone:42  or  salesforce:*",
                    )
                    pa_actions = st.multiselect("Actions", ["read", "write", "list", "*"], default=["*"])
                    pa_principals = st.text_input(
                        "Principals (comma-separated user_ids and role:<name>)",
                        value="*",
                    )
                    pa_description = st.text_input("Description")
                    if st.form_submit_button("Add policy") and pa_pattern:
                        p = auth.policies.add(
                            effect=pa_effect,
                            resource_type=pa_type,
                            resource_pattern=pa_pattern,
                            actions=pa_actions or ["*"],
                            principals=[s.strip() for s in pa_principals.split(",") if s.strip()],
                            description=pa_description,
                        )
                        st.success(f"Added policy {p.id[:8]}")
                        st.rerun()

            with sub_test:
                with st.form("policy_test_form"):
                    pt_user = st.text_input("user_id", value="alice")
                    pt_role = st.selectbox("role", ["admin", "operator", "member", "viewer"])
                    pt_type = st.selectbox(
                        "resource_type", ["connector", "memory", "prompt", "skill", "block"]
                    )
                    pt_id = st.text_input(
                        "resource_id", placeholder="box:/Praxia/specs"
                    )
                    pt_action = st.selectbox("action", ["read", "write", "list"])
                    if st.form_submit_button("Evaluate") and pt_id:
                        decision = auth.policies.evaluate(
                            user_id=pt_user, role=pt_role,
                            resource_type=pt_type, resource_id=pt_id, action=pt_action,
                        )
                        if decision.allowed:
                            st.success(f"✅ Allowed — {decision.reason}")
                        else:
                            st.error(f"🚫 Denied — {decision.reason}")

    # --- Exports (formerly the Admin Downloads sub-tab) ----------------
    with tab_exports:
        st.markdown(
            "Export audit logs, users, skill usage, memories, and policies for "
            "compliance, SIEM ingestion, or backups. Every export action is logged."
        )
        if auth:
            kind = st.selectbox(
                "What to export",
                [
                    "Audit log",
                    "Users",
                    "Skill usage",
                    "Personal memory (one user)",
                    "All personal memories",
                    "Shared memory blocks",
                    "Access policies",
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
                    path = auth.exports.export_audit(output_path=out_dir / f"audit_{ts}.{fmt}", format=fmt)
                elif kind == "Users":
                    path = auth.exports.export_users(output_path=out_dir / f"users_{ts}.{fmt}", format=fmt)
                elif kind == "Skill usage":
                    path = auth.exports.export_skill_usage(
                        output_path=out_dir / f"skill_usage_{ts}.{fmt}",
                        format=fmt,
                        skill_name=extra_input or None,
                    )
                elif kind == "Personal memory (one user)":
                    path = auth.exports.export_personal_memory(
                        user_id=extra_input or "default-user",
                        output_path=out_dir / f"memory_{extra_input}_{ts}.{fmt}",
                        format=fmt,
                    )
                elif kind == "All personal memories":
                    path = auth.exports.export_all_personal_memory(
                        output_dir=out_dir / f"all_memory_{ts}", format=fmt
                    )
                elif kind == "Shared memory blocks":
                    path = auth.exports.export_shared_memory(
                        output_path=out_dir / f"shared_{ts}.{fmt}", format=fmt
                    )
                else:  # Access policies
                    path = auth.exports.export_policies(
                        output_path=out_dir / f"policies_{ts}.{fmt}", format=fmt
                    )
                st.success(f"Exported → {path}")
                if isinstance(path, Path) and path.exists():
                    st.download_button(
                        "⬇️ Download",
                        data=path.read_bytes(),
                        file_name=path.name,
                        mime="application/octet-stream",
                    )

    # --- About (formerly Tab 11) ---------------------------------------
    with tab_about:
        st.header("ℹ Praxia について")
        st.markdown(
            """
**Praxia** は、業務特化型のマルチエージェント・オーケストレーターです。
個人で利用するだけで暗黙知が自動蓄積され、有効なものだけが組織知へ昇格する
**5層メモリ循環機構**を備えています。

#### サポート LLM
- Anthropic Claude (Opus / Sonnet / Haiku)
- OpenAI ChatGPT (GPT-4o / o1)
- Google Gemini (2.0 Pro / Flash)
- Alibaba Qwen (API: dashscope / Local: Ollama)
- 他、LiteLLM 対応の全プロバイダ

#### 同梱業務スキル
- 投資 / 営業 / 設計 / 購買 / 特許 / 法務

#### LTM バックエンド
- Mem0 (推奨) / LangMem / Letta / Zep / JSON

[GitHub](https://github.com/praxia-dev/praxia) | License: Apache 2.0
            """
        )
