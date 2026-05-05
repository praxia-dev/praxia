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
        table.add_column("Notes")
        table.add_row("json", "Default — zero deps, JSONL on disk")
        table.add_row("mem0", "Mem0 OSS — entity linking + hybrid search (recommended)")
        table.add_row("langmem", "LangChain LangMem SDK")
        table.add_row("letta", "Letta shared blocks")
        table.add_row("zep", "Zep / Graphiti — temporal KG (Layer 5)")
        table.add_row("hindsight", "vectorize-io/hindsight — agent memory store")
        console.print(table)
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


@user_app.command("update")
def user_update(
    username: str = typer.Argument(...),
    new_username: str = typer.Option("", help="Rename the user"),
    email: str = typer.Option("", help="New email"),
    role: str = typer.Option("", help="New role"),
    activate: bool = typer.Option(False, "--activate"),
    deactivate: bool = typer.Option(False, "--deactivate"),
) -> None:
    """Update a user's profile (admin only). All fields are optional."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    is_active: bool | None = None
    if activate:
        is_active = True
    elif deactivate:
        is_active = False
    user = auth.update_user(
        username,
        new_username=new_username or None,
        email=email or None,
        role=role or None,
        is_active=is_active,
    )
    console.print(
        f"✅ Updated [bold]{user.username}[/bold] (role={user.role}, active={user.is_active}, email={user.email})"
    )


@user_app.command("delete")
def user_delete(
    username: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation"),
) -> None:
    """Hard-delete a user (admin only)."""
    from praxia.auth import AuthManager

    if not yes:
        confirm = typer.confirm(f"Permanently delete user '{username}'?")
        if not confirm:
            raise typer.Exit(0)
    auth = AuthManager()
    if auth.delete_user(username):
        console.print(f"🗑  Deleted [bold]{username}[/bold]")
    else:
        console.print(f"[red]Unknown user: {username}[/red]")
        raise typer.Exit(1)


@user_app.command("deactivate")
def user_deactivate(username: str = typer.Argument(...)) -> None:
    """Soft-deactivate a user (preserves history; API keys stop working)."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    auth.deactivate_user(username)
    console.print(f"⏸  Deactivated [bold]{username}[/bold]")


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


# --- External connectors -----------------------------------------------

connector_app = typer.Typer(help="External storage / SaaS connectors (Box, SharePoint, Dropbox, GDrive, kintone, Salesforce)")
app.add_typer(connector_app, name="connector")


@connector_app.command("list")
def connector_list() -> None:
    """List all built-in connectors."""
    from praxia.connectors.registry import list_builtin

    table = Table(title="Built-in Connectors")
    table.add_column("Name", style="cyan")
    table.add_column("Install extra")
    table.add_column("Auth method")
    rows = [
        ("box", "praxia[box]", "OAuth2 access token / JWT"),
        ("sharepoint", "praxia[sharepoint]", "Microsoft Entra ID app (client credentials)"),
        ("dropbox", "praxia[dropbox]", "OAuth2 access token"),
        ("gdrive", "praxia[gdrive]", "Service account or OAuth credentials"),
        ("kintone", "praxia[kintone]", "API token or basic auth"),
        ("salesforce", "praxia[salesforce]", "Username/password+token or OAuth"),
    ]
    for name, extra, auth in rows:
        table.add_row(name, extra, auth)
    console.print(table)


@connector_app.command("pull")
def connector_pull(
    name: str = typer.Argument(..., help="Connector name (box / sharepoint / dropbox / gdrive / kintone / salesforce)"),
    path: str = typer.Argument(..., help="Source path / folder ID / SOQL query / kintone app id"),
    limit: int = typer.Option(20),
    save_to: str = typer.Option("", help="Optional directory to save items"),
    user_id: str = typer.Option("default-user"),
    role: str = typer.Option("member"),
) -> None:
    """Pull items from a connector. Subject to admin policies."""
    from praxia.auth import AuthManager
    from praxia.connectors import get_connector

    auth = AuthManager()
    auth.policies.require(
        user_id=user_id,
        role=role,
        resource_type="connector",
        resource_id=f"{name}:{path}",
        action="read",
    )

    config = _load_connector_config(name)
    conn = get_connector(name, **config)
    items = conn.pull(path, limit=limit)
    console.print(f"📥 Pulled {len(items)} item(s) from [bold]{name}[/bold]")
    if save_to:
        out_dir = Path(save_to)
        out_dir.mkdir(parents=True, exist_ok=True)
        for it in items:
            target = out_dir / it.name
            mode = "wb" if isinstance(it.content, bytes) else "w"
            with target.open(mode, encoding=None if mode == "wb" else "utf-8") as f:
                f.write(it.content)
        console.print(f"   Saved to {out_dir}/")
    else:
        for it in items[:5]:
            preview = (it.content[:200] if isinstance(it.content, str) else "<binary>") if it.content else ""
            console.print(f"  • {it.name} ({it.id}): {preview!r}")


