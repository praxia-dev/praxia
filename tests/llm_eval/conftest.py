"""Fixtures + CLI options for the LLM eval suite."""
from __future__ import annotations

import os

import pytest


def pytest_addoption(parser):
    """Add `--update-baselines` so authors can refresh the committed baseline."""
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="LLM eval: write current scores to baselines.json instead of comparing.",
    )
    parser.addoption(
        "--llm-eval-model",
        action="store",
        default=os.getenv("PRAXIA_LLM_EVAL_MODEL", "claude"),
        help="LLM alias to evaluate against (default: claude).",
    )
    parser.addoption(
        "--llm-eval-judge",
        action="store",
        default=os.getenv("PRAXIA_LLM_EVAL_JUDGE", ""),
        help="LLM alias for the judge in LLM_JUDGE rubric (different from --llm-eval-model).",
    )


@pytest.fixture
def update_baselines(request) -> bool:
    return request.config.getoption("--update-baselines")


@pytest.fixture
def eval_model(request) -> str:
    return request.config.getoption("--llm-eval-model")


@pytest.fixture
def eval_judge(request) -> str:
    return request.config.getoption("--llm-eval-judge")


@pytest.fixture
def baseline_store():
    from tests.llm_eval.framework import BaselineStore
    return BaselineStore()


@pytest.fixture
def llm(eval_model):
    """The LLM under evaluation. Skip the test if no API key is configured."""
    from praxia import LLM

    # Skip if the chosen model can't actually run
    keys_for_alias = {
        "claude": "ANTHROPIC_API_KEY",
        "claude-sonnet": "ANTHROPIC_API_KEY",
        "claude-haiku": "ANTHROPIC_API_KEY",
        "chatgpt": "OPENAI_API_KEY",
        "gpt-4o": "OPENAI_API_KEY",
        "o1": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "gemini-flash": "GEMINI_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "qwen-72b": "DASHSCOPE_API_KEY",
    }
    required = keys_for_alias.get(eval_model)
    if required and not os.getenv(required):
        pytest.skip(f"{required} not set — cannot evaluate {eval_model!r}")
    return LLM(eval_model, temperature=0.0)


@pytest.fixture
def judge_llm(eval_judge):
    """Optional independent judge LLM (for LLM_JUDGE rubric)."""
    if not eval_judge:
        return None
    from praxia import LLM
    return LLM(eval_judge, temperature=0.0)
