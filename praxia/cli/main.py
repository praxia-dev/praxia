"""Praxia CLI.

Usage:
    praxia init
    praxia run <flow> --customer "Acme" --product "BizFlow"
    praxia skill run <skill_name> "<input>"
    praxia skill promote --candidates
    praxia user create alice --role member
    praxia user audit
    praxia freeze --block <label>
    praxia list flows | skills | models | backends
    praxia consolidate
    praxia ui
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from praxia import Praxia, LLM
from praxia.flows import ALL_FLOWS, LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow
from praxia.skills import BUSINESS_SKILLS

app = typer.Typer(help="Praxia — multi-agent orchestrator with cyclic memory.")
console = Console()

FLOW_REGISTRY: dict[str, type] = {
    "sales": SalesAgentFlow,
    "sales-agent": SalesAgentFlow,
    "logic": LogicCheckerFlow,
    "logic-checker": LogicCheckerFlow,
    "rag": RAGOptimizationFlow,
    "rag-optimizer": RAGOptimizationFlow,
}

SKILL_REGISTRY: dict[str, type] = {s.manifest.name: s for s in BUSINESS_SKILLS}
SKILL_REGISTRY.update({s.manifest.domain: s for s in BUSINESS_SKILLS})


@app.command()
def init(
    user_id: str = typer.Option("default-user", help="User ID (personal memory namespace)"),
    org_id: str = typer.Option("default-org", help="Organization ID (shared memory namespace)"),
    backend: str = typer.Option(
        "json", help="LTM backend: json|mem0|langmem|letta|zep|hindsight"
    ),
    model: str = typer.Option(
        "auto", help="LLM model: auto|claude|chatgpt|gemini|qwen|qwen-local"
    ),
) -> None:
    """Initialize: create memory directories + register default skills + bootstrap admin."""
    loom = Praxia(user_id=user_id, org_id=org_id, default_model=model)
    if loom.skill_registry:
        for skill_cls in BUSINESS_SKILLS:
            skill = skill_cls(llm=loom.llm)
            loom.skill_registry.register_org(skill)

    # Bootstrap auth (creates default admin if none exists)
    from praxia.auth import AuthManager
    AuthManager(storage_dir=loom.config.memory_dir / "auth")
    bootstrap_path = loom.config.memory_dir / "auth" / "BOOTSTRAP_API_KEY.txt"

    console.print(
        Panel.fit(
            f"✅ Praxia initialized\n"
            f"  user_id: [bold]{user_id}[/bold]\n"
            f"  org_id:  [bold]{org_id}[/bold]\n"
            f"  backend: [bold]{backend}[/bold]\n"
            f"  model:   [bold]{loom.llm.model}[/bold]\n"
            f"  storage: [bold]{loom.config.memory_dir}[/bold]\n\n"
            f"Registered {len(BUSINESS_SKILLS)} business skills in the org registry.\n"
            f"Bootstrap admin API key: {bootstrap_path}",
            title="Praxia",
            border_style="cyan",
        )
    )


@app.command()
def run(
    flow: str = typer.Argument(..., help=f"フロー名: {', '.join(FLOW_REGISTRY)}"),
    user_id: str = typer.Option("default-user"),
    model: str = typer.Option("auto"),
    customer_name: str = typer.Option("", help="(sales) 顧客名"),
    product: str = typer.Option("", help="(sales) 製品名"),
    additional_context: str = typer.Option("", help="(sales) 追加コンテキスト"),
    document: str = typer.Option("", help="(logic) 文書本文 または ファイルパス"),
    question: str = typer.Option("", help="(rag) 質問"),
) -> None:
    """フローを実行"""
    if flow not in FLOW_REGISTRY:
        console.print(f"[red]Unknown flow: {flow}[/red]")
        console.print("利用可能: " + ", ".join(FLOW_REGISTRY))
        raise typer.Exit(1)

    flow_cls = FLOW_REGISTRY[flow]
    loom = Praxia(user_id=user_id, default_model=model)

    # gather inputs based on flow type
    inputs: dict = {}
    if flow_cls is SalesAgentFlow:
        if not customer_name:
            console.print("[red]--customer-name is required for sales flow[/red]")
            raise typer.Exit(1)
        inputs = {
            "customer_name": customer_name,
            "product": product,
            "additional_context": additional_context,
        }
    elif flow_cls is LogicCheckerFlow:
        body = document
        if document and Path(document).is_file():
            body = Path(document).read_text(encoding="utf-8")
        inputs = {"document": body}
    elif flow_cls is RAGOptimizationFlow:
        inputs = {"question": question, "retriever": None}

    console.print(f"▶ Running [bold]{flow_cls.name}[/bold] with model [bold]{loom.llm.model}[/bold]…")
    result = loom.run(flow_cls, inputs=inputs)
    console.print(Panel(result.final_output, title="Final Output", border_style="green"))
    console.print(
        f"[dim]usage: in={result.total_usage['input_tokens']}, "
        f"out={result.total_usage['output_tokens']}[/dim]"
    )


@app.command(name="list")
def list_(
    target: str = typer.Argument("flows", help="flows | skills | models | backends")
) -> None:
    """利用可能なリソース一覧"""
    if target == "flows":
        table = Table(title="Available Flows")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        for cls in ALL_FLOWS:
            table.add_row(cls.name, cls.description)
        console.print(table)
    elif target == "skills":
        table = Table(title="Default Business Skills")
        table.add_column("Name", style="cyan")
        table.add_column("Domain", style="yellow")
        table.add_column("Description")
        for cls in BUSINESS_SKILLS:
            m = cls.manifest
            table.add_row(m.name, m.domain, m.description)
        console.print(table)
    elif target == "models":
        table = Table(title="Supported LLM Providers")
        table.add_column("Alias", style="cyan")
        table.add_column("Resolves to")
        from praxia.core.llm import DEFAULT_ALIASES
        for alias, model in DEFAULT_ALIASES.items():
            table.add_row(alias, model)
        console.print(table)
        console.print(
            "[dim]Any LiteLLM-supported provider works — pass `--model <provider>/<model>`.[/dim]"
        )
    elif target == "backends":
        table = Table(title="Memory Backends")
        table.add_column("Name", style="cyan")
        table.add_column("Notes")
        table.add_row("json", "Default — zero deps, JSONL on disk")
        table.add_row("mem0", "Mem0 OSS — entity linking + hybrid search (recommended)")
        table.add_row("langmem", "LangChain LangMem SDK")
        table.add_row("letta", "Letta shared blocks")
        table.add_row("zep", "Zep / Graphiti — temporal KG (Layer 5)")
        table.add_row("hindsight", "vectorize-io/hindsight — agent memory store")
        console.print(table)
    else:
        console.print(f"[red]Unknown target: {target}[/red]")
        raise typer.Exit(1)


@app.command()
def consolidate(
    user_id: str = typer.Option("default-user"),
    threshold: float = typer.Option(0.75, help="自動昇格の閾値 (0..1)"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """個人メモリ → 組織メモリへの蒸留 (Sleep-time Consolidation)"""
    loom = Praxia(user_id=user_id)
    loom.config.consolidation_threshold = threshold
    report = loom.consolidate(dry_run=dry_run)
    console.print(Panel.fit(str(report), title="Consolidation Report", border_style="blue"))


@app.command()
def ui(
    port: int = typer.Option(8501),
    user_id: str = typer.Option("default-user"),
) -> None:
    """Launch the default Streamlit UI."""
    import subprocess
    import sys

    from praxia.ui import launcher

    ui_path = Path(launcher.__file__).parent / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(ui_path), "--server.port", str(port)]
    console.print(f"Launching UI at [bold]http://localhost:{port}[/bold] (user_id={user_id})…")
    subprocess.run(cmd, env={**__import__("os").environ, "PRAXIA_USER_ID": user_id}, check=False)


# --- Phase 3: Freeze ---------------------------------------------------------

@app.command()
def freeze(
    block: str = typer.Option(..., "--block", help="Shared block label to freeze"),
    user_id: str = typer.Option("default-user"),
    output_dir: str = typer.Option(".praxia/frozen", help="Markdown root dir"),
) -> None:
    """Promote a shared block to the Markdown frozen layer (Phase 3)."""
    from praxia.memory.markdown_store import MarkdownStore

    loom = Praxia(user_id=user_id)
    if not loom.shared_memory:
        console.print("[red]Shared memory disabled[/red]")
        raise typer.Exit(1)

    blk = loom.shared_memory.get_by_label(block)
    if not blk:
        console.print(f"[red]Block not found: {block}[/red]")
        raise typer.Exit(1)

    store = MarkdownStore(output_dir)
    path = store.freeze_instruction(
        title=blk.label,
        description=blk.description,
        body=blk.value,
        tags=["frozen", "auto-promoted"],
    )
    console.print(f"✅ Frozen [bold]{block}[/bold] → {path}")


# --- Phase 4: Skill promotion ------------------------------------------------

skill_app = typer.Typer(help="Skill registry commands")
app.add_typer(skill_app, name="skill")


@skill_app.command("run")
def skill_run(
    name: str = typer.Argument(..., help="Skill name or domain"),
    user_input: str = typer.Argument(..., help="Input to the agent"),
    model: str = typer.Option("auto"),
) -> None:
    """Run a single business skill."""
    if name not in SKILL_REGISTRY:
        console.print(f"[red]Unknown skill: {name}[/red]. Available: {', '.join(SKILL_REGISTRY)}")
        raise typer.Exit(1)
    skill_cls = SKILL_REGISTRY[name]
    llm = LLM(LLM.auto_detect() if model == "auto" else model)
    obj = skill_cls(llm=llm)
    output = obj.run(user_input)
    console.print(Panel(output, title=obj.manifest.name, border_style="magenta"))


@skill_app.command("promote")
def skill_promote(
    candidates: bool = typer.Option(False, "--candidates", help="List eligible skills"),
    name: str = typer.Option("", help="Skill to promote"),
    user_id: str = typer.Option("", help="Source user_id (required when promoting)"),
    min_users: int = typer.Option(3),
    min_count: int = typer.Option(10),
    min_success: float = typer.Option(0.6),
) -> None:
    """List or perform personal-to-org skill promotion (Phase 4)."""
    from praxia.skills.registry import SkillRegistry

    reg = SkillRegistry()

    if candidates or not name:
        eligible = reg.promote_candidates(
            min_users=min_users, min_count=min_count, min_success_rate=min_success
        )
        if not eligible:
            console.print("[dim]No skills meet the promotion thresholds yet.[/dim]")
            return
        table = Table(title="Promotion Candidates")
        table.add_column("Name", style="cyan")
        table.add_column("Users", justify="right")
        table.add_column("Count", justify="right")
        table.add_column("Success rate", justify="right")
        for s in eligible:
            stats = reg.usage_stats(s.name)
            table.add_row(
                s.name,
                str(stats["users"]),
                str(stats["count"]),
                f"{stats['success_rate']:.0%}",
            )
        console.print(table)
        return

    if not user_id:
        console.print("[red]--user-id is required when promoting a specific skill[/red]")
        raise typer.Exit(1)
    promoted = reg.promote(name, source_user_id=user_id)
    if promoted:
        console.print(f"✅ Promoted [bold]{name}[/bold] → org registry ({promoted.manifest_path})")
    else:
        console.print(f"[red]Skill {name} not found in personal registry of {user_id}[/red]")
        raise typer.Exit(1)


# --- Phase 5: User & auth management -----------------------------------------

user_app = typer.Typer(help="User and role management")
app.add_typer(user_app, name="user")


@user_app.command("create")
def user_create(
    username: str = typer.Argument(...),
    role: str = typer.Option("member", help="admin | operator | member | viewer"),
    email: str = typer.Option(""),
) -> None:
    """Create a user and print their freshly-issued API key."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    user, raw_key = auth.create_user(username, role=role, email=email or None)
    console.print(
        Panel.fit(
            f"✅ User created\n"
            f"  username: [bold]{user.username}[/bold]\n"
            f"  role:     [bold]{user.role}[/bold]\n"
            f"  api_key:  [yellow]{raw_key}[/yellow]\n\n"
            f"[red]Save this API key now — it will not be shown again.[/red]",
            border_style="green",
        )
    )


