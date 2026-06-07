"""Tests for the chat-driven schedule + batch agent tools.

These let the user say "every Monday at 9, summarise the docs folder"
or "for each of these 5 files, extract the action items" and the LLM
picks the right tool. We don't test LLM routing here (that's an
integration concern) — we test that the tools themselves:

1. Validate cron + prompt correctly.
2. Persist to the same on-disk store the /schedules and /batches
   routers read from, so what gets created via chat shows up in the
   Schedules / Batches tabs.
3. Fan out child Tasks for batches that complete via the existing
   threaded worker.
4. Reject empty / oversized inputs cleanly so the LLM gets a usable
   error message back.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from praxia.agent.tools import (
    _run_parallel_tasks,
    _schedule_recurring_task,
    builtin_tools,
)
from praxia.core.llm import LLMResponse


@pytest.fixture
def fake_agent(tmp_path: Path):
    """A minimal stand-in for AutonomousAgent with just the fields the
    schedule/batch handlers need (user_id, memory_dir, role).

    Pre-creates an admin user under tmp_path/auth/ so the batch workers
    don't race on `AutonomousAgent.__init__`'s bootstrap_admin step.

    In production, `praxia serve` creates the AuthManager once at server
    startup; by the time any agent runs, "admin" already exists and the
    bootstrap check short-circuits. The race only surfaces in tests where
    each fresh tmp_path has an empty auth dir and N parallel threads all
    see "no users → create admin → boom, second writer fails."
    """
    from praxia.auth.manager import AuthManager
    AuthManager(storage_dir=tmp_path / "auth")  # writes auth/users.jsonl
    agent = MagicMock()
    agent.user_id = "alice"
    agent.role = "member"
    agent.memory_dir = str(tmp_path)
    return agent


# ---------------------------------------------------------------------------
# Registration — the agent's tool registry should expose both tools so the
# LLM's function-calling layer can pick them up.
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_both_tools_registered(self):
        tools = builtin_tools()
        assert "schedule_recurring_task" in tools
        assert "run_parallel_tasks" in tools

    def test_schemas_have_required_fields(self):
        tools = builtin_tools()
        sched_schema = tools["schedule_recurring_task"].parameters_schema
        assert set(sched_schema["required"]) == {"cron", "prompt"}
        batch_schema = tools["run_parallel_tasks"].parameters_schema
        assert set(batch_schema["required"]) == {"prompts"}


# ---------------------------------------------------------------------------
# schedule_recurring_task
# ---------------------------------------------------------------------------


class TestScheduleTool:
    def test_creates_valid_schedule(self, fake_agent, tmp_path: Path):
        res = _schedule_recurring_task(
            fake_agent,
            cron="0 9 * * 1-5",
            prompt="Summarise yesterday's Documents changes.",
            label="weekday brief",
        )
        assert res["created"] is True
        assert res["schedule_id"]
        assert res["next_run_iso"]  # ISO 8601 string for the next firing
        # And it's persisted in the exact location the /schedules router
        # reads from — so the user sees it in the Schedules tab.
        path = tmp_path / "schedules" / "alice" / f"{res['schedule_id']}.json"
        assert path.exists()
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert rec["cron"] == "0 9 * * 1-5"
        assert rec["prompt"].startswith("Summarise")
        assert rec["enabled"] is True
        assert rec["args"]["label"] == "weekday brief"

    def test_rejects_empty_prompt(self, fake_agent):
        res = _schedule_recurring_task(fake_agent, cron="0 9 * * 1-5", prompt="  ")
        assert res["created"] is False
        assert "prompt" in res["error"]

    def test_rejects_invalid_cron_with_helpful_message(self, fake_agent):
        res = _schedule_recurring_task(
            fake_agent, cron="every 5 minutes", prompt="do a thing"
        )
        assert res["created"] is False
        # The error must contain examples so the LLM can self-correct
        # without another round-trip.
        assert "cron" in res["error"].lower()
        assert "Examples" in res["error"] or "examples" in res["error"]

    @pytest.mark.parametrize(
        "cron,label",
        [
            ("0 9 * * 1-5", "weekday 9am"),
            ("*/30 * * * *", "every 30 min"),
            ("0 0 1 * *", "first of month midnight"),
            ("0 8 * * 1", "Mondays 8am"),
        ],
    )
    def test_accepts_documented_examples(self, fake_agent, cron, label):
        # The tool description lists these patterns to teach the LLM —
        # if any of them are rejected by our own parser we have a
        # doc-vs-code drift.
        res = _schedule_recurring_task(fake_agent, cron=cron, prompt=label)
        assert res["created"], f"{cron!r} should parse: {res.get('error')}"

    def test_propagates_parent_llm_to_schedule_args(self, fake_agent, tmp_path: Path):
        """Regression for alpha22: when the agent schedules a recurring
        task, every cron firing creates a TaskRecord from the schedule's
        args. If model isn't lifted from the parent, the worker uses
        its hard-coded 'claude' default and breaks non-Anthropic users
        with 'Missing ANTHROPIC_API_KEY'."""
        from unittest.mock import MagicMock
        fake_llm = MagicMock()
        fake_llm.config.model = "openai/gpt-5"
        fake_agent.llm = fake_llm
        fake_agent._scout_model = "openai/gpt-5-mini"
        fake_agent._workspace_root = str(tmp_path / "work")
        fake_agent.org_id = "acme"

        res = _schedule_recurring_task(
            fake_agent,
            cron="0 9 * * 1-5",
            prompt="daily summary",
            label="dailies",
        )
        assert res["created"], res
        sched_files = list((tmp_path / "schedules" / "alice").glob("*.json"))
        assert len(sched_files) == 1
        rec = json.loads(sched_files[0].read_text(encoding="utf-8"))
        assert rec["args"].get("model") == "openai/gpt-5"
        assert rec["args"].get("scout_model") == "openai/gpt-5-mini"
        assert rec["args"].get("workspace_root") == str(tmp_path / "work")
        assert rec["args"].get("org_id") == "acme"
        assert rec["args"].get("label") == "dailies"


# ---------------------------------------------------------------------------
# run_parallel_tasks
# ---------------------------------------------------------------------------


def _stub_llm(text: str = "done") -> LLMResponse:
    return LLMResponse(
        text="",
        model="stub",
        usage={},
        raw={},
        tool_calls=[{
            "id": "c1",
            "name": "final_answer",
            "arguments": '{"answer": "' + text.replace('"', '\\"') + '"}',
        }],
    )


def _wait_until(predicate, *, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


class TestBatchTool:
    def test_rejects_empty_prompts(self, fake_agent):
        res = _run_parallel_tasks(fake_agent, prompts=[])
        assert res["created"] is False
        assert "prompts" in res["error"]

    def test_rejects_all_blank_prompts(self, fake_agent):
        res = _run_parallel_tasks(fake_agent, prompts=["", "   ", "\t"])
        assert res["created"] is False
        assert "no non-empty prompts" in res["error"]

    def test_caps_at_100(self, fake_agent):
        res = _run_parallel_tasks(fake_agent, prompts=[f"p{i}" for i in range(101)])
        assert res["created"] is False
        assert "100" in res["error"]

    def test_propagates_parent_llm_model_to_children(self, fake_agent, tmp_path: Path):
        """Regression for alpha22: batches default to model='claude' in
        the worker if no model is passed in args, which breaks every
        non-Anthropic user (OpenAI / Gemini / Azure / Ollama) with
        'Missing ANTHROPIC_API_KEY'. The handler must lift the parent
        agent's model into each child TaskRecord."""
        from unittest.mock import MagicMock
        # Wire the fake agent with a concrete (non-claude) LLM config.
        fake_llm = MagicMock()
        fake_llm.config.model = "openai/gpt-5"
        fake_agent.llm = fake_llm
        fake_agent.org_id = "acme"

        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm("ok")):
            res = _run_parallel_tasks(
                fake_agent,
                prompts=["q1", "q2"],
                label="model-prop",
            )
            assert res["created"] is True
            tasks_dir = tmp_path / "tasks" / "alice"
            files = list(tasks_dir.glob("*.json"))
            assert len(files) == 2
            for f in files:
                rec = json.loads(f.read_text(encoding="utf-8"))
                assert rec["args"].get("model") == "openai/gpt-5", (
                    "child task missing parent's model — would default to "
                    "claude and fail for non-Anthropic users"
                )
                assert rec["args"].get("org_id") == "acme"

    def test_creates_n_child_tasks_and_runs_them(self, fake_agent, tmp_path: Path):
        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm("hi")):
            res = _run_parallel_tasks(
                fake_agent,
                prompts=["question A", "question B", "question C"],
                label="trio",
            )
            assert res["created"] is True
            assert res["task_count"] == 3
            assert res["batch_id"]
            batch_path = tmp_path / "batches" / "alice" / f"{res['batch_id']}.json"
            assert batch_path.exists()
            # All children visible in the tasks store
            tasks_dir = tmp_path / "tasks" / "alice"
            assert len(list(tasks_dir.glob("*.json"))) == 3

            # And — because the handler kicks off the worker threads
            # synchronously — every child should reach "done" shortly.
            def _all_done() -> bool:
                files = list(tasks_dir.glob("*.json"))
                if len(files) != 3:
                    return False
                statuses = [json.loads(f.read_text(encoding="utf-8"))["status"] for f in files]
                return all(s == "done" for s in statuses)
            assert _wait_until(_all_done), "children never reached done"

    def test_children_carry_batch_id(self, fake_agent, tmp_path: Path):
        # Lets the UI roll a Task back up to its originating Batch.
        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm("ok")):
            res = _run_parallel_tasks(fake_agent, prompts=["a", "b"])
            assert res["created"]
            time.sleep(0.4)  # give the workers time to write started_at
            tasks_dir = tmp_path / "tasks" / "alice"
            for f in tasks_dir.glob("*.json"):
                rec = json.loads(f.read_text(encoding="utf-8"))
                assert rec["args"]["_batch_id"] == res["batch_id"]
