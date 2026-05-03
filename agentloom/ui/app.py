"""Default Streamlit UI for AgentLoom.

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

from agentloom import AgentLoom, LLM
from agentloom.core.llm import DEFAULT_ALIASES
from agentloom.flows import LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow
from agentloom.skills import BUSINESS_SKILLS

st.set_page_config(page_title="AgentLoom", page_icon="🪡", layout="wide")

# --- Sidebar: settings -----------------------------------------------------

st.sidebar.title("🪡 AgentLoom")
st.sidebar.caption("Multi-agent orchestrator with cyclic memory")

user_id = st.sidebar.text_input(
    "User ID",
    value=os.getenv("AGENTLOOM_USER_ID", "default-user"),
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
os.environ["AGENTLOOM_MEMORY_BACKEND"] = backend_choice

st.sidebar.divider()
st.sidebar.markdown(
    "📚 [README](https://github.com/your-org/agentloom)  \n"
    "🐛 [Issues](https://github.com/your-org/agentloom/issues)"
)


@st.cache_resource(show_spinner=False)
def get_loom(_user_id: str, _org_id: str, _model: str) -> AgentLoom:
    return AgentLoom(user_id=_user_id, org_id=_org_id, default_model=_model)


loom = get_loom(user_id, org_id, model_choice)

# --- Main: tabs -------------------------------------------------------------

tab_run, tab_skill, tab_memory, tab_consolidate, tab_about = st.tabs(
    ["🎬 Run Flow", "🛠 Business Skill", "🧠 Memory", "🌙 Consolidate", "ℹ About"]
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
        flow_cls: Any = SalesAgentFlow
    elif flow_name == "logic-checker":
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


# Tab 5: About -------------------------------------------------------------
with tab_about:
    st.header("ℹ AgentLoom について")
    st.markdown(
        """
**AgentLoom** は、業務特化型のマルチエージェント・オーケストレーターです。
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

[GitHub](https://github.com/your-org/agentloom) | License: Apache 2.0
        """
    )
