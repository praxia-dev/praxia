"""`praxia config ...` — show / get / set / init / path for the unified key store."""
from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from praxia.cli._console import console

config_app = typer.Typer(help="Manage all Praxia keys / secrets in one place")


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


__all__ = ["config_app"]
