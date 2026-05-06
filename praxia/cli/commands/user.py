"""`praxia user ...` — user + role management (admin only for most actions)."""
from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from praxia.cli._console import console

user_app = typer.Typer(help="User and role management")


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


__all__ = ["user_app"]
