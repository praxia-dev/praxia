"""Default Streamlit UI for Praxia.

Tabs:
    1. Run Flow      — pick a flow + LLM, fill inputs, see step-by-step output
    2. Business Skill — invoke one of the 6 default business skills
    3. Memory        — browse/search personal memory & shared blocks
    4. Consolidate   — trigger sleep-time consolidation (dry-run by default)
    5. Settings      — pick LLM provider, memory backend
"""
from __future__ import annotations

import os
from typing import Any

import streamlit as st

from praxia import Praxia, LLM
from praxia.core.llm import DEFAULT_ALIASES
from praxia.flows import LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow
from praxia.skills import BUSINESS_SKILLS

st.set_page_config(page_title="Praxia", page_icon="🪡", layout="wide")

# --- Sidebar: settings -----------------------------------------------------

st.sidebar.title("🪡 Praxia")
st.sidebar.caption("Multi-agent orchestrator with cyclic memory")

user_id = st.sidebar.text_input(
    "User ID",
    value=os.getenv("PRAXIA_USER_ID", "default-user"),
    help="個人メモリの namespace",
)
org_id = st.sidebar.text_input("Org ID", value="default-org")

model_options = list(DEFAULT_ALIASES.keys()) + ["custom"]
model_choice = st.sidebar.selectbox(
    "LLM Model",
    options=model_options,
    index=0,
    help="Claude / ChatGPT / Gemini / Qwen から選択。custom は自由入力。",
)
if model_choice == "custom":
    model_choice = st.sidebar.text_input("Custom model string", value="anthropic/claude-opus-4-7")

backend_choice = st.sidebar.selectbox(
    "Memory Backend",
    options=["json", "mem0", "langmem", "letta", "zep"],
    index=0,
    help="LTM 実装を選択 (Mem0 推奨)",
)
os.environ["PRAXIA_MEMORY_BACKEND"] = backend_choice

st.sidebar.divider()
st.sidebar.markdown(
    "📚 [README](https://github.com/your-org/praxia)  \n"
    "🐛 [Issues](https://github.com/your-org/praxia/issues)"
)


@st.cache_resource(show_spinner=False)
def get_loom(_user_id: str, _org_id: str, _model: str) -> Praxia:
    return Praxia(user_id=_user_id, org_id=_org_id, default_model=_model)


loom = get_loom(user_id, org_id, model_choice)

# --- Main: tabs -------------------------------------------------------------

(
    tab_run, tab_skill, tab_memory, tab_consolidate, tab_dashboard,
    tab_prompts, tab_users, tab_connectors, tab_policies, tab_admin, tab_about,
) = st.tabs(
    [
        "🎬 Run Flow",
        "🛠 Skill",
        "🧠 Memory",
        "🌙 Consolidate",
        "📊 Dashboard",
        "📝 Prompts",
        "👥 Users",
        "🔌 Connectors",
        "🛡 Policies",
        "💾 Admin",
        "ℹ About",
    ]
)


# Tab 1: Run Flow ----------------------------------------------------------
with tab_run:
    st.header("🎬 Multi-Agent Flow を実行")

    flow_name = st.selectbox(
        "Flow を選択",
        options=["sales-agent", "logic-checker", "rag-optimizer"],
    )

    flow_inputs: dict[str, Any] = {}
    if flow_name == "sales-agent":
        flow_inputs["customer_name"] = st.text_input("顧客名", placeholder="株式会社サンプル")
        flow_inputs["product"] = st.text_input("自社製品", placeholder="BizFlow")
        flow_inputs["additional_context"] = st.text_area("追加コンテキスト (任意)", height=100)
        # Local file upload for additional context
        sales_files = st.file_uploader(
            "📎 補助資料 (任意): IR / プレス / 議事録 などをアップロード",
            type=["txt", "md", "pdf", "csv", "json"],
            accept_multiple_files=True,
            key="sales_files",
        )
        if sales_files:
            extra_text = []
            for f in sales_files:
                try:
                    content = f.read().decode("utf-8", errors="replace")
                except Exception:
                    content = f"[binary {f.name}, {f.size} bytes — provide a text/PDF parser]"
                extra_text.append(f"## File: {f.name}\n{content[:8000]}")
            flow_inputs["additional_context"] += "\n\n" + "\n\n".join(extra_text)
            st.success(f"📎 Attached {len(sales_files)} file(s)")
        flow_cls: Any = SalesAgentFlow
    elif flow_name == "logic-checker":
        # Allow either text paste OR file upload
        upload_mode = st.radio("入力方法", ["テキスト貼り付け", "ファイルアップロード"], horizontal=True)
        if upload_mode == "ファイルアップロード":
            uploaded = st.file_uploader(
                "📎 レビュー対象ファイル (.md / .txt / .py / その他テキスト)",
                type=["md", "txt", "py", "ts", "js", "rst", "html", "json", "yaml", "yml"],
                key="logic_file",
            )
            if uploaded:
                try:
                    flow_inputs["document"] = uploaded.read().decode("utf-8", errors="replace")
                    st.caption(f"📄 {uploaded.name} · {len(flow_inputs['document']):,} chars")
                except Exception as e:
                    st.error(f"Failed to read file: {e}")
                    flow_inputs["document"] = ""
            else:
                flow_inputs["document"] = ""
        else:
            flow_inputs["document"] = st.text_area("レビュー対象の文書", height=300)
        flow_cls = LogicCheckerFlow
    else:  # rag-optimizer
        flow_inputs["question"] = st.text_input("質問")
        st.info(
            "RAG フローはリトリーバを別途設定する必要があります。"
            "簡易デモではダミーリトリーバを使用します。"
        )
        flow_inputs["retriever"] = lambda q: [{"id": 1, "text": f"(stub chunk for: {q})"}]
        flow_cls = RAGOptimizationFlow

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


