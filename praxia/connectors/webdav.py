"""WebDAV connector — pull / push files via standard WebDAV.

Works with Nextcloud, ownCloud, generic WebDAV servers. Auth is HTTP
Basic (username + password or app token).

Path semantics:
    pull:  "<remote_path>" — directory listing OR file content
    push:  "<remote_path>" — uploads bytes to that path (overwrites)
"""
from __future__ import annotations

import base64
import os
import re
from typing import Any
from urllib import parse, request
from xml.etree import ElementTree as ET

from praxia.connectors.base import Connector, ConnectorItem


class WebDAVConnector:
    name = "webdav"
    MAX_FILE_SIZE = 5 * 1024 * 1024

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        base_url = base_url or os.getenv("PRAXIA_CONN_WEBDAV_BASE_URL")
        username = username or os.getenv("PRAXIA_CONN_WEBDAV_USERNAME")
        password = password or os.getenv("PRAXIA_CONN_WEBDAV_PASSWORD")
        if not base_url:
            raise ValueError("Provide base_url (or PRAXIA_CONN_WEBDAV_BASE_URL).")
        if not (username and password):
            raise ValueError(
                "Provide username + password (or PRAXIA_CONN_WEBDAV_USERNAME + _PASSWORD)."
            )
        self._base = base_url.rstrip("/")
        creds = f"{username}:{password}".encode()
        self._auth = "Basic " + base64.b64encode(creds).decode()

    def pull(self, path: str, *, limit: int = 50) -> list[ConnectorItem]:
        url = self._url(path)
        # PROPFIND with Depth: 1 to list directory; Depth: 0 = the resource itself
        req = request.Request(
            url,
            method="PROPFIND",
            headers={
                "Authorization": self._auth,
                "Depth": "1",
                "Accept": "application/xml",
                "Content-Type": "application/xml",
            },
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                xml = resp.read()
        except Exception as e:
            # Fallback: GET as a file
            return self._fetch_one(path, e)

        ns = {"d": "DAV:"}
        root = ET.fromstring(xml)
        out: list[ConnectorItem] = []
        for response in root.findall("d:response", ns)[:limit + 1]:
            href_el = response.find("d:href", ns)
            if href_el is None or not href_el.text:
                continue
            href = parse.unquote(href_el.text)
            # Skip the directory itself
            if href.rstrip("/").endswith(path.rstrip("/")):
                continue
            propstat = response.find("d:propstat/d:prop", ns)
            if propstat is None:
                continue
            ctype_el = propstat.find("d:getcontenttype", ns)
            length_el = propstat.find("d:getcontentlength", ns)
            ctype = ctype_el.text if ctype_el is not None and ctype_el.text else "application/octet-stream"
            size = int(length_el.text) if length_el is not None and length_el.text else 0
            name = href.rstrip("/").rsplit("/", 1)[-1]
            content: str | bytes = b""
            if size <= self.MAX_FILE_SIZE and not href.endswith("/"):
                content = self._download(href)
            out.append(ConnectorItem(
                id=href,
                name=name,
                content=content,
                mime_type=ctype,
                metadata={"size": size, "href": href},
            ))
            if len(out) >= limit:
                break
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        url = self._url(path)
        body = data.content if isinstance(data.content, (bytes, bytearray)) else str(data.content).encode()
        req = request.Request(
            url,
            data=body,
            method="PUT",
            headers={
                "Authorization": self._auth,
                "Content-Type": data.mime_type or "application/octet-stream",
            },
        )
        with request.urlopen(req, timeout=60) as resp:
            return {"path": path, "size": len(body), "status": resp.status}

    # --- helpers ---------------------------------------------------------

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else "/" + path
        return self._base + parse.quote(path, safe="/")

    def _download(self, href: str) -> bytes:
        # `href` may be absolute or relative to base
        if re.match(r"^https?://", href):
            url = href
        else:
            url = self._base + (href if href.startswith("/") else "/" + href)
        req = request.Request(url, headers={"Authorization": self._auth})
        with request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def _fetch_one(self, path: str, err: Exception) -> list[ConnectorItem]:
        try:
            data = self._download(parse.quote(path, safe="/"))
        except Exception:
            raise err
        return [ConnectorItem(
            id=path,
            name=path.rstrip("/").rsplit("/", 1)[-1],
            content=data,
            mime_type="application/octet-stream",
            metadata={"path": path, "size": len(data)},
        )]
