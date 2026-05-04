"""External storage / SaaS connectors with bi-directional Pull / Push.

Built-in connectors:
    - box         (Box.com)
    - sharepoint  (Microsoft 365 / SharePoint via Graph API)
    - dropbox     (Dropbox)
    - gdrive      (Google Drive)
    - kintone     (Cybozu kintone)
    - salesforce  (Salesforce CRM)

Each connector implements the `Connector` protocol with `pull(path)` and
`push(path, data)`. Optional SDKs are imported lazily — install only the
extras you need:

    pip install "praxia[box]"
    pip install "praxia[connectors]"   # all six

Usage:

    from praxia.connectors import get_connector

    box = get_connector("box", access_token=os.environ["BOX_TOKEN"])
    docs = box.pull("/Praxia/specs")          # list of dicts with content
    box.push("/Praxia/output", {"name": "review.md", "body": "..."})
"""
from praxia.connectors.base import (
    Connector,
    ConnectorItem,
    MissingDependencyError,
)
from praxia.connectors.registry import (
    ALL_CONNECTORS,
    get_connector,
    register_connector,
)

__all__ = [
    "Connector",
    "ConnectorItem",
    "MissingDependencyError",
    "ALL_CONNECTORS",
    "get_connector",
    "register_connector",
]