# Tab 2: Business Skills ---------------------------------------------------
with tab_skill:
    st.header("🛠 Business Skill を実行")

    skill_options = {f"{s.manifest.domain} — {s.manifest.name}": s for s in BUSINESS_SKILLS}
    label = st.selectbox("Skill を選択", options=list(skill_options.keys()))
    skill_cls = skill_options[label]

    st.caption(skill_cls.manifest.description)
    user_input = st.text_area("入力", height=200, placeholder="エージェントへの依頼内容を記入")

    # Optional file attachment(s)
    skill_files = st.file_uploader(
        "📎 ファイル添付 (任意): 契約書・仕様書・財務資料などを添付すると入力に追記されます",
        type=["txt", "md", "pdf", "csv", "json", "yaml", "yml", "html"],
        accept_multiple_files=True,
        key="skill_files",
    )
    if skill_files:
        attached_text: list[str] = []
        for f in skill_files:
            try:
                body = f.read().decode("utf-8", errors="replace")
            except Exception:
                body = f"[binary {f.name}, {f.size} bytes]"
            attached_text.append(f"## Attached file: {f.name}\n{body[:8000]}")
        user_input = (user_input or "") + "\n\n" + "\n\n".join(attached_text)
        st.caption(f"📎 {len(skill_files)} file(s) attached, total {sum(len(t) for t in attached_text):,} chars")

    if st.button("▶ 実行", key="skill_run", type="primary", disabled=not user_input):
        llm = LLM(model_choice)
        skill_obj = skill_cls(llm=llm)
        with st.spinner(f"Running {skill_obj.manifest.name}…"):
            output = skill_obj.run(user_input)
        st.markdown(output)
        if loom.skill_registry:
            loom.skill_registry.log_usage(skill_name=skill_obj.manifest.name, user_id=user_id)


# Tab 3: Memory ------------------------------------------------------------
with tab_memory:
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


# Tab 4: Consolidate -------------------------------------------------------
with tab_consolidate:
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


# Tab 5: Dashboard -------------------------------------------------------
with tab_dashboard:
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

# Tab 6: Prompts ---------------------------------------------------------
with tab_prompts:
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
                    tags=[t.strip() for t in tags.split(",") if t.strip()],
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

# Tab 7: User management -------------------------------------------------
with tab_users:
    st.header("👥 User management (admin)")
    try:
        from praxia.auth import AuthManager, Role
        auth = AuthManager(storage_dir=loom.config.memory_dir / "auth")
        users_list = auth.users.list_all()
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
            if submit and new_username:
                user, raw = auth.create_user(new_username, role=new_role, email=new_email or None)
                st.success(f"Created {user.username} (role={user.role})")
                st.code(raw, language="text")
                st.warning("Save this API key now — it will not be shown again.")

    with sub_edit:
        if users_list:
            target = st.selectbox("Select user", [u.username for u in users_list])
            t = next((u for u in users_list if u.username == target), None)
            if t:
                colA, colB = st.columns(2)
                with colA:
                    new_role = st.selectbox(
                        "New role",
                        ["admin", "operator", "member", "viewer"],
                        index=["admin", "operator", "member", "viewer"].index(t.role),
                    )
                    new_email = st.text_input("New email", value=t.email or "")
                    if st.button("Update"):
                        auth.update_user(target, role=new_role, email=new_email or None)
                        st.success("Updated")
                        st.rerun()
                with colB:
                    if st.button("Rotate API key"):
                        new_key = auth.users.rotate_api_key(t.id)
                        st.code(new_key, language="text")
                    if st.button("Deactivate" if t.is_active else "Activate"):
                        auth.update_user(target, is_active=not t.is_active)
                        st.success("Toggled")
                        st.rerun()
                    if st.button("🗑 Delete (cannot undo)", type="primary"):
                        auth.delete_user(target)
                        st.success("Deleted")
                        st.rerun()

# Tab 8: Connectors ------------------------------------------------------
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
                import os
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
                import os
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

# Tab 9: Policies (admin / IS dept) -------------------------------------
with tab_policies:
    st.header("🛡 Resource Access Policies")
    st.markdown(
        "Control which users / roles can access connector paths, memory "
        "namespaces, prompts, and skills. Designed for enterprise IS departments."
    )
    try:
        from praxia.auth import AuthManager
        auth = AuthManager(storage_dir=loom.config.memory_dir / "auth")
    except Exception as e:
        st.error(f"Auth not available: {e}")
        auth = None

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

# Tab 10: Admin downloads ----------------------------------------------
with tab_admin:
    st.header("💾 Admin Downloads")
    st.markdown(
        "Export audit logs, users, skill usage, memories, and policies for "
        "compliance, SIEM ingestion, or backups. Every export action is logged."
    )
    try:
        from praxia.auth import AuthManager
        auth = AuthManager(storage_dir=loom.config.memory_dir / "auth")
    except Exception as e:
        st.error(f"Auth not available: {e}")
        auth = None

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

# Tab 11: About ---------------------------------------------------------
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

[GitHub](https://github.com/your-org/praxia) | License: Apache 2.0
        """
    )
