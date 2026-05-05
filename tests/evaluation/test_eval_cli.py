"""CLI smoke tests — every major command runs and returns exit 0 for --help.

This catches regressions where a command silently breaks (e.g., import
error, typer signature mismatch) without requiring real LLM / connector
calls.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.evaluation


@pytest.fixture(autouse=True)
def _utf8_io():
    """Force UTF-8 IO on Windows so rich-formatted help text doesn't crash."""
    os.environ["PYTHONIOENCODING"] = "utf-8"


class TestCLIHelp:
    @pytest.mark.parametrize(
        "args",
        [
            ["--help"],
            ["init", "--help"],
            ["run", "--help"],
            ["list", "--help"],
            ["consolidate", "--help"],
            ["freeze", "--help"],
            ["ui", "--help"],
            ["serve", "--help"],
            ["skill", "--help"],
            ["user", "--help"],
            ["prompt", "--help"],
            ["connector", "--help"],
            ["oauth", "--help"],
            ["policy", "--help"],
            ["memory", "--help"],
            ["admin", "--help"],
            ["config", "--help"],
            ["export", "--help"],
        ],
    )
    def test_help_returns_zero(self, args):
        from typer.testing import CliRunner
        from praxia.cli.main import app

        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, (
            f"`praxia {' '.join(args)}` exited {result.exit_code}\n{result.stdout}"
        )

    @pytest.mark.parametrize(
        "args",
        [
            # Sub-sub-help
            ["user", "create", "--help"],
            ["user", "list", "--help"],
            ["user", "delete", "--help"],
            ["skill", "run", "--help"],
            ["skill", "promote", "--help"],
            ["skill", "distribute", "--help"],
            ["connector", "list", "--help"],
            ["connector", "pull", "--help"],
            ["connector", "push", "--help"],
            ["oauth", "start", "--help"],
            ["oauth", "list", "--help"],
            ["oauth", "revoke", "--help"],
            ["policy", "add", "--help"],
            ["policy", "list", "--help"],
            ["policy", "remove", "--help"],
            ["policy", "test", "--help"],
            ["memory", "mode", "--help"],
            ["memory", "backend", "--help"],
            ["memory", "show", "--help"],
            ["admin", "memory-policy-show", "--help"],
            ["admin", "memory-policy-set", "--help"],
            ["admin", "export-audit", "--help"],
            ["admin", "export-users", "--help"],
            ["admin", "export-memory", "--help"],
            ["admin", "export-policies", "--help"],
            ["admin", "export-shared-memory", "--help"],
            ["config", "show", "--help"],
            ["config", "get", "--help"],
            ["config", "set", "--help"],
            ["config", "init", "--help"],
            ["config", "path", "--help"],
            ["prompt", "create", "--help"],
            ["prompt", "list", "--help"],
            ["prompt", "distribute", "--help"],
        ],
    )
    def test_subcommand_help_returns_zero(self, args):
        from typer.testing import CliRunner
        from praxia.cli.main import app

        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, (
            f"`praxia {' '.join(args)}` exited {result.exit_code}\n{result.stdout}"
        )


class TestCLIList:
    def test_list_models_shows_all_aliases(self):
        from typer.testing import CliRunner
        from praxia.cli.main import app

        result = CliRunner().invoke(app, ["list", "models"])
        assert result.exit_code == 0
        # Spot check important aliases
        for needed in ("claude", "chatgpt", "gemini", "qwen-local", "gemma"):
            assert needed in result.stdout, f"{needed} missing from `list models`"

    def test_list_backends_shows_all_six(self):
        from typer.testing import CliRunner
        from praxia.cli.main import app

        result = CliRunner().invoke(app, ["list", "backends"])
        assert result.exit_code == 0
        for needed in ("json", "mem0", "langmem", "letta", "zep", "hindsight"):
            assert needed in result.stdout

    def test_list_skills(self):
        from typer.testing import CliRunner
        from praxia.cli.main import app

        result = CliRunner().invoke(app, ["list", "skills"])
        assert result.exit_code == 0
        for needed in ("investment_analyst", "sales_strategist", "legal_reviewer"):
            assert needed in result.stdout

    def test_list_flows(self):
        from typer.testing import CliRunner
        from praxia.cli.main import app

        result = CliRunner().invoke(app, ["list", "flows"])
        assert result.exit_code == 0
        for needed in ("sales_agent_flow", "logic_checker_flow", "rag_optimization_flow"):
            assert needed in result.stdout
