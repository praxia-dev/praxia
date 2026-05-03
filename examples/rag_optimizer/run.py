"""RAG-Optimization-Flow demo with a tiny in-memory retriever."""
from __future__ import annotations

from praxia import Praxia
from praxia.flows import RAGOptimizationFlow

CORPUS = [
    {"id": "doc1", "text": "Praxia は Apache 2.0 ライセンスで配布されています。"},
    {"id": "doc2", "text": "Praxia は Mem0 / LangMem / Letta / Zep / JSON の LTM バックエンドを選択できます。"},
    {"id": "doc3", "text": "Praxia は Qwen / ChatGPT / Gemini / Claude を含む主要 LLM をサポートします。"},
    {"id": "doc4", "text": "Sleep-time Consolidation は個人メモリを組織メモリへ自動昇格させます。"},
]


def naive_retriever(query: str) -> list[dict]:
    """Return the 2 most-overlapping documents."""
    terms = {t.lower() for t in query.split() if len(t) > 1}
    scored = []
    for doc in CORPUS:
        score = sum(1 for t in terms if t in doc["text"].lower())
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:2]]


def main() -> None:
    loom = Praxia(user_id="charlie", default_model="auto")
    result = loom.run(
        RAGOptimizationFlow,
        inputs={
            "question": "Praxia はどのライセンスで配布されていますか?",
            "retriever": naive_retriever,
        },
    )
    print("\n=== Hallucination check ===\n")
    print(result.final_output)
    print("\n=== Generated answer ===\n")
    print(result.step_outputs["answerer"].output)


if __name__ == "__main__":
    main()
