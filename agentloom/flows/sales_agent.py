"""Sales-Agent-Flow — Pre-meeting research → hypothesis → FAQ → proposal outline.

Three-agent pipeline:
    1. ResearchAgent      — pull together public IR / press / industry context
    2. HypothesisAgent    — generate top-3 customer pain hypotheses
    3. ProposalAgent      — draft FAQ + proposal outline
"""
from __future__ import annotations

from agentloom.core.agent import Agent
from agentloom.core.flow import Flow, FlowStep
from agentloom.core.llm import LLM


class SalesAgentFlow(Flow):
    name = "sales_agent_flow"
    description = (
        "顧客の公開情報から仮説を立て、FAQ と提案アウトラインまでを"
        "一気通貫で生成する営業準備フロー"
    )

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()

        research_agent = Agent(
            name="research",
            role="account-research",
            llm=llm,
            system_prompt=(
                "あなたは B2B セールスのリサーチャーです。"
                "顧客名・業界・公開情報から、直近の経営トピック・"
                "業績ハイライト・人事異動・新規施策をまとめてください。"
                "出典 (URL があれば併記) を必ず示し、推測には [仮説] を付けてください。"
            ),
        )

        hypothesis_agent = Agent(
            name="hypothesis",
            role="pain-hypothesis",
            llm=llm,
            system_prompt=(
                "あなたは営業戦略アドバイザーです。"
                "提示された顧客リサーチを読み、その企業が直面しているであろう"
                "経営課題を上位3つ仮説として立て、それぞれの根拠と"
                "自社製品との接点 (1行) を併記してください。"
            ),
        )

        proposal_agent = Agent(
            name="proposal",
            role="proposal-writer",
            llm=llm,
            system_prompt=(
                "あなたは提案書ライターです。"
                "顧客リサーチと課題仮説を元に、(1) 商談 FAQ 5本、"
                "(2) 提案書アウトライン (見出し + 各章 1行サマリ) を生成してください。"
                "FAQ は 想定質問 / 推奨回答 / 根拠 の3列表で書いてください。"
            ),
        )

        self.steps = [
            FlowStep(
                name="research",
                agent=research_agent,
                inputs={
                    "customer_name": "${customer_name}",
                    "product": "${product}",
                    "additional_context": "${additional_context}",
                },
            ),
            FlowStep(
                name="hypothesis",
                agent=hypothesis_agent,
                inputs={
                    "customer_research": "${research}",
                    "product": "${product}",
                },
            ),
            FlowStep(
                name="proposal",
                agent=proposal_agent,
                inputs={
                    "customer_research": "${research}",
                    "hypotheses": "${hypothesis}",
                    "product": "${product}",
                },
            ),
        ]


__all__ = ["SalesAgentFlow"]
