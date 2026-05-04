"""Connector factory + registry."""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector

ALL_CONNECTORS: dict[str, type] = {}


def register_connector(name: str, cls: type) -> None:
    ALL_CONNECTORS[name] = cls


def get_connector(name: str, **config: Any) -> Connector:
    """Construct a connector by name.

    Lazy-imports the module so optional SDKs stay optional.
    """
    name = name.lower()
    if name == "box":
        from praxia.connectors.box import BoxConnector
        return BoxConnector(**config)
    if name == "sharepoint":
        from praxia.connectors.sharepoint import SharePointConnector
        return SharePointConnector(**config)
    if name == "dropbox":
        from praxia.connectors.dropbox_ import DropboxConnector
        return DropboxConnector(**config)
    if name == "gdrive":
        from praxia.connectors.gdrive import GoogleDriveConnector
        return GoogleDriveConnector(**config)
    if name == "kintone":
        from praxia.connectors.kintone import KintoneConnector
        return KintoneConnector(**config)
    if name == "salesforce":
        from praxia.connectors.salesforce import SalesforceConnector
        return SalesforceConnector(**config)
    if name in ALL_CONNECTORS:
        return ALL_CONNECTORS[name](**config)
    raise ValueError(
        f"Unknown connector: {name!r}. "
        f"Built-in: box, sharepoint, dropbox, gdrive, kintone, salesforce"
    )


def list_builtin() -> list[str]:
    return ["box", "sharepoint", "dropbox", "gdrive", "kintone", "salesforce"]
