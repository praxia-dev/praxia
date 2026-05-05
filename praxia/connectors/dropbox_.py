"""Dropbox connector."""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class DropboxConnector:
    name = "dropbox"

    def __init__(self, *, access_token: str | None = None, user_id: str | None = None) -> None:
        dropbox = _require("dropbox", 'pip install "praxia[dropbox]"')
        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, "dropbox").access_token
        if not access_token:
            raise ValueError("Provide access_token or user_id with a stored OAuth token")
        self._client = dropbox.Dropbox(access_token)

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is the folder path (e.g. "/Praxia/specs")."""
        result = self._client.files_list_folder(path, limit=limit)
        out: list[ConnectorItem] = []
        for entry in result.entries:
            if entry.__class__.__name__ == "FileMetadata":
                _, resp = self._client.files_download(entry.path_lower)
                out.append(
                    ConnectorItem(
                        id=entry.id,
                        name=entry.name,
                        content=resp.content,
                        mime_type="application/octet-stream",
                        metadata={"path": entry.path_display},
                    )
                )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(id="", name=data.get("name", "praxia_output.md"), content=data.get("body", ""))
        body = data.content.encode() if isinstance(data.content, str) else data.content
        full_path = f"{path.rstrip('/')}/{data.name}"
        result = self._client.files_upload(body, full_path, mode=__import__("dropbox").files.WriteMode("overwrite"))
        return {"id": result.id, "path": result.path_display, "size": result.size}
