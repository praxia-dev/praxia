"""HubSpot CRM connector — pull contacts/companies/deals, push notes.

Path semantics:
    pull:  "contacts"  — list recent contacts
           "companies" — list recent companies
           "deals"     — list recent deals
           "contacts/<id>" — single contact
    push:  "<object>:<id>" — creates a note attached to that record
"""
from __future__ import annotations

from typing import Any

from praxia.connectors._helpers import resolve_oauth_token
from praxia.connectors.base import Connector, ConnectorItem, _require


class HubSpotConnector:
    name = "hubspot"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        hubspot = _require("hubspot", "pip install hubspot-api-client")
        access_token = resolve_oauth_token(access_token, user_id, "hubspot")
        self._hs = hubspot.Client.create(access_token=access_token)

    def pull(self, path: str, *, limit: int = 50) -> list[ConnectorItem]:
        parts = path.split("/", 1)
        obj = parts[0]
        if obj not in ("contacts", "companies", "deals"):
            raise ValueError(f"Unsupported HubSpot object: {obj}")
        if len(parts) == 2:
            return self._get_one(obj, parts[1])
        api = getattr(self._hs.crm, obj).basic_api
        page = api.get_page(limit=min(limit, 100))
        out: list[ConnectorItem] = []
        for record in page.results:
            props = record.properties or {}
            name = (
                props.get("firstname") and f"{props['firstname']} {props.get('lastname','')}".strip()
                or props.get("name")
                or props.get("dealname")
                or record.id
            )
            content_lines = [f"{k}: {v}" for k, v in props.items() if v]
            out.append(ConnectorItem(
                id=record.id,
                name=name,
                content="\n".join(content_lines),
                mime_type="text/plain",
                metadata={"object": obj, "created_at": str(record.created_at)},
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        if ":" not in path:
            raise ValueError("Push path must be '<object>:<id>' (e.g. 'contacts:12345')")
        obj, target_id = path.split(":", 1)
        body = data.content if isinstance(data.content, str) else str(data.content)
        # Use HubSpot Notes Engagement
        from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate  # type: ignore
        note_input = SimplePublicObjectInputForCreate(
            properties={
                "hs_note_body": body[:65000],
                "hs_timestamp": "0",
            },
            associations=[{
                "to": {"id": target_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    # Default note → contact = 202; deal = 214; company = 190
                    "associationTypeId": {"contacts": 202, "deals": 214, "companies": 190}[obj],
                }],
            }],
        )
        result = self._hs.crm.objects.notes.basic_api.create(
            simple_public_object_input_for_create=note_input
        )
        return {"id": result.id}

    def _get_one(self, obj: str, record_id: str) -> list[ConnectorItem]:
        api = getattr(self._hs.crm, obj).basic_api
        record = api.get_by_id(record_id)
        props = record.properties or {}
        return [ConnectorItem(
            id=record.id,
            name=(props.get("name") or props.get("dealname") or record.id),
            content="\n".join(f"{k}: {v}" for k, v in props.items() if v),
            mime_type="text/plain",
            metadata={"object": obj},
        )]
