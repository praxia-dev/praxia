"""Base abstractions for storage / SaaS connectors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class MissingDependencyError(ImportError):
    """Raised when a connector's optional SDK isn't installed.

    Includes a clear pip install hint in the message.
    """


@dataclass
class ConnectorItem:
    """One pulled item — could be a file, record, or document."""

    id: str
    name: str
    content: str | bytes
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = field(default_factory=dict)


class Connector(Protocol):
    """Every connector implements this protocol."""

    name: str

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """Read items from `path` (folder, dataset, query, etc.)."""
        ...

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """Write `data` to `path`. Returns provider-specific receipt."""
        ...


def _require(module_name: str, install_hint: str) -> Any:
    """Helper: import a module, raise MissingDependencyError on failure."""
    try:
        return __import__(module_name)
    except ImportError as e:
        raise MissingDependencyError(
            f"This connector requires `{module_name}`. Install with:\n  {install_hint}"
        ) from e
