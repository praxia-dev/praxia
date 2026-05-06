"""`praxia admin ...` — data exports + memory policy (admin only)."""
from __future__ import annotations

import typer
from rich.table import Table

from praxia.cli._console import console

admin_app = typer.Typer(help="Admin data exports for compliance / SIEM")


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
        output_path=output, format=format,  # type: ignore[arg-type]
        since=since, actor_id=actor or None,
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
        output_path=output, format=format, skill_name=skill or None,  # type: ignore[arg-type]
    )
    console.print(f"💾 Exported skill usage → [bold]{path}[/bold]")


@admin_app.command("export-memory")
def admin_export_memory(
    output: str = typer.Argument(..., help="Output path (one user) or directory (--all)"),
    user: str = typer.Option("", help="user_id; required unless --all"),
    all_users: bool = typer.Option(False, "--all", help="Export all personal memories"),
    format: str = typer.Option("jsonl"),
) -> None:
    """Export personal memory dumps for one user or all users."""
    from praxia.auth import AuthManager

    auth = AuthManager()
    if all_users:
        paths = auth.exports.export_all_personal_memory(
            output_dir=output, format=format,  # type: ignore[arg-type]
        )
        console.print(f"💾 Exported {len(paths)} user(s) → [bold]{output}/[/bold]")
    else:
        if not user:
            console.print("[red]Provide --user or --all[/red]")
            raise typer.Exit(1)
        path = auth.exports.export_personal_memory(
            user_id=user, output_path=output, format=format,  # type: ignore[arg-type]
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


# --- Memory policy ---------------------------------------------------------

@admin_app.command("memory-policy-show")
def admin_memory_policy_show(
    storage_dir: str = typer.Option(".praxia", help="Praxia storage directory"),
) -> None:
    """Show the current admin-level memory policy."""
    from praxia.memory.policy import MemoryAdminPolicy

    policy = MemoryAdminPolicy.load(storage_dir)
    table = Table(title="Memory Admin Policy")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("enforced_backend", str(policy.enforced_backend or "—"))
    table.add_row("default_backend", policy.default_backend)
    table.add_row("allowed_backends", ", ".join(policy.allowed_backends) or "(any)")
    table.add_row("default_mode", policy.default_mode)
    table.add_row("mode_locked", str(policy.mode_locked))
    table.add_row("accumulate_locked_to", ", ".join(policy.accumulate_locked_to) or "—")
    console.print(table)


@admin_app.command("memory-policy-set")
def admin_memory_policy_set(
    storage_dir: str = typer.Option(".praxia"),
    enforced_backend: str = typer.Option("", help="Pin all users to this backend (empty = no enforcement)"),
    default_backend: str = typer.Option("", help="Backend used when user has no preference"),
    allowed: str = typer.Option("", help="Comma-separated whitelist of backends (empty = any)"),
    default_mode: str = typer.Option("", help="accumulate | read_only"),
    mode_locked: bool = typer.Option(False, "--mode-locked/--mode-unlocked"),
    accumulate_locked_roles: str = typer.Option(
        "", help="Comma-separated roles forced to accumulate (e.g. operator,admin)"
    ),
) -> None:
    """Update the admin-level memory policy. Empty options leave existing values."""
    from praxia.memory.policy import MemoryAdminPolicy

    policy = MemoryAdminPolicy.load(storage_dir)
    if enforced_backend:
        policy.enforced_backend = None if enforced_backend == "none" else enforced_backend
    if default_backend:
        policy.default_backend = default_backend
    if allowed:
        policy.allowed_backends = [b.strip() for b in allowed.split(",") if b.strip()]
    if default_mode:
        if default_mode not in ("accumulate", "read_only"):
            console.print("[red]default_mode must be 'accumulate' or 'read_only'[/red]")
            raise typer.Exit(1)
        policy.default_mode = default_mode  # type: ignore[assignment]
    policy.mode_locked = mode_locked
    if accumulate_locked_roles:
        policy.accumulate_locked_to = [
            r.strip() for r in accumulate_locked_roles.split(",") if r.strip()
        ]
    path = policy.save(storage_dir)
    console.print(f"💾 Memory policy updated → [bold]{path}[/bold]")


__all__ = ["admin_app"]
