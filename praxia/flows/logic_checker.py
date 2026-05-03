"""Logic-Checker-Flow — Multi-perspective consistency review.

Three agents inspect a long-form document from independent angles:
    1. StructureAgent — extract the skeleton tree
    2. ContradictionAgent — flag internal inconsistencies and broken set-ups
    3. ReaderAgent — judge clarity and reader friction
"""
from __future__ import annotations

from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM


class LogicCheckerFlow(Flow):
    name = "logic_checker_flow"
    description = (
        "長文ドキュメント (報告書 / マニュアル / 小説) の論理整合性を"
        "3つの独立視点でレビューするフロー"
    )

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()

        structure_agent = Agent(
            name="structure",
            role="structure-extraction",
            llm=llm,
            system_prompt=(
                "あなたは構造分析エージェントです。"
                "提供された文書を読み、章立て・主要主張・前提・結論の"
                "ツリー構造を Markdown のリスト形式で抽出してください。"
                "曖昧な接続や論理の飛躍があれば [⚠ Gap] でマークしてください。"
            ),
        )

        contradiction_agent = Agent(
            name="contradiction",
            role="contradiction-detection",
            llm=llm,
            system_prompt=(
                "あなたは矛盾検知エージェントです。"
                "文書中の前後の記述で矛盾するもの・"
                "設定/前提が後段で破綻しているもの・"
                "未回収の伏線 (chekhov's gun) を検出してください。"
                "出力は: (該当箇所抜粋, 矛盾の種類, 重大度) の三列表。"
            ),
        )

        reader_agent = Agent(
            name="reader_perspective",
            role="reader-experience",
            llm=llm,
            system_prompt=(
                "あなたはターゲット読者の代弁者です。"
                "読者として、つまずきそうな箇所・分かりづらい用語・"
                "認知負荷の高い段落を指摘してください。"
                "また 1 行で読後の納得度 (10点満点) を採点してください。"
            ),
        )

        self.steps = [
            FlowStep(
                name="structure",
                agent=structure_agent,
                inputs={"document": "${document}"},
            ),
            FlowStep(
                name="contradiction",
                agent=contradiction_agent,
                inputs={
                    "document": "${document}",
                    "structure": "${structure}",
                },
            ),
            FlowStep(
                name="reader_perspective",
                agent=reader_agent,
                inputs={
                    "document": "${document}",
                    "structure": "${structure}",
                    "contradictions": "${contradiction}",
                },
            ),
        ]


__all__ = ["LogicCheckerFlow"]
