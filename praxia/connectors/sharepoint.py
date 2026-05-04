"""SharePoint / Microsoft 365 connector — via Graph API."""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class SharePointConnector:
    name = "sharepoint"

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        site_id: str | None = None,
    ) -> None:
        msal = _require("msal", 'pip install "praxia[sharepoint]"')
        _require("requests", 'pip install requests')
        import requests
        self._app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        result = self._app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        self._token = result.get("access_token")
        if not self._token:
            raise RuntimeError(f"SharePoint auth failed: {result.get('error_description')}")
        self._site_id = site_id
        self._requests = requests

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is "<drive_id>:<folder_path>"."""
        drive_id, folder = path.split(":", 1) if ":" in path else (path, "")
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{folder}:/children?$top={limit}"
        resp = self._requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        out: list[ConnectorItem] = []
        for item in resp.json().get("value", []):
            if "file" in item:
                content_url = item.get("@microsoft.graph.downloadUrl")
                content = b""
                if content_url:
                    content_resp = self._requests.get(content_url, timeout=60)
                    content_resp.raise_for_status()
                    content = content_resp.content
                out.append(
                    ConnectorItem(
                        id=item["id"],
                        name=item["name"],
                        content=content,
                        mime_type=item.get("file", {}).get("mimeType", "application/octet-stream"),
                        metadata={"web_url": item.get("webUrl")},
                    )
                )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """`path` is "<drive_id>:<folder_path>"."""
        if isinstance(data, dict):
            data = ConnectorItem(id="", name=data.get("name", "praxia_output.md"), content=data.get("body", ""))
        drive_id, folder = path.split(":", 1) if ":" in path else (path, "")
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{folder}/{data.name}:/content"
        body = data.content.encode() if isinstance(data.content, str) else data.content
        resp = self._requests.put(url, headers=self._headers(), data=body, timeout=60)
        resp.raise_for_status()
        return {"id": resp.json().get("id"), "web_url": resp.json().get("webUrl")}