@connector_app.command("push")
def connector_push(
    name: str = typer.Argument(...),
    path: str = typer.Argument(..., help="Destination folder/app ID / sObject API name"),
    file: str = typer.Argument(..., help="Local file or inline JSON"),
    user_id: str = typer.Option("default-user"),
    role: str = typer.Option("member"),
) -> None:
    """Push a file or record to a connector. Subject to admin policies."""
    from praxia.auth import AuthManager
    from praxia.connectors import get_connector
    from praxia.connectors.base import ConnectorItem

    auth = AuthManager()
    auth.policies.require(
        user_id=user_id,
        role=role,
        resource_type="connector",
        resource_id=f"{name}:{path}",
        action="write",
    )

    config = _load_connector_config(name)
    conn = get_connector(name, **config)
    p = Path(file)
    if p.is_file():
        body = p.read_bytes()
        item = ConnectorItem(id="", name=p.name, content=body)
    else:
        item = ConnectorItem(id="", name="praxia_inline.json", content=file)
    receipt = conn.push(path, item)
    console.print(f"📤 Pushed to [bold]{name}[/bold]: {receipt}")


def _load_connector_config(name: str) -> dict[str, str]:
    """Read connector credentials from env vars (PRAXIA_CONN_<NAME>_<KEY>)."""
    import os

    prefix = f"PRAXIA_CONN_{name.upper()}_"
    return {
        k[len(prefix):].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


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


# --- Admin: data exports / downloads ----------------------------------

admin_app = typer.Typer(help="Admin data exports for compliance / SIEM")
app.add_typer(admin_app, name="admin")


@admin_app.command("export-audit")
def admin_export_audit(
    output: str = typer.Argument(..., help="Output file path"),
    format: str = typer.Option("csv", help="csv | json | jsonl"),
    since_days: int = typer.Option(0, help="Limit to events from the last N days"),
    actor: str = typer.Option(""),
) -> None:
    """Export the audit log."""
    import time
    from praxia.auth import AuthManager

    since = (time.time() - since_days * 86400) if since_days > 0 else None
    auth = AuthManager()
    path = auth.exports.export_audit(
        output_path=output,
        format=format,  # type: ignore[arg-type]
        since=since,
        actor_id=actor or None,
    )
    console.print(f"💾 Exported audit log → [bold]{path}[/bold]")


@admin_app.command("export-users")
def admin_export_users(
    output: str = typer.Argument(...),
    format: str = typer.Option("csv"),
) -> None:
    """Export the user list (sensitive — admin only)."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    path = auth.exports.export_users(output_path=output, format=format)  # type: ignore[arg-type]
    console.print(f"💾 Exported users → [bold]{path}[/bold]")


@admin_app.command("export-usage")
def admin_export_usage(
    output: str = typer.Argument(...),
    format: str = typer.Option("csv"),
    skill: str = typer.Option("", help="Filter to one skill name"),
) -> None:
    """Export skill usage stats."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    path = auth.exports.export_skill_usage(
        output_path=output, format=format, skill_name=skill or None  # type: ignore[arg-type]
    )
    console.print(f"💾 Exported skill usage → [bold]{path}[/bold]")


@admin_app.command("export-memory")
def admin_export_memory(
    output: str = typer.Argument(..., help="Output path (for one user) or directory (for --all)"),
    user: str = typer.Option("", help="user_id; required unless --all"),
    all_users: bool = typer.Option(False, "--all", help="Export all personal memories"),
    format: str = typer.Option("jsonl"),
) -> None:
    """Export personal memory dumps for one user or all users."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    if all_users:
        paths = auth.exports.export_all_personal_memory(
            output_dir=output, format=format  # type: ignore[arg-type]
        )
        console.print(f"💾 Exported {len(paths)} user(s) → [bold]{output}/[/bold]")
    else:
        if not user:
            console.print("[red]Provide --user or --all[/red]")
            raise typer.Exit(1)
        path = auth.exports.export_personal_memory(
            user_id=user, output_path=output, format=format  # type: ignore[arg-type]
        )
        console.print(f"💾 Exported {user}'s memory → [bold]{path}[/bold]")


@admin_app.command("export-policies")
def admin_export_policies(
    output: str = typer.Argument(...),
    format: str = typer.Option("json"),
) -> None:
    """Export the access policy list."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    path = auth.exports.export_policies(output_path=output, format=format)  # type: ignore[arg-type]
    console.print(f"💾 Exported policies → [bold]{path}[/bold]")