@user_app.command("list")
def user_list() -> None:
    """List all users."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    table = Table(title="Users")
    table.add_column("Username", style="cyan")
    table.add_column("Role", style="yellow")
    table.add_column("Email")
    table.add_column("Active")
    for u in auth.users.list_all():
        table.add_row(u.username, u.role, u.email or "—", "✓" if u.is_active else "✗")
    console.print(table)


@user_app.command("grant")
def user_grant(
    username: str = typer.Argument(...),
    role: str = typer.Argument(..., help="admin | operator | member | viewer"),
) -> None:
    """Change a user's role."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    auth.grant_role(username, role)
    console.print(f"✅ Role of [bold]{username}[/bold] changed to [bold]{role}[/bold]")


@user_app.command("rotate-key")
def user_rotate_key(username: str = typer.Argument(...)) -> None:
    """Rotate the user's API key (old key is invalidated)."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    user = auth.users.get_by_username(username)
    if not user:
        console.print(f"[red]Unknown user: {username}[/red]")
        raise typer.Exit(1)
    raw = auth.users.rotate_api_key(user.id)
    console.print(f"✅ New API key for [bold]{username}[/bold]: [yellow]{raw}[/yellow]")


@user_app.command("audit")
def user_audit(limit: int = typer.Option(50)) -> None:
    """Tail the audit log."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    table = Table(title=f"Last {limit} Audit Events")
    table.add_column("Time")
    table.add_column("Actor")
    table.add_column("Action", style="cyan")
    table.add_column("Resource")
    table.add_column("Outcome")
    import datetime
    for e in auth.audit.tail(limit=limit):
        ts = datetime.datetime.fromtimestamp(e.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        style = "green" if e.outcome == "success" else "red"
        table.add_row(ts, e.actor_id[:12], e.action, e.resource, f"[{style}]{e.outcome}[/{style}]")
    console.print(table)


if __name__ == "__main__":
    app()
