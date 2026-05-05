"""Google Drive connector."""
from __future__ import annotations

from io import BytesIO
from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class GoogleDriveConnector:
    name = "gdrive"

    def __init__(
        self,
        *,
        service_account_file: str | None = None,
        oauth_credentials: Any = None,
        user_id: str | None = None,
    ) -> None:
        _require("googleapiclient", 'pip install "praxia[gdrive]"')
        from googleapiclient.discovery import build
        if user_id:
            # User-delegated OAuth — fetch from token store
            from google.oauth2.credentials import Credentials
            from praxia.connectors.oauth import oauth_token_for
            tok = oauth_token_for(user_id, "google")
            creds = Credentials(
                token=tok.access_token,
                refresh_token=tok.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/drive"],
            )
        elif service_account_file:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=["https://www.googleapis.com/auth/drive"],
            )
        elif oauth_credentials is not None:
            creds = oauth_credentials
        else:
            raise ValueError(
                "Provide user_id (with stored OAuth token), service_account_file, "
                "or oauth_credentials"
            )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is the parent folder ID."""
        from googleapiclient.http import MediaIoBaseDownload
        results = (
            self._service.files()
            .list(
                q=f"'{path}' in parents and trashed=false",
                pageSize=limit,
                fields="files(id, name, mimeType)",
            )
            .execute()
        )
        out: list[ConnectorItem] = []
        for f in results.get("files", []):
            content = b""
            try:
                req = self._service.files().get_media(fileId=f["id"])
                buf = BytesIO()
                downloader = MediaIoBaseDownload(buf, req)
                done = False
                while not done:
                    _status, done = downloader.next_chunk()
                content = buf.getvalue()
            except Exception:
                # Google Docs etc need export — skip for skeleton
                pass
            out.append(
                ConnectorItem(
                    id=f["id"],
                    name=f["name"],
                    content=content,
                    mime_type=f.get("mimeType", "application/octet-stream"),
                )
            )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        from googleapiclient.http import MediaIoBaseUpload
        if isinstance(data, dict):
            data = ConnectorItem(id="", name=data.get("name", "praxia_output.md"), content=data.get("body", ""))
        body = data.content.encode() if isinstance(data.content, str) else data.content
        media = MediaIoBaseUpload(BytesIO(body), mimetype=data.mime_type)
        meta = {"name": data.name, "parents": [path]}
        f = self._service.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
        return {"id": f["id"], "web_url": f.get("webViewLink")}
