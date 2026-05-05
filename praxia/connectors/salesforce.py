"""Salesforce CRM connector — Pull records via SOQL, Push by sObject create."""
from __future__ import annotations

import json
from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class SalesforceConnector:
    name = "salesforce"

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        security_token: str | None = None,
        instance_url: str | None = None,
        access_token: str | None = None,
        domain: str = "login",
        user_id: str | None = None,
    ) -> None:
        _require("simple_salesforce", 'pip install "praxia[salesforce]"')
        from simple_salesforce import Salesforce

        # User-delegated OAuth — preferred
        if user_id:
            from praxia.connectors.oauth import oauth_token_for
            tok = oauth_token_for(user_id, "salesforce")
            access_token = tok.access_token
            instance_url = tok.extra.get("instance_url") or instance_url

        if access_token and instance_url:
            self._sf = Salesforce(instance_url=instance_url, session_id=access_token)
        elif username and password and security_token:
            self._sf = Salesforce(
                username=username,
                password=password,
                security_token=security_token,
                domain=domain,
            )
        else:
            raise ValueError(
                "Provide one of: user_id (with stored OAuth token), "
                "(instance_url + access_token), or (username + password + security_token)"
            )

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` is a SOQL query, e.g. "SELECT Id, Name FROM Account WHERE Industry = 'Manufacturing'"."""
        query = f"{path} LIMIT {limit}" if "LIMIT" not in path.upper() else path
        result = self._sf.query(query)
        out: list[ConnectorItem] = []
        for rec in result.get("records", []):
            attrs = rec.get("attributes", {})
            obj_type = attrs.get("type", "sObject")
            rec_id = rec.get("Id", "")
            out.append(
                ConnectorItem(
                    id=rec_id,
                    name=f"{obj_type}_{rec_id}",
                    content=json.dumps(rec, ensure_ascii=False),
                    mime_type="application/json",
                    metadata={"object_type": obj_type},
                )
            )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """`path` is the sObject API name (e.g. "Lead", "Account", "Note__c").

        `data.content` should be JSON of the record fields.
        """
        if isinstance(data, dict):
            content = data.get("body", data.get("content", "{}"))
            data = ConnectorItem(id="", name=path, content=content)
        record = json.loads(data.content) if isinstance(data.content, str) else json.loads(data.content.decode())
        sobject = getattr(self._sf, path)
        result = sobject.create(record)
        return result
