"""CLI commands for the autonomous agent (`praxia agent ...`).

Examples:
    praxia agent run "Acme との今四半期の営業状況を整理して"
    praxia agent tools          # list built-in tools the agent can call
"""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

agent_app = typer.Typer(help="Autonomous agent (ClaudeCode-style tool-use loop)")


@agent_app.command("run")
def agent_run(
    user_input: str = typer.Argument(..., help="Task / question for the agent"),
    user_id: str = typer.Option("default-user", help="User ID (personal memory namespace)"),
    role: str = typer.Option("member", help="RBAC role for ACL evaluation"),
    org_id: str = typer.Option("default-org", help="Organization ID"),
    model: str = typer.Option("auto", help="LLM (auto detects ANTHROPIC_API_KEY etc.)"),
    memory_dir: str = typer.Option(".praxia"),
    max_steps: int = typer.Option(10, help="Hard cap on the tool-use loop"),
    enable_tools: str = typer.Option(
        "", help="Comma-separated tool whitelist (default: all built-ins)"
    ),
    show_trace: bool = typer.Option(True, help="Show tool-call trace"),
) -> None:
    """Run an autonomous agent task end-to-end."""
    from praxia.agent import AutonomousAgent
    from praxia.core.llm import LLM

    chosen = LLM.auto_detect() if model == "auto" else model
    llm = LLM(chosen)
    enabled = [t.strip() for t in enable_tools.split(",") if t.strip()] or None
    agent = AutonomousAgent(
        user_id=user_id,
        role=role,
        org_id=org_id,
        llm=llm,
        memory_dir=memory_dir,
        max_steps=max_steps,
        enable_tools=enabled,
    )
    console.print(
        f"▶ Running autonomous agent (model=[bold]{llm.model}[/bold], "
        f"user={user_id}, max_steps={max_steps})…"
    )
    result = agent.run(user_input)

    if show_trace and result.tool_calls:
        table = Table(title="Tool-call trace")
        table.add_column("#", style="dim")
        table.add_column("Tool", style="cyan")
        table.add_column("Args")
        table.add_column("Outcome")
        for i, tc in enumerate(result.tool_calls, 1):
            args_str = json.dumps(tc.arguments, ensure_ascii=False)
            outcome = "[green]ok[/green]" if tc.ok else f"[red]err: {tc.error[:60]}[/red]"
            table.add_row(str(i), tc.name, args_str[:80], outcome)
        console.print(table)

    border = "green" if result.stopped_reason == "completed" else "yellow"
    console.print(
        Panel(
            result.final_text or "(no output)",
            title=f"Agent answer ({result.stopped_reason}, {result.steps} step(s))",
            border_style=border,
        )
    )
    console.print(
        f"[dim]usage: in={result.usage.get('input_tokens', 0)}, "
        f"out={result.usage.get('output_tokens', 0)}, "
        f"tool_calls={len(result.tool_calls)}[/dim]"
    )


@agent_app.command("tools")
def agent_tools() -> None:
    """List built-in tools the autonomous agent can call."""
    from praxia.agent.tools import builtin_tools

    table = Table(title="Built-in agent tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for name, tool in builtin_tools().items():
        table.add_row(name, tool.description)
    console.print(table)
