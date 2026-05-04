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
    ) -> None:
        _require("requests", 'pip install requests')
        import requests
        self._requests = requests
        self._base = f"https://{subdomain}.cybozu.com/k/v1"
        self._headers: dict[str, str] = {}
        if api_token:
            self._headers["X-Cybozu-API-Token"] = api_token
        elif username and password:
            auth = base64.b64encode(f"{username}:{password}".encode()).decode()
            self._headers["X-Cybozu-Authorization"] = auth
        else:
            raise ValueError("Provide api_token or username+password")

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
