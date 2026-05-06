"""Evaluation tests for praxia.agent.AutonomousAgent.

Uses a programmable stub LLM so the suite never touches a real provider.
The stub returns scripted tool_calls (in OpenAI format) plus an optional
final text reply. This lets us exercise:

  - The tool-use loop (multi-step)
  - Parsing of tool_calls from LiteLLM-style responses
  - ACL denial via PolicyManager
  - Audit logging side-effects
  - read_only memory mode (write tools no-op)
  - Loop termination via `final_answer` and via empty tool_calls
  - max_steps cap
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from praxia.agent import AutonomousAgent
from praxia.agent.tools import builtin_tools


# --- LLM stub --------------------------------------------------------------


class StubLLM:
    """Mimics praxia.core.llm.LLM but returns a scripted sequence."""

    def __init__(self, scripts: list[dict[str, Any]]) -> None:
        # Each script: {"text": "...", "tool_calls": [{"id","name","arguments"}]}
        self.scripts = list(scripts)
        self.calls: list[dict[str, Any]] = []
        self.model = "stub/test"

    def complete(self, messages, *, tools=None, **kwargs):  # noqa: ANN001
        self.calls.append({"messages": messages, "tools": tools, "kwargs": kwargs})
        if not self.scripts:
            # Default safe terminator
            return SimpleNamespace(
                text="(stub fallback)",
                model=self.model,
                usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                raw=None,
                tool_calls=[],
            )
        s = self.scripts.pop(0)
        return SimpleNamespace(
            text=s.get("text", ""),
            model=self.model,
            usage={"input_tokens": 5, "output_tokens": 5, "total_tokens": 10},
            raw=None,
            tool_calls=list(s.get("tool_calls", [])),
        )


def _tc(name: str, args: dict[str, Any], call_id: str = "call_1") -> dict[str, Any]:
    return {"id": call_id, "name": name, "arguments": json.dumps(args)}


# --- Tests -----------------------------------------------------------------


def test_builtin_tools_have_complete_schemas():
    tools = builtin_tools()
    expected = {
        "search_personal_memory",
        "search_org_memory",
        "search_frozen_layer",
        "list_skills",
        "list_personal_skills",
        "list_org_skills",
        "run_skill",
        "list_connectors",
        "pull_from_connector",
        "record_fact",
        "final_answer",
    }
    assert expected.issubset(tools.keys())
    for name, t in tools.items():
        schema = t.to_litellm_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == name
        assert "parameters" in schema["function"]


def test_agent_terminates_via_final_answer(tmp_path: Path):
    llm = StubLLM([
        {
            "tool_calls": [_tc("final_answer", {"answer": "Hi from the agent."})],
        },
    ])
    agent = AutonomousAgent(
        user_id="alice",
        memory_dir=str(tmp_path),
        llm=llm,
        max_steps=3,
    )
    result = agent.run("hello")
    assert result.final_text == "Hi from the agent."
    assert result.stopped_reason == "completed"
    assert result.steps == 1
    # final_answer was the one tool call recorded
    assert [t.name for t in result.tool_calls] == ["final_answer"]


def test_agent_terminates_when_llm_emits_no_tool_calls(tmp_path: Path):
    llm = StubLLM([{"text": "Direct answer.", "tool_calls": []}])
    agent = AutonomousAgent(user_id="bob", memory_dir=str(tmp_path), llm=llm, max_steps=3)
    result = agent.run("question?")
    assert result.final_text == "Direct answer."
    assert result.tool_calls == []
    assert result.stopped_reason == "completed"


def test_agent_runs_multi_step_loop(tmp_path: Path):
    """Loop: search_personal_memory → list_skills → final_answer."""
    llm = StubLLM([
        {"tool_calls": [_tc("search_personal_memory", {"query": "Acme"})]},
        {"tool_calls": [_tc("list_skills", {})]},
        {"tool_calls": [_tc("final_answer", {"answer": "Done."})]},
    ])
    agent = AutonomousAgent(
        user_id="carol",
        memory_dir=str(tmp_path),
        llm=llm,
        max_steps=10,
    )
    result = agent.run("Tell me about Acme")
    assert result.final_text == "Done."
    assert [t.name for t in result.tool_calls] == [
        "search_personal_memory",
        "list_skills",
        "final_answer",
    ]
    # Each tool returned a non-empty result_text serialization
    for t in result.tool_calls:
        assert t.ok is True
        assert isinstance(t.result_text, str) and t.result_text


def test_agent_max_steps_cap(tmp_path: Path):
    """If the LLM never calls final_answer the loop must stop at max_steps."""
    llm = StubLLM([
        {"tool_calls": [_tc("list_skills", {}, call_id=f"c{i}")]} for i in range(20)
    ])
    agent = AutonomousAgent(
        user_id="dave",
        memory_dir=str(tmp_path),
        llm=llm,
        max_steps=3,
    )
    result = agent.run("loop forever")
    assert result.stopped_reason == "max_steps"
    assert result.steps == 3
    # Three tool calls fired before the cap kicked in
    assert len(result.tool_calls) == 3


def test_agent_record_fact_noop_in_read_only_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PRAXIA_MEMORY_MODE", "read_only")
    llm = StubLLM([
        {"tool_calls": [_tc("record_fact", {"text": "alice loves coffee"})]},
        {"tool_calls": [_tc("final_answer", {"answer": "noted"})]},
    ])
    agent = AutonomousAgent(
        user_id="alice",
        memory_dir=str(tmp_path),
        llm=llm,
        max_steps=3,
    )
    result = agent.run("remember a fact")
    rec = next(t for t in result.tool_calls if t.name == "record_fact")
    payload = json.loads(rec.result_text)
    assert payload["recorded"] is False
    assert "read_only" in payload["reason"]


def test_agent_blocks_connector_when_acl_denies(tmp_path: Path):
    from praxia.auth.manager import AuthManager

    auth = AuthManager(storage_dir=str(tmp_path / "auth"))
    auth.policies.add(
        effect="deny",
        resource_type="connector",
        resource_pattern="box:*",
        actions=["*"],
        principals=["*"],
        description="deny all box access in tests",
    )

    llm = StubLLM([
        {"tool_calls": [_tc("pull_from_connector", {"name": "box", "path": "/Confidential"})]},
        {"tool_calls": [_tc("final_answer", {"answer": "blocked"})]},
    ])
    agent = AutonomousAgent(
        user_id="alice",
        role="member",
        memory_dir=str(tmp_path),
        llm=llm,
        max_steps=3,
        auth=auth,
    )
    result = agent.run("get confidential file")
    pull = next(t for t in result.tool_calls if t.name == "pull_from_connector")
    payload = json.loads(pull.result_text)
    assert payload["ok"] is False
    assert "denied" in payload["error"]
    # Audit log captured the denial
    events = auth.audit.tail(limit=200)
    assert any(e.action == "connector.pull" and e.outcome == "denied" for e in events)


def test_agent_audit_records_run_lifecycle(tmp_path: Path):
    from praxia.auth.manager import AuthManager

    auth = AuthManager(storage_dir=str(tmp_path / "auth"))
    llm = StubLLM([{"tool_calls": [_tc("final_answer", {"answer": "ok"})]}])
    agent = AutonomousAgent(
        user_id="ed",
        memory_dir=str(tmp_path),
        llm=llm,
        max_steps=2,
        auth=auth,
    )
    agent.run("hi")
    actions = [e.action for e in auth.audit.tail(limit=100)]
    assert "agent.run.start" in actions
    assert "agent.run.end" in actions


def test_agent_handles_unknown_tool_gracefully(tmp_path: Path):
    llm = StubLLM([
        {"tool_calls": [_tc("search_unicorn", {"query": "x"})]},
        {"tool_calls": [_tc("final_answer", {"answer": "fallback"})]},
    ])
    agent = AutonomousAgent(user_id="alice", memory_dir=str(tmp_path), llm=llm, max_steps=3)
    result = agent.run("call unknown")
    bad = result.tool_calls[0]
    assert bad.ok is False
    assert "unknown tool" in bad.error
    assert result.final_text == "fallback"


def test_agent_handles_malformed_json_arguments(tmp_path: Path):
    llm = StubLLM([
        {"tool_calls": [{"id": "c1", "name": "list_skills", "arguments": "not json"}]},
        {"tool_calls": [_tc("final_answer", {"answer": "k"})]},
    ])
    agent = AutonomousAgent(user_id="alice", memory_dir=str(tmp_path), llm=llm, max_steps=3)
    result = agent.run("test")
    first = result.tool_calls[0]
    assert first.name == "list_skills"
    assert first.arguments == {}  # parser fell back to empty dict
    assert first.ok is True


def test_agent_enable_tools_filter_keeps_final_answer(tmp_path: Path):
    """`enable_tools` must always keep `final_answer`, otherwise the loop never terminates."""
    agent = AutonomousAgent(
        user_id="alice",
        memory_dir=str(tmp_path),
        llm=StubLLM([]),
        enable_tools=["search_personal_memory"],
    )
    assert "final_answer" in agent.tools
    assert "search_personal_memory" in agent.tools
    assert "pull_from_connector" not in agent.tools


@pytest.mark.parametrize("model_text", ["", "thinking..."])
def test_agent_appends_tool_messages_to_history(tmp_path: Path, model_text):
    """After each tool call we must append (assistant w/ tool_calls + tool result)."""
    llm = StubLLM([
        {"text": model_text, "tool_calls": [_tc("list_skills", {})]},
        {"tool_calls": [_tc("final_answer", {"answer": "ok"})]},
    ])
    agent = AutonomousAgent(user_id="alice", memory_dir=str(tmp_path), llm=llm, max_steps=3)
    agent.run("hi")
    # Inspect the messages on the second LLM call
    second_call_messages = llm.calls[1]["messages"]
    roles = [m["role"] for m in second_call_messages]
    # system, user, assistant (tool_calls), tool, ...
    assert roles[:4] == ["system", "user", "assistant", "tool"]
    assistant = second_call_messages[2]
    assert assistant["tool_calls"][0]["function"]["name"] == "list_skills"
    tool_msg = second_call_messages[3]
    assert tool_msg["name"] == "list_skills"
    assert tool_msg["tool_call_id"] == "call_1"
