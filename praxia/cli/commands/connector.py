"""`praxia connector ...` — list / pull / push for the 20 built-in connectors."""
from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.table import Table

from praxia.cli._console import console

connector_app = typer.Typer(
    help="External storage / SaaS connectors (20 built-in)"
)


@connector_app.command("list")
def connector_list() -> None:
    """List all built-in connectors."""
    from praxia.connectors.registry import list_builtin  # noqa: F401  (registry side-effect)

    table = Table(title="Built-in Connectors")
    table.add_column("Name", style="cyan")
    table.add_column("Install extra")
    table.add_column("Auth method")
    rows = [
        # v1.0
        ("box", "praxia[box]", "OAuth2 access token / JWT"),
        ("sharepoint", "praxia[sharepoint]", "Microsoft Entra ID app"),
        ("dropbox", "praxia[dropbox]", "OAuth2"),
        ("gdrive", "praxia[gdrive]", "Service account or OAuth"),
        ("kintone", "praxia[kintone]", "API token or basic"),
        ("salesforce", "praxia[salesforce]", "Username+token or OAuth"),
        # Tier 1 (v1.1)
        ("notion", "praxia[notion]", "OAuth (Notion)"),
        ("confluence", "(stdlib)", "OAuth (Atlassian)"),
        ("jira", "(stdlib)", "OAuth (Atlassian)"),
        ("slack", "(stdlib)", "OAuth (Slack)"),
        ("teams", "(stdlib)", "OAuth (Microsoft, ChannelMessage scopes)"),
        # Tier 2 (v1.1)
        ("github", "praxia[github]", "OAuth (GitHub)"),
        ("hubspot", "praxia[hubspot]", "OAuth (HubSpot)"),
        ("zendesk", "(stdlib)", "OAuth or API token"),
        ("linear", "(stdlib)", "OAuth or API key"),
        ("s3", "praxia[s3]", "AWS IAM (boto3 chain)"),
        ("azure-blob", "praxia[azure-blob]", "Azure DefaultAzureCredential / SAS / connstr"),
        ("gcs", "praxia[gcs]", "GCP ADC / service account JSON"),
        ("webdav", "(stdlib)", "HTTP Basic"),
        ("email", "(stdlib + optional [gdrive] for gmail)", "IMAP/SMTP / OAuth"),
    ]
    for name, extra, auth in rows:
        table.add_row(name, extra, auth)
    console.print(table)


@connector_app.command("pull")
def connector_pull(
    name: str = typer.Argument(..., help="Connector name"),
    path: str = typer.Argument(..., help="Source path / folder ID / SOQL query / etc."),
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
        user_id=user_id, role=role,
        resource_type="connector", resource_id=f"{name}:{path}", action="read",
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
    path: str = typer.Argument(..., help="Destination path / app ID / sObject API name"),
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
        user_id=user_id, role=role,
        resource_type="connector", resource_id=f"{name}:{path}", action="write",
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
    prefix = f"PRAXIA_CONN_{name.upper()}_"
    return {
        k[len(prefix):].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


__all__ = ["connector_app"]
