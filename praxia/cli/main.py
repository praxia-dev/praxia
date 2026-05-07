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
# Utility skills are not in BUSINESS_SKILLS but are runnable via `praxia skill run`.
from praxia.skills import OutputFormatSkill, PromptDesignerSkill  # noqa: E402
SKILL_REGISTRY["output_format"] = OutputFormatSkill
SKILL_REGISTRY["prompt_designer"] = PromptDesignerSkill


@app.command()
def init(
    user_id: str = typer.Option("default-user", help="User ID (personal memory namespace)"),
    org_id: str = typer.Option("default-org", help="Organization ID (shared memory namespace)"),
    backend: str = typer.Option(
        "json",
        help=(
            "LTM backend. Recommended: json (default, zero deps) or mem0 "
            "(production). Other backends (langmem / letta / zep / hindsight) "
            "ship as protocol stubs and require pinning their respective SDK "
            "versions before use — see docs/FEATURES.md § 5."
        ),
    ),
    model: str = typer.Option(
        "auto", help="LLM model: auto|claude|chatgpt|gemini|qwen|qwen-local|gemma|gemma-cloud"
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
            # Use the unified parser → handles PDF / Word / PowerPoint /
            # Excel / CSV / TXT / MD / HTML and more
            from praxia.io.parsers import parse_file
            try:
                parsed = parse_file(document)
                body = parsed.content
                console.print(
                    f"[dim]📄 Parsed {parsed.filename} · {len(body):,} chars · {parsed.metadata}[/dim]"
                )
            except Exception as e:
                console.print(f"[yellow]Parser failed ({e}); falling back to raw read[/yellow]")
                body = Path(document).read_text(encoding="utf-8", errors="replace")
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
        table.add_column("Status", style="yellow")
        table.add_column("Notes")
        table.add_row("json", "✅ stable", "Default — zero deps, JSONL on disk")
        table.add_row("mem0", "✅ stable", "Mem0 OSS — entity linking + hybrid search (recommended for production)")
        table.add_row(
            "langmem", "🟡 experimental",
            "LangChain LangMem — SDK shape unstable; pin a specific version before use",
        )
        table.add_row(
            "letta", "🟡 experimental",
            "Letta shared blocks — search is substring-only against the JSONL form",
        )
        table.add_row(
            "zep", "🟡 experimental",
            "Zep / Graphiti — errors silently swallowed; verify before relying on results",
        )
        table.add_row(
            "hindsight", "🟡 experimental",
            "vectorize-io/hindsight — speculative SDK probing; falls back to in-memory list",
        )
        console.print(table)
        console.print(
            "[dim]✅ stable means tested against a real SDK. 🟡 experimental "
            "means the wrapper exists but production users should pin versions "
            "and verify behavior before relying on the backend.[/dim]"
        )
        console.print(
            "[dim]Combine multiple backends with CompositeBackend (RRF fusion) "
            "or RoutedBackend (query-aware dispatch) — see "
            "docs/FEATURES.md § 5.1.[/dim]"
        )
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


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
    storage_dir: str = typer.Option(".praxia"),
    cors_origin: list[str] = typer.Option(
        [], help="Allowed CORS origin (repeatable)"
    ),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code change (dev only)"),
) -> None:
    """Run the FastAPI HTTP backend (mode B in deployment-modes.md).

    Endpoints are versioned under /api/v1. Authenticate with X-API-Key or
    a JWT issued by /api/v1/auth/login.

    Requires `pip install 'praxia[server]'`.
    """
    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        console.print(
            "[red]uvicorn is not installed. Run: pip install 'praxia[server]'[/red]"
        )
        raise typer.Exit(1)
    from praxia.server.app import create_app

    fastapi_app = create_app(
        storage_dir=storage_dir,
        cors_origins=list(cors_origin) or None,
    )
    uvicorn.run(fastapi_app, host=host, port=port, reload=reload)


# --- MCP server -------------------------------------------------------------

mcp_app = typer.Typer(help="Model Context Protocol server (Claude Desktop / Cursor)")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("serve")
def mcp_serve() -> None:
    """Run an MCP server on stdio. Connect from Claude Desktop / Cursor."""
    from praxia.mcp import serve_stdio
    serve_stdio()


@mcp_app.command("tools")
def mcp_tools() -> None:
    """List the MCP tools Praxia exposes (skills + flows + utilities)."""
    from praxia.mcp import build_tools
    table = Table(title="MCP tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    for t in build_tools():
        table.add_row(t.name, t.description)
    console.print(table)


# --- Webhooks ---------------------------------------------------------------

webhook_app = typer.Typer(help="Outgoing webhook subscriptions")
app.add_typer(webhook_app, name="webhook")


@webhook_app.command("add")
def webhook_add(
    url: str = typer.Argument(..., help="Receiver URL (e.g. Slack incoming webhook)"),
    event: str = typer.Option("*", help="Event filter (e.g. 'flow.run.complete' or '*')"),
    secret: str = typer.Option("", help="Optional HMAC secret (recommended)"),
) -> None:
    """Subscribe a URL to Praxia events."""
    from praxia.webhooks import WebhookManager
    mgr = WebhookManager()
    sub = mgr.add(url=url, event=event, secret=secret)
    console.print(f"✅ Subscribed [bold]{sub.id}[/bold] → {url} (event={event})")


@webhook_app.command("list")
def webhook_list() -> None:
    from praxia.webhooks import WebhookManager
    mgr = WebhookManager()
    table = Table(title="Webhook subscriptions")
    table.add_column("ID", style="cyan")
    table.add_column("Event")
    table.add_column("URL")
    table.add_column("Active")
    for s in mgr.list():
        table.add_row(s.id[:8], s.event, s.url, "✓" if s.active else "✗")
    console.print(table)


@webhook_app.command("remove")
def webhook_remove(
    sub_id: str = typer.Argument(..., help="Subscription ID (or its first 8 chars)"),
) -> None:
    from praxia.webhooks import WebhookManager
    mgr = WebhookManager()
    # Accept partial ID
    matches = [s for s in mgr.list() if s.id.startswith(sub_id)]
    if not matches:
        console.print(f"[red]No subscription matches: {sub_id}[/red]")
        raise typer.Exit(1)
    if len(matches) > 1:
        console.print(f"[red]Ambiguous prefix; {len(matches)} matches[/red]")
        raise typer.Exit(1)
    mgr.remove(matches[0].id)
    console.print(f"🗑  Removed {matches[0].id}")


@webhook_app.command("test")
def webhook_test(
    sub_id: str = typer.Argument(...),
) -> None:
    """Fire a test event to a single subscription (sync, prints result)."""
    from praxia.webhooks import WebhookManager
    mgr = WebhookManager()
    matches = [s for s in mgr.list() if s.id.startswith(sub_id)]
    if not matches:
        console.print(f"[red]No subscription matches: {sub_id}[/red]")
        raise typer.Exit(1)
    sub = matches[0]
    # Temporarily filter to this one subscription by using .dispatch with sync=True
    # but the manager dispatches to all matching subs — we cheat by creating
    # a one-off temporary manager instance pointed at a hidden dir. Simpler:
    # invoke the private _deliver method directly.
    import json
    body = json.dumps({"event": "test.ping", "payload": {"hello": "world"}}).encode()
    delivery = mgr._deliver(sub, "test.ping", body)
    console.print(
        f"  status: {delivery.status_code}  success: {delivery.success}  "
        f"duration: {delivery.duration_ms:.1f} ms\n"
        f"  error: {delivery.error or '(none)'}"
    )


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


# --- Phase 5: User & auth management -------------------------------------
from praxia.cli.commands.user import user_app
app.add_typer(user_app, name="user")

# --- Custom prompts -----------------------------------------------------

prompt_app = typer.Typer(help="Custom prompt management (user + admin distribution)")
app.add_typer(prompt_app, name="prompt")


@prompt_app.command("create")
def prompt_create(
    name: str = typer.Argument(...),
    body: str = typer.Argument(..., help="Prompt body or path to file"),
    user_id: str = typer.Option("default-user"),
    description: str = typer.Option(""),
    tags: str = typer.Option("", help="Comma-separated tags"),
) -> None:
    """Save a personal prompt for the current user."""
    from praxia.skills.prompts import PromptStore

    body_text = Path(body).read_text(encoding="utf-8") if Path(body).is_file() else body
    store = PromptStore()
    p = store.save_personal(
        user_id,
        name=name,
        body=body_text,
        description=description,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    console.print(f"✅ Saved personal prompt [bold]{p.name}[/bold] for {user_id}")


@prompt_app.command("list")
def prompt_list(
    user_id: str = typer.Option("default-user"),
    role: str = typer.Option("member"),
) -> None:
    """List all prompts visible to the user (personal + org + distributed)."""
    from praxia.skills.prompts import PromptStore

    store = PromptStore()
    prompts = store.list_for_user(user_id=user_id, role=role)
    table = Table(title=f"Prompts visible to {user_id}")
    table.add_column("Name", style="cyan")
    table.add_column("Scope")
    table.add_column("Owner")
    table.add_column("Description")
    for p in prompts:
        table.add_row(p.name, p.scope, p.owner, p.description)
    console.print(table)


@prompt_app.command("distribute")
def prompt_distribute(
    name: str = typer.Argument(...),
    body: str = typer.Argument(..., help="Prompt body or path to file"),
    target_users: str = typer.Option("", help="Comma-separated user_ids"),
    target_roles: str = typer.Option("", help="Comma-separated roles"),
    description: str = typer.Option(""),
) -> None:
    """Admin: push a prompt to specific users or roles."""
    from praxia.skills.prompts import PromptStore

    body_text = Path(body).read_text(encoding="utf-8") if Path(body).is_file() else body
    store = PromptStore()
    saved = store.distribute(
        name=name,
        body=body_text,
        description=description,
        target_users=[u.strip() for u in target_users.split(",") if u.strip()] or None,
        target_roles=[r.strip() for r in target_roles.split(",") if r.strip()] or None,
    )
    console.print(f"📤 Distributed [bold]{name}[/bold] to {len(saved)} target(s)")


@prompt_app.command("delete")
def prompt_delete(
    name: str = typer.Argument(...),
    user_id: str = typer.Option("default-user"),
) -> None:
    """Delete a personal prompt."""
    from praxia.skills.prompts import PromptStore

    store = PromptStore()
    if store.delete_personal(user_id, name):
        console.print(f"🗑  Deleted personal prompt {name}")
    else:
        console.print(f"[red]Not found: {name}[/red]")
        raise typer.Exit(1)


# --- Skill distribution (extends existing skill_app) -----------------------

@skill_app.command("distribute")
def skill_distribute(
    name: str = typer.Argument(..., help="Skill name (must exist in org or personal)"),
    target_users: str = typer.Option("", help="Comma-separated user_ids"),
    target_roles: str = typer.Option("", help="Comma-separated roles"),
    source_user_id: str = typer.Option("", help="Source user (if distributing a personal skill)"),
) -> None:
    """Admin: distribute a skill to specific users or roles."""
    from praxia.skills.registry import SkillRegistry
    from praxia.skills import BUSINESS_SKILLS

    reg = SkillRegistry()
    # Resolve the skill — try built-in business skills first
    skill_obj = None
    for sk in BUSINESS_SKILLS:
        if sk.manifest.name == name:
            skill_obj = sk()
            break
    if skill_obj is None:
        console.print(f"[red]Skill not found: {name}[/red]")
        raise typer.Exit(1)
    saved = reg.distribute(
        skill_obj,
        target_users=[u.strip() for u in target_users.split(",") if u.strip()] or None,
        target_roles=[r.strip() for r in target_roles.split(",") if r.strip()] or None,
    )
    console.print(f"📤 Distributed [bold]{name}[/bold] to {len(saved)} target(s)")


# --- Dashboard ----------------------------------------------------------

@app.command()
def dashboard(
    scope: str = typer.Option("personal", help="personal | org"),
    user_id: str = typer.Option("default-user"),
    org_id: str = typer.Option("default-org"),
) -> None:
    """Show usage dashboard (personal or organizational)."""
    from praxia.analytics import Dashboard

    d = Dashboard()
    if scope == "personal":
        s = d.personal_summary(user_id)
        import datetime
        last = (
            datetime.datetime.fromtimestamp(s.last_active_ts).strftime("%Y-%m-%d %H:%M")
            if s.last_active_ts
            else "—"
        )
        console.print(
            Panel.fit(
                f"📊 Personal dashboard for [bold]{s.user_id}[/bold]\n\n"
                f"  Flow runs:        {s.flow_runs}\n"
                f"  Skill runs:       {s.skill_runs}\n"
                f"  Memory entries:   {s.memory_entries}\n"
                f"  Episodes:         {s.episodes}\n"
                f"  Outcomes:         {s.outcomes_recorded} (success rate: {s.success_rate:.0%})\n"
                f"  Tokens (in/out):  {s.total_input_tokens:,} / {s.total_output_tokens:,}\n"
                f"  Last active:      {last}",
                title="Personal",
                border_style="cyan",
            )
        )
        if s.top_skills:
            top = Table(title="Top skills (by invocations)")
            top.add_column("Skill")
            top.add_column("Count", justify="right")
            for n, c in s.top_skills:
                top.add_row(n, str(c))
            console.print(top)
    elif scope == "org":
        s = d.org_summary(org_id)
        console.print(
            Panel.fit(
                f"📊 Organization dashboard for [bold]{s.org_id}[/bold]\n\n"
                f"  Active users:           {s.active_users}\n"
                f"  Total flow runs:        {s.total_flow_runs}\n"
                f"  Total skill runs:       {s.total_skill_runs}\n"
                f"  Total outcomes:         {s.total_outcomes} (success rate: {s.org_success_rate:.0%})\n"
                f"  Promoted shared blocks: {s.promoted_blocks}\n"
                f"  Frozen Markdown files:  {s.frozen_files}\n"
                f"  Distributed skills:     {s.distributed_skills}\n"
                f"  Distributed prompts:    {s.distributed_prompts}\n"
                f"  Total audit events:     {s.audit_event_count}",
                title="Organization",
                border_style="magenta",
            )
        )
        if s.top_users:
            tu = Table(title="Top users (by audit event count)")
            tu.add_column("User"); tu.add_column("Events", justify="right")
            for u, c in s.top_users:
                tu.add_row(u[:20], str(c))
            console.print(tu)
        if s.top_skills:
            ts = Table(title="Top skills")
            ts.add_column("Skill"); ts.add_column("Invocations", justify="right")
            for n, c in s.top_skills:
                ts.add_row(n, str(c))
            console.print(ts)
    else:
        console.print(f"[red]Unknown scope: {scope}. Use 'personal' or 'org'.[/red]")
        raise typer.Exit(1)


# --- External connectors --------------------------------------------------
from praxia.cli.commands.connector import connector_app
app.add_typer(connector_app, name="connector")


# --- Autonomous agent (LLM-driven tool-use loop) ------------------
from praxia.cli.commands.agent import agent_app
app.add_typer(agent_app, name="agent")


# --- Admin: resource access policies (ACL) -----------------------------

policy_app = typer.Typer(help="Resource access policies (admin / IS dept use)")
app.add_typer(policy_app, name="policy")


@policy_app.command("add")
def policy_add(
    effect: str = typer.Argument(..., help="allow | deny"),
    resource_type: str = typer.Argument(..., help="connector|memory|prompt|skill|block|*"),
    resource_pattern: str = typer.Argument(..., help='Glob, e.g. "box:/Confidential/*"'),
    actions: str = typer.Option("*", help="Comma-separated actions: read,write,list,*"),
    principals: str = typer.Option("*", help="Comma-separated user_ids and role:<name>"),
    description: str = typer.Option(""),
) -> None:
    """Create a new access policy."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    p = auth.policies.add(
        effect=effect,  # type: ignore[arg-type]
        resource_type=resource_type,
        resource_pattern=resource_pattern,
        actions=[a.strip() for a in actions.split(",") if a.strip()],
        principals=[a.strip() for a in principals.split(",") if a.strip()],
        description=description,
    )
    console.print(f"✅ Added policy [bold]{p.id}[/bold] ({p.effect} {p.resource_type}:{p.resource_pattern})")


@policy_app.command("list")
def policy_list() -> None:
    """List all access policies in evaluation order."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    table = Table(title="Access Policies (evaluated top → bottom)")
    table.add_column("ID", style="dim")
    table.add_column("Effect", style="cyan")
    table.add_column("Type")
    table.add_column("Pattern")
    table.add_column("Actions")
    table.add_column("Principals")
    table.add_column("Description")
    for p in auth.policies.list():
        eff_style = "green" if p.effect == "allow" else "red"
        table.add_row(
            p.id[:8],
            f"[{eff_style}]{p.effect}[/{eff_style}]",
            p.resource_type,
            p.resource_pattern,
            ",".join(p.actions),
            ",".join(p.principals),
            p.description,
        )
    console.print(table)


@policy_app.command("remove")
def policy_remove(policy_id: str = typer.Argument(...)) -> None:
    """Remove a policy by ID."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    if auth.policies.remove(policy_id):
        console.print(f"🗑  Removed policy {policy_id}")
    else:
        console.print(f"[red]Policy not found: {policy_id}[/red]")
        raise typer.Exit(1)


@policy_app.command("test")
def policy_test(
    user_id: str = typer.Argument(...),
    role: str = typer.Argument(...),
    resource_type: str = typer.Argument(...),
    resource_id: str = typer.Argument(...),
    action: str = typer.Argument(...),
) -> None:
    """Dry-run policy evaluation (debug helper for IS dept)."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    decision = auth.policies.evaluate(
        user_id=user_id,
        role=role,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
    )
    icon = "✅" if decision.allowed else "🚫"
    console.print(
        Panel.fit(
            f"{icon} {'allowed' if decision.allowed else 'DENIED'}\n\n"
            f"  user:     {user_id}\n"
            f"  role:     {role}\n"
            f"  resource: {resource_type}:{resource_id}\n"
            f"  action:   {action}\n\n"
            f"  reason:   {decision.reason}\n"
            f"  policy:   {decision.matched_policy_id or '— (default)'}",
            title="Policy decision",
            border_style="green" if decision.allowed else "red",
        )
    )


# --- Admin: data exports + memory policy --------------------------------------
from praxia.cli.commands.admin import admin_app
app.add_typer(admin_app, name="admin")


# --- User: memory mode preference --------------------------------------------

memory_app = typer.Typer(help="Per-user memory preferences (mode + backend)")
app.add_typer(memory_app, name="memory")


@memory_app.command("mode")
def memory_mode_set(
    user_id: str = typer.Option(..., help="User ID"),
    mode: str = typer.Argument(..., help="accumulate | read_only"),
    storage_dir: str = typer.Option(".praxia"),
) -> None:
    """Set this user's memory accumulation mode (subject to admin policy)."""
    from praxia.memory.policy import MemoryAdminPolicy, MemoryUserPreference

    if mode not in ("accumulate", "read_only"):
        console.print("[red]mode must be 'accumulate' or 'read_only'[/red]")
        raise typer.Exit(1)

    admin = MemoryAdminPolicy.load(storage_dir)
    if admin.mode_locked:
        console.print(
            f"[yellow]⚠ Admin policy locks mode to {admin.default_mode!r}. "
            f"Your preference is saved but the effective mode will not change.[/yellow]"
        )

    pref = MemoryUserPreference.load(storage_dir, user_id)
    pref.mode = mode  # type: ignore[assignment]
    path = pref.save(storage_dir)
    console.print(f"✅ {user_id}'s memory mode → [bold]{mode}[/bold] ({path})")


@memory_app.command("backend")
def memory_backend_set(
    user_id: str = typer.Option(..., help="User ID"),
    backend: str = typer.Argument(..., help="json | mem0 | langmem | letta | zep | hindsight"),
    storage_dir: str = typer.Option(".praxia"),
) -> None:
    """Set this user's preferred memory backend (subject to admin policy)."""
    from praxia.memory.policy import MemoryAdminPolicy, MemoryUserPreference

    admin = MemoryAdminPolicy.load(storage_dir)
    if not admin.is_backend_allowed(backend):
        console.print(
            f"[red]✗ Backend {backend!r} is not allowed by admin policy. "
            f"Allowed: {admin.allowed_backends or 'any except enforcement'}[/red]"
        )
        raise typer.Exit(1)

    pref = MemoryUserPreference.load(storage_dir, user_id)
    pref.backend = backend
    pref.save(storage_dir)
    console.print(f"✅ {user_id}'s memory backend → [bold]{backend}[/bold]")


@memory_app.command("show")
def memory_show(
    user_id: str = typer.Option(..., help="User ID"),
    role: str = typer.Option("member", help="User role (used to evaluate role-based locks)"),
    storage_dir: str = typer.Option(".praxia"),
) -> None:
    """Show the effective memory configuration for this user."""
    from praxia.memory.policy import resolve_memory_config

    cfg = resolve_memory_config(
        user_id=user_id,
        storage_dir=storage_dir,
        user_role=role,
    )
    table = Table(title=f"Memory config for {user_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("backend", cfg.backend)
    table.add_row("mode", cfg.mode)
    table.add_row("locked_by_admin", str(cfg.locked_by_admin))
    table.add_row("reason", cfg.reason)
    console.print(table)


# --- Output exporters --------------------------------------------------------

# --- Experiments (A/B testing) ----------------------------------------------

experiment_app = typer.Typer(help="A/B experiments for prompts / skills / LLMs")
app.add_typer(experiment_app, name="experiment")


@experiment_app.command("create")
def experiment_create(
    exp_id: str = typer.Argument(..., help="Stable identifier (don't change once running)"),
    name: str = typer.Option(..., help="Human-readable name"),
    variants_json: str = typer.Option(
        ..., "--variants", help='JSON: {"control":{"prompt":"..."},"treatment":{"prompt":"..."}}'
    ),
    traffic_split: str = typer.Option(
        "", help='Comma-separated name=fraction (e.g. "control=0.5,treatment=0.5")'
    ),
    description: str = typer.Option(""),
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """Create a new experiment in DRAFT status."""
    import json as _json
    from praxia.experiments import Experiment, ExperimentRegistry, Variant

    try:
        var_dict = _json.loads(variants_json)
    except _json.JSONDecodeError as e:
        console.print(f"[red]Invalid --variants JSON: {e}[/red]")
        raise typer.Exit(1)
    variants = {n: Variant(name=n, payload=p) for n, p in var_dict.items()}

    split: dict[str, float] = {}
    if traffic_split:
        for chunk in traffic_split.split(","):
            k, _, v = chunk.partition("=")
            split[k.strip()] = float(v)

    reg = ExperimentRegistry(storage_dir=storage_dir)
    exp = reg.create(Experiment(
        id=exp_id,
        name=name,
        description=description,
        variants=variants,
        traffic_split=split or {},
    ))
    console.print(f"✅ Created experiment [bold]{exp.id}[/bold] (status: {exp.status})")
    console.print(f"   Activate with: praxia experiment start {exp.id}")


@experiment_app.command("list")
def experiment_list(
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """List all experiments."""
    from praxia.experiments import ExperimentRegistry

    reg = ExperimentRegistry(storage_dir=storage_dir)
    table = Table(title="Experiments")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Variants")
    for exp in reg.list():
        table.add_row(
            exp.id, exp.name, exp.status,
            ", ".join(f"{n}({s:.0%})" for n, s in exp.traffic_split.items()),
        )
    console.print(table)


@experiment_app.command("start")
def experiment_start(
    exp_id: str = typer.Argument(...),
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """Set an experiment's status to RUNNING."""
    from praxia.experiments import ExperimentRegistry, ExperimentStatus

    reg = ExperimentRegistry(storage_dir=storage_dir)
    exp = reg.set_status(exp_id, ExperimentStatus.RUNNING)
    console.print(f"▶️  {exp.id} → running")


@experiment_app.command("pause")
def experiment_pause(
    exp_id: str = typer.Argument(...),
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """Pause a running experiment."""
    from praxia.experiments import ExperimentRegistry, ExperimentStatus

    reg = ExperimentRegistry(storage_dir=storage_dir)
    exp = reg.set_status(exp_id, ExperimentStatus.PAUSED)
    console.print(f"⏸  {exp.id} → paused")


@experiment_app.command("finish")
def experiment_finish(
    exp_id: str = typer.Argument(...),
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """Mark an experiment FINISHED (no further assignments)."""
    from praxia.experiments import ExperimentRegistry, ExperimentStatus

    reg = ExperimentRegistry(storage_dir=storage_dir)
    exp = reg.set_status(exp_id, ExperimentStatus.FINISHED)
    console.print(f"🏁 {exp.id} → finished")


@experiment_app.command("results")
def experiment_results(
    exp_id: str = typer.Argument(...),
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """Show outcome rollup + tentative winner."""
    from praxia.experiments import ExperimentRegistry

    reg = ExperimentRegistry(storage_dir=storage_dir)
    results = reg.results(exp_id)
    table = Table(title=f"Results: {exp_id}")
    table.add_column("Variant", style="cyan")
    table.add_column("Outcomes", justify="right")
    table.add_column("Successes", justify="right")
    table.add_column("Success rate", justify="right")
    table.add_column("Avg score", justify="right")
    for v in results.variants:
        rate = (
            f"{v.success_rate:.1%}" if v.success_rate is not None else "—"
        )
        avg = f"{v.avg_score:.2f}" if v.avg_score is not None else "—"
        table.add_row(v.name, str(v.outcomes_recorded), str(v.successes), rate, avg)
    console.print(table)
    if results.winner:
        console.print(
            f"🏆 Tentative winner: [bold]{results.winner}[/bold] "
            f"(confidence {results.confidence:.2f})"
        )
    console.print(f"[dim]{results.notes}[/dim]")


@experiment_app.command("delete")
def experiment_delete(
    exp_id: str = typer.Argument(...),
    storage_dir: str = typer.Option(".praxia/experiments"),
) -> None:
    """Delete an experiment definition (outcome log retained)."""
    from praxia.experiments import ExperimentRegistry

    reg = ExperimentRegistry(storage_dir=storage_dir)
    if reg.delete(exp_id):
        console.print(f"🗑  Deleted {exp_id}")
    else:
        console.print(f"[yellow]Not found: {exp_id}[/yellow]")
        raise typer.Exit(1)


# --- Output exporters --------------------------------------------------------

@app.command("export")
def export_command(
    input_path: str = typer.Argument(..., help="Input file (md/markdown)"),
    output_path: str = typer.Argument(..., help="Output file (.html/.pptx/.docx/.json/.md)"),
    format: str = typer.Option("", help="Override format (else inferred from extension)"),
    title: str = typer.Option("", help="Document title for HTML/DOCX/PPTX"),
) -> None:
    """Render a Markdown file to HTML / PPTX / DOCX / JSON."""
    from pathlib import Path
    from praxia.io.exporters import export_as

    src = Path(input_path)
    if not src.exists():
        console.print(f"[red]Input not found: {input_path}[/red]")
        raise typer.Exit(1)

    fmt = format or Path(output_path).suffix.lstrip(".")
    if not fmt:
        console.print("[red]Cannot infer format — pass --format[/red]")
        raise typer.Exit(1)

    kwargs = {"title": title} if title else {}
    result = export_as(
        src.read_text(encoding="utf-8"),
        format=fmt,
        output_path=output_path,
        **kwargs,
    )
    console.print(
        f"💾 Exported {input_path} → [bold]{output_path}[/bold] "
        f"({result.format}, {result.size} bytes)"
    )


# --- Unified configuration (single source of truth for all keys) ------------
from praxia.cli.commands.config import config_app
app.add_typer(config_app, name="config")

# --- User-delegated OAuth ----------------------------------------------------

oauth_app = typer.Typer(help="Per-user OAuth for connector access (Box / SharePoint / Drive / Dropbox / Salesforce)")
app.add_typer(oauth_app, name="oauth")


@oauth_app.command("start")
def oauth_start(
    provider: str = typer.Argument(..., help="box | microsoft | dropbox | google | salesforce | zendesk | ..."),
    user_id: str = typer.Option(..., help="Praxia user_id this token belongs to"),
    redirect_uri: str = typer.Option(
        "http://localhost:8765/callback",
        help="Redirect URI registered with the provider's OAuth app",
    ),
    scopes: str = typer.Option(
        "",
        help=(
            "Space-separated scopes to request (overrides provider defaults). "
            "Use this for `microsoft` when you need the Teams connector — pass "
            "e.g. 'Files.ReadWrite.All Sites.Read.All ChannelMessage.Read.All ChannelMessage.Send'."
        ),
    ),
) -> None:
    """Print the authorization URL for a user to authorize a connector.

    Reads client credentials from
        PRAXIA_OAUTH_<PROVIDER>_CLIENT_ID
        PRAXIA_OAUTH_<PROVIDER>_CLIENT_SECRET

    For providers with per-tenant URLs (e.g. Zendesk), also reads:
        PRAXIA_OAUTH_<PROVIDER>_SUBDOMAIN
    """
    import os
    from praxia.connectors.oauth import OAuthFlow

    cid = os.environ.get(f"PRAXIA_OAUTH_{provider.upper()}_CLIENT_ID")
    csec = os.environ.get(f"PRAXIA_OAUTH_{provider.upper()}_CLIENT_SECRET")
    if not (cid and csec):
        console.print(
            f"[red]Set PRAXIA_OAUTH_{provider.upper()}_CLIENT_ID and "
            f"PRAXIA_OAUTH_{provider.upper()}_CLIENT_SECRET first.[/red]"
        )
        raise typer.Exit(1)

    # Per-tenant URL placeholders (e.g. Zendesk subdomain).
    # The flow's _validate_url_params() raises a clear error if any
    # required placeholder is missing.
    url_params: dict[str, str] = {}
    sub = os.environ.get(f"PRAXIA_OAUTH_{provider.upper()}_SUBDOMAIN")
    if sub:
        url_params["subdomain"] = sub

    try:
        flow = OAuthFlow.for_provider(
            provider,
            client_id=cid,
            client_secret=csec,
            redirect_uri=redirect_uri,
            url_params=url_params or None,
        )
    except ValueError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        console.print(
            f"[dim]Hint: set PRAXIA_OAUTH_{provider.upper()}_SUBDOMAIN=<your-subdomain>[/dim]"
        )
        raise typer.Exit(1)
    requested_scopes = [s for s in scopes.split() if s] or None
    url, state = flow.authorization_url(user_id=user_id, scopes=requested_scopes)
    console.print(
        Panel.fit(
            f"Open this URL in a browser to authorize:\n\n"
            f"[link]{url}[/link]\n\n"
            f"After consent the provider will redirect to:\n  {redirect_uri}\n\n"
            f"State (save this; needed for callback): [yellow]{state}[/yellow]",
            title=f"OAuth start: {provider} ({user_id})",
            border_style="cyan",
        )
    )


# NOTE: there is no `praxia oauth callback` CLI command.
# The OAuth state lives in `OAuthFlow`, which is constructed per-process.
# A CLI invocation that received the redirect could not see the state
# stored by the previous `praxia oauth start` invocation, so a `callback`
# CLI command would always fail. Use the production HTTP path instead:
#
#     praxia serve  →  POST /api/v1/oauth/{provider}/start
#                   →  GET  /api/v1/oauth/{provider}/callback?code=...
#
# or call the SDK directly inside your own redirect handler:
#
#     flow = OAuthFlow.for_provider(provider, ...)
#     url, state = flow.authorization_url(user_id=...)
#     # ... user authorizes, IdP redirects to your handler ...
#     token = flow.exchange_code(code=..., state=...)


@oauth_app.command("list")
def oauth_list(user_id: str = typer.Option("", help="Filter to one user")) -> None:
    """List authorized OAuth tokens (without revealing secrets)."""
    import datetime
    from praxia.connectors.oauth import OAuthTokenStore

    store = OAuthTokenStore()
    tokens = store.list_for_user(user_id) if user_id else store.list_all()
    table = Table(title="OAuth tokens")
    table.add_column("User")
    table.add_column("Provider", style="cyan")
    table.add_column("Expires")
    table.add_column("Refresh?")
    table.add_column("Scope")
    for t in tokens:
        expires = (
            datetime.datetime.fromtimestamp(t.expires_at).strftime("%Y-%m-%d %H:%M")
            if t.expires_at
            else "—"
        )
        table.add_row(
            t.user_id,
            t.provider,
            f"[red]{expires}[/red]" if t.is_expired() else expires,
            "✓" if t.refresh_token else "—",
            t.scope[:60],
        )
    console.print(table)


@oauth_app.command("revoke")
def oauth_revoke(
    provider: str = typer.Argument(...),
    user_id: str = typer.Option(...),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    """Revoke a user's OAuth grant for a provider."""
    if not yes and not typer.confirm(f"Revoke {provider} access for {user_id}?"):
        raise typer.Exit(0)
    from praxia.connectors.oauth import OAuthTokenStore
    if OAuthTokenStore().delete(user_id, provider):
        console.print(f"🗑  Revoked {provider} for {user_id}")
    else:
        console.print(f"[red]No token found for {user_id}/{provider}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
