"""LLM output-quality evaluation framework.

Different goal from `tests/evaluation/`: those tests are deterministic and
free (no LLM calls). The tests in this directory **do** call the configured
LLM and measure quality of the output. They are:

    - **Skipped by default** (`pytest -m llm_eval` to run)
    - **Deterministic given a seed** (temperature=0, fixed prompts)
    - **Measured, not asserted-equal** — output is graded against rubrics
      and a regression baseline is committed

Use cases:

    - Verify a system prompt change doesn't degrade quality
    - Confirm a new memory backend doesn't lose retrieval relevance
    - Compare LLM providers (Claude vs GPT-4o vs Gemma) on the same task
    - CI gate: fail the build if quality drops > X%

The framework provides:

    - `LLMEvalCase` — one (input, expected, rubric) triple
    - `EvalRunner` — runs cases, collects metrics
    - `BaselineStore` — persists prior scores; flags regressions
    - Built-in rubrics: hallucination rate, retrieval@k, exact-match,
      semantic similarity, structure compliance

Running:

    # All LLM eval cases (requires API keys)
    pytest tests/llm_eval -m llm_eval -v

    # One case
    pytest tests/llm_eval/test_eval_investment.py::test_q3_review

    # Update the baseline (run from a known-good state)
    pytest tests/llm_eval -m llm_eval --update-baselines

The baseline file (`tests/llm_eval/baselines.json`) is committed to git
so PRs can be flagged when scores regress.
"""
