"""Box.com connector — Pull files from a folder, Push generated outputs."""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class BoxConnector:
    name = "box"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        enterprise_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        boxsdk = _require("boxsdk", 'pip install "praxia[box]"')

        # User-delegated OAuth: pull the user's stored token + auto-refresh
        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            tok = oauth_token_for(user_id, "box")
            access_token = tok.access_token

        if access_token:
            self._client = boxsdk.Client(
                boxsdk.OAuth2(
                    client_id=client_id, client_secret=client_secret, access_token=access_token
                )
            )
        elif enterprise_id:  # pragma: no cover — JWT path
            auth = boxsdk.JWTAuth.from_settings_file("box_jwt.json")
            self._client = boxsdk.Client(auth)
        else:
            raise ValueError(
                "Provide access_token, user_id (with stored OAuth token), "
                "or JWT settings + enterprise_id"
            )

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is the Box folder ID (e.g. "0" for root)."""
        folder = self._client.folder(folder_id=path).get()
        items = folder.get_items(limit=limit)
        out: list[ConnectorItem] = []
        for item in items:
            if item.type == "file":
                content = self._client.file(item.id).content()
                out.append(
                    ConnectorItem(
                        id=item.id,
                        name=item.name,
                        content=content,
                        mime_type="application/octet-stream",
                        metadata={"box_type": "file"},
                    )
                )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """`path` is the destination folder ID."""
        if isinstance(data, dict):
            data = ConnectorItem(
                id="",
                name=data.get("name", "praxia_output.md"),
                content=data.get("body", data.get("content", "")),
                metadata=data.get("metadata", {}),
            )
        folder = self._client.folder(folder_id=path)
        body = data.content.encode() if isinstance(data.content, str) else data.content
        from io import BytesIO
        new_file = folder.upload_stream(BytesIO(body), data.name)
        return {"id": new_file.id, "name": new_file.name, "url": f"https://app.box.com/file/{new_file.id}"}