@admin_app.command("export-shared-memory")
def admin_export_shared_memory(
    output: str = typer.Argument(...),
    format: str = typer.Option("jsonl"),
) -> None:
    """Export the shared memory blocks."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    path = auth.exports.export_shared_memory(output_path=output, format=format)  # type: ignore[arg-type]
    console.print(f"💾 Exported shared memory → [bold]{path}[/bold]")


# --- Unified configuration (single source of truth for all keys) ------------

config_app = typer.Typer(help="Manage all Praxia keys / secrets in one place")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show() -> None:
    """Show all configured keys (secrets masked)."""
    from praxia.config import PraxiaConfig

    set_keys = PraxiaConfig.list_set()
    unset_keys = PraxiaConfig.list_unset()

    if set_keys:
        table = Table(title=f"Configured ({len(set_keys)} keys)")
        table.add_column("Key", style="cyan")
        table.add_column("Category")
        table.add_column("Value")
        by_cat: dict[str, list[tuple[str, str]]] = {}
        for k, (cat, v) in set_keys.items():
            by_cat.setdefault(cat, []).append((k, v))
        for cat in sorted(by_cat):
            for k, v in sorted(by_cat[cat]):
                table.add_row(k, cat, v)
        console.print(table)
    else:
        console.print("[yellow]No keys configured yet.[/yellow]")

    if unset_keys:
        console.print(
            f"\n[dim]{len(unset_keys)} known keys are not set. "
            f"Run [bold]praxia config init[/bold] for a guided walkthrough.[/dim]"
        )


@config_app.command("get")
def config_get(key: str = typer.Argument(...)) -> None:
    """Show one key's resolved value (masks secrets)."""
    from praxia.config import KNOWN_KEYS, PraxiaConfig

    val = PraxiaConfig.get(key)
    if val is None:
        console.print(f"[yellow]{key} is not set[/yellow]")
        raise typer.Exit(1)
    is_secret = KNOWN_KEYS.get(key, ("?", False))[1]
    display = PraxiaConfig._mask(val) if is_secret else val
    console.print(f"{key} = {display}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Key name, e.g. ANTHROPIC_API_KEY"),
    value: str = typer.Argument(..., help="Value to write"),
) -> None:
    """Persist a key to .praxia/config.toml (lower precedence than env vars)."""
    from praxia.config import PraxiaConfig

    PraxiaConfig.set_persistent(key, value)
    console.print(f"✅ Saved {key} to .praxia/config.toml")


