"""Connector registry — uses praxia.extensions.Registry.

Adding a new connector is now a single-step process:

    1. Subclass `Connector` (or implement the protocol).
    2. Either:
       a. Decorate it: `@CONNECTORS.register_decorator("my_crm")`
       b. Or declare an entry-point in your package's pyproject.toml:
          [project.entry-points."praxia.connectors"]
          my_crm = "my_pkg.my_crm:MyCRMConnector"

The 6 built-in connectors register themselves below. Third-party connectors
get discovered automatically via entry points — **no edit to this file**.
"""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector
from praxia.extensions import Registry, lazy

CONNECTORS: Registry[Connector] = Registry(
    name="connector",
    entry_point_group="praxia.connectors",
)

# Built-in registrations (lazy so optional SDKs stay optional)
CONNECTORS.register("box", lazy("praxia.connectors.box:BoxConnector"))
CONNECTORS.register("sharepoint", lazy("praxia.connectors.sharepoint:SharePointConnector"))
CONNECTORS.register("dropbox", lazy("praxia.connectors.dropbox_:DropboxConnector"))
CONNECTORS.register("gdrive", lazy("praxia.connectors.gdrive:GoogleDriveConnector"))
CONNECTORS.register("kintone", lazy("praxia.connectors.kintone:KintoneConnector"))
CONNECTORS.register("salesforce", lazy("praxia.connectors.salesforce:SalesforceConnector"))
# Tier 1
CONNECTORS.register("notion", lazy("praxia.connectors.notion:NotionConnector"))
CONNECTORS.register("confluence", lazy("praxia.connectors.confluence:ConfluenceConnector"))
CONNECTORS.register("jira", lazy("praxia.connectors.jira:JiraConnector"))
CONNECTORS.register("slack", lazy("praxia.connectors.slack:SlackConnector"))
CONNECTORS.register("teams", lazy("praxia.connectors.teams:TeamsConnector"))
# Tier 2
CONNECTORS.register("github", lazy("praxia.connectors.github:GitHubConnector"))
CONNECTORS.register("hubspot", lazy("praxia.connectors.hubspot:HubSpotConnector"))
CONNECTORS.register("zendesk", lazy("praxia.connectors.zendesk:ZendeskConnector"))
CONNECTORS.register("linear", lazy("praxia.connectors.linear:LinearConnector"))
CONNECTORS.register("s3", lazy("praxia.connectors.s3:S3Connector"))
CONNECTORS.register("azure-blob", lazy("praxia.connectors.azure_blob:AzureBlobConnector"))
CONNECTORS.register("gcs", lazy("praxia.connectors.gcs:GcsConnector"))
CONNECTORS.register("webdav", lazy("praxia.connectors.webdav:WebDAVConnector"))
# Email (multi-backend: imap / gmail / outlook)
CONNECTORS.register("email", lazy("praxia.connectors.email_:EmailConnector"))


# --- Public API (kept for backwards compatibility) ---------------------------

# Legacy mapping kept so existing callers keep working
ALL_CONNECTORS: dict[str, type] = {}


def register_connector(name: str, cls: type) -> None:
    """Legacy direct registration. Prefer `@CONNECTORS.register_decorator`."""
    CONNECTORS.register(name, cls)
    ALL_CONNECTORS[name] = cls


def get_connector(name: str, **config: Any) -> Connector:
    """Construct a connector by name (instantiates with config kwargs)."""
    try:
        cls = CONNECTORS.get(name.lower())
    except KeyError:
        raise ValueError(
            f"Unknown connector: {name!r}. "
            f"Built-in: box, sharepoint, dropbox, gdrive, kintone, salesforce. "
            f"Currently registered: {CONNECTORS.list()}"
        )
    return cls(**config)


def list_builtin() -> list[str]:
    """All registered connector names (built-in + third-party via entry-points)."""
    return CONNECTORS.list()
