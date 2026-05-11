"""Cybozu kintone connector — Pull records from an app, Push records back."""
from __future__ import annotations

import base64
import json
from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class KintoneConnector:
    name = "kintone"

    def __init__(
        self,
        *,
        subdomain: str,
        api_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Connect to a kintone tenant.

        Three auth modes (highest priority first):

        1. **Per-user OAuth** (recommended for enterprise) — pass ``user_id``
           and a previously-stored OAuth token will be used. kintone's native
           per-user permissions apply, so each Praxia user only sees records
           their kintone account can access.
        2. **OAuth access token** — pass ``access_token`` directly.
        3. **API token** — legacy per-app static token (kintone's
           ``X-Cybozu-API-Token``). Bound to the app, not the user.
        4. **Username + password** — Basic auth fallback (kintone's
           ``X-Cybozu-Authorization``). Discouraged for new deployments.
        """
        _require("requests", 'pip install requests')
        import requests
        self._requests = requests
        self._base = f"https://{subdomain}.cybozu.com/k/v1"
        self._headers: dict[str, str] = {}

        # 1. Per-user OAuth: fetch the stored token (auto-refreshes if expired)
        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            tok = oauth_token_for(user_id, "kintone")
            access_token = tok.access_token

        if access_token:
            self._headers["Authorization"] = f"Bearer {access_token}"
        elif api_token:
            self._headers["X-Cybozu-API-Token"] = api_token
        elif username and password:
            auth = base64.b64encode(f"{username}:{password}".encode()).decode()
            self._headers["X-Cybozu-Authorization"] = auth
        else:
            raise ValueError(
                "Provide access_token, user_id (with stored OAuth token), "
                "api_token, or username+password"
            )

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is "<app_id>" or "<app_id>?<query>".

        Example: "42?status = 'open'"
        """
        if "?" in path:
            app_id, query = path.split("?", 1)
        else:
            app_id, query = path, ""
        params = {"app": app_id, "query": f"{query} limit {limit}".strip()}
        resp = self._requests.get(
            f"{self._base}/records.json", params=params, headers=self._headers, timeout=30
        )
        resp.raise_for_status()
        out: list[ConnectorItem] = []
        for rec in resp.json().get("records", []):
            rec_id = rec.get("$id", {}).get("value", "")
            out.append(
                ConnectorItem(
                    id=rec_id,
                    name=f"record_{rec_id}",
                    content=json.dumps(rec, ensure_ascii=False),
                    mime_type="application/json",
                    metadata={"app_id": app_id},
                )
            )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """`path` is the app ID. `data.content` should be JSON of record fields."""
        if isinstance(data, dict):
            content = data.get("body", data.get("content", "{}"))
            data = ConnectorItem(id="", name="kintone_record", content=content)
        record = json.loads(data.content) if isinstance(data.content, str) else json.loads(data.content.decode())
        body = {"app": path, "record": record}
        resp = self._requests.post(
            f"{self._base}/record.json", json=body, headers=self._headers, timeout=30
        )
        resp.raise_for_status()
        return resp.json()
