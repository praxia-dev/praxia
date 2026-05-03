"""RAG-Optimization-Flow — Self-correcting RAG with evaluation loop.

Pipeline:
    1. QueryRewriter   — generate 3 alternative queries from the user question.
    2. Retriever       — pluggable retrieval (caller-provided callable).
    3. Evaluator       — score retrieval relevance.
    4. Answerer        — synthesize an answer.
    5. Hallucination   — verify answer is grounded in retrieved chunks.

The retriever is provided by the caller via the `retriever` input — it should
be a function: `retriever(query: str) -> list[dict]` returning chunks.
"""
from __future__ import annotations

from typing import Any

from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM


class RAGOptimizationFlow(Flow):
    name = "rag_optimization_flow"
    description = (
        "クエリ拡張 → 検索 → 妥当性評価 → 回答生成 → ハルシネーション検証 を"
        "ループする自己修復型 RAG フロー"
    )

    def __init__(self, llm: LLM | None = None) -> None:
        llm = llm or LLM()

        query_rewriter = Agent(
            name="query_rewriter",
            role="query-expansion",
            llm=llm,
            system_prompt=(
                "あなたはクエリ拡張エージェントです。"
                "ユーザの質問を、検索エンジン向けに3通りに書き換えてください。"
                "(1) キーワード型, (2) 自然文型, (3) 同義語展開型。"
                "JSON 配列で返してください: [\"...\", \"...\", \"...\"]"
            ),
        )

        evaluator = Agent(
            name="evaluator",
            role="retrieval-evaluation",
            llm=llm,
            system_prompt=(
                "あなたは検索結果の妥当性評価エージェントです。"
                "検索チャンクと元の質問を読み、"
                "(1) 質問への直接的な関連性 (0-1)、"
                "(2) 不足している情報の指摘 を返してください。"
            ),
        )

        answerer = Agent(
            name="answerer",
            role="answer-synthesis",
            llm=llm,
            system_prompt=(
                "あなたは RAG 回答生成エージェントです。"
                "検索チャンクに **明示的に書かれた事実のみ** を使って回答してください。"
                "推測は禁止。引用箇所は [chunk_id] で示してください。"
                "情報が不足する場合は「情報不足」と明記してください。"
            ),
        )

        hallucination_checker = Agent(
            name="hallucination_check",
            role="hallucination-detection",
            llm=llm,
            system_prompt=(
                "あなたはハルシネーション検証エージェントです。"
                "回答中の各文を、提供された検索チャンクと照合し、"
                "(1) 根拠あり / (2) 根拠なし (ハルシネーション) を判定してください。"
                "根拠なしの文は具体的に列挙してください。"
            ),
        )

        def _retrieve(context: dict[str, Any]) -> str:
            retriever = context.get("retriever")
            queries_raw = context.get("query_rewriter", "[]")
            try:
                import json

                queries = json.loads(queries_raw)
            except Exception:
                queries = [context.get("question", "")]
            chunks: list[dict[str, Any]] = []
            if callable(retriever):
                for q in queries:
                    chunks.extend(retriever(q) or [])
            return "\n".join(
                f"[{c.get('id', i)}] {c.get('text', '')}"
                for i, c in enumerate(chunks)
            ) or "(no chunks retrieved)"

        retrieval_step = FlowStep(
            name="retrieval",
            agent=Agent(
                name="retrieval",
                role="retrieval",
                llm=llm,
                system_prompt=(
                    "あなたは取得結果を整形するだけのエージェントです。"
                    "提供されたチャンクをそのまま整形して返してください。"
                ),
            ),
            inputs={"chunks": _retrieve},
        )

        self.steps = [
            FlowStep(
                name="query_rewriter",
                agent=query_rewriter,
                inputs={"question": "${question}"},
            ),
            retrieval_step,
            FlowStep(
                name="evaluator",
                agent=evaluator,
                inputs={
                    "question": "${question}",
                    "chunks": "${retrieval}",
                },
            ),
            FlowStep(
                name="answerer",
                agent=answerer,
                inputs={
                    "question": "${question}",
                    "chunks": "${retrieval}",
                    "evaluation": "${evaluator}",
                },
            ),
            FlowStep(
                name="hallucination_check",
                agent=hallucination_checker,
                inputs={
                    "answer": "${answerer}",
                    "chunks": "${retrieval}",
                },
            ),
        ]


__all__ = ["RAGOptimizationFlow"]