@config_app.command("init")
def config_init() -> None:
    """Interactive walkthrough — prompts for the keys most users need."""
    from praxia.config import PraxiaConfig

    console.print(
        Panel.fit(
            "[bold]Praxia config init[/bold] — interactive setup\n\n"
            "We'll walk through the keys you actually need.\n"
            "Press Enter to skip any key.\n"
            "Values are saved to [cyan].praxia/config.toml[/cyan].\n"
            "Existing environment variables take precedence.",
            border_style="cyan",
        )
    )

    sections = [
        (
            "LLM provider — pick at least one",
            [
                ("ANTHROPIC_API_KEY", "Claude (recommended)"),
                ("OPENAI_API_KEY", "ChatGPT (also enables Whisper STT + OpenAI TTS)"),
                ("GEMINI_API_KEY", "Google Gemini"),
                ("DASHSCOPE_API_KEY", "Alibaba Qwen API"),
            ],
        ),
        (
            "Memory backend (optional, default 'json' is fine)",
            [("PRAXIA_MEMORY_BACKEND", "json | mem0 | langmem | letta | zep | hindsight")],
        ),
        (
            "Auth secrets (regenerate when going to production)",
            [
                ("PRAXIA_JWT_SECRET", "Used to sign JWT tokens"),
                ("PRAXIA_TOKEN_ENC_KEY", "Used to encrypt OAuth tokens at rest"),
            ],
        ),
        (
            "OAuth (only if you'll use user-delegated OAuth — skip otherwise)",
            [
                ("PRAXIA_OAUTH_BOX_CLIENT_ID", "Box OAuth app client ID"),
                ("PRAXIA_OAUTH_BOX_CLIENT_SECRET", "Box OAuth app client secret"),
                ("PRAXIA_OAUTH_GOOGLE_CLIENT_ID", "Google OAuth client ID"),
                ("PRAXIA_OAUTH_GOOGLE_CLIENT_SECRET", "Google OAuth client secret"),
            ],
        ),
        (
            "Audio (optional)",
            [("ELEVENLABS_API_KEY", "ElevenLabs TTS (premium voices)")],
        ),
    ]
    saved = 0
    for section, keys in sections:
        console.print(f"\n[bold]{section}[/bold]")
        for key, desc in keys:
            current = PraxiaConfig.get(key)
            current_hint = " [dim](currently set; leave blank to keep)[/dim]" if current else ""
            value = typer.prompt(
                f"  {key} ({desc}){current_hint}", default="", show_default=False
            )
            if value:
                PraxiaConfig.set_persistent(key, value)
                saved += 1
    console.print(
        f"\n✅ Saved {saved} key(s) to [cyan].praxia/config.toml[/cyan]\n"
        f"Run [bold]praxia config show[/bold] to verify."
    )


@config_app.command("path")
def config_path() -> None:
    """Show where Praxia looks for keys (resolution order)."""
    from pathlib import Path

    env_exists = "✓ exists" if Path(".env").exists() else "✗ not found"
    toml_exists = "✓ exists" if Path(".praxia/config.toml").exists() else "✗ not found"
    console.print(
        Panel.fit(
            "Praxia resolves keys in this order (first match wins):\n\n"
            "  1. Process environment variables\n"
            f"  2. .env file → [cyan]{Path('.env').resolve()}[/cyan] {env_exists}\n"
            f"  3. .praxia/config.toml → [cyan]{Path('.praxia/config.toml').resolve()}[/cyan] {toml_exists}\n"
            f"  4. Built-in defaults\n\n"
            f"Current working directory: [cyan]{Path.cwd()}[/cyan]",
            border_style="cyan",
        )
    )


# --- User-delegated OAuth ----------------------------------------------------

oauth_app = typer.Typer(help="Per-user OAuth for connector access (Box / SharePoint / Drive / Dropbox / Salesforce)")
app.add_typer(oauth_app, name="oauth")


@oauth_app.command("start")
def oauth_start(
    provider: str = typer.Argument(..., help="box | microsoft | dropbox | google | salesforce"),
    user_id: str = typer.Option(..., help="Praxia user_id this token belongs to"),
    redirect_uri: str = typer.Option(
        "http://localhost:8765/callback",
        help="Redirect URI registered with the provider's OAuth app",
    ),
) -> None:
    """Print the authorization URL for a user to authorize a connector.

    Reads client credentials from
        PRAXIA_OAUTH_<PROVIDER>_CLIENT_ID
        PRAXIA_OAUTH_<PROVIDER>_CLIENT_SECRET
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

    flow = OAuthFlow.for_provider(
        provider, client_id=cid, client_secret=csec, redirect_uri=redirect_uri
    )
    url, state = flow.authorization_url(user_id=user_id)
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


@oauth_app.command("callback")
def oauth_callback(
    provider: str = typer.Argument(...),
    code: str = typer.Argument(..., help="The 'code' query param from the redirect"),
    state: str = typer.Argument(..., help="The state token returned by `oauth start`"),
    redirect_uri: str = typer.Option("http://localhost:8765/callback"),
) -> None:
    """Complete the OAuth flow with the code returned by the provider.

    NOTE: The state must match the one shown in `oauth start`. The flow
    object holds the state in-memory; for production deployments use a
    web server with persistent state storage.
    """
    console.print(
        "[yellow]CLI callback is intended for local dev/test only. "
        "For production use a real HTTP redirect handler.[/yellow]"
    )
    console.print(
        "Use the SDK form for production:\n"
        "  flow = OAuthFlow.for_provider(...)\n"
        "  url, state = flow.authorization_url(user_id=...)\n"
        "  # ... user authorizes ...\n"
        "  token = flow.exchange_code(code=..., state=...)"
    )


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
