"""SCIM 2.0 implementation — User resource only (Group support is a future addition).

This module provides:
    - SCIMUser dataclass (the on-the-wire representation)
    - Mapping functions between SCIM and Praxia's User
    - A FastAPI APIRouter that an operator mounts on the main app

Spec: RFC 7643 / RFC 7644.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from praxia.auth import AuthManager, Role


# --- SCIM resource model ---------------------------------------------------

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST_RESPONSE_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


@dataclass
class SCIMUser:
    """Subset of SCIM User attributes Praxia handles."""

    id: str
    userName: str
    active: bool = True
    name: dict[str, str] = field(default_factory=dict)
    emails: list[dict[str, Any]] = field(default_factory=list)
    externalId: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemas": [SCIM_USER_SCHEMA],
            "id": self.id,
            "userName": self.userName,
            "active": self.active,
            "name": self.name or None,
            "emails": self.emails or None,
            "externalId": self.externalId,
            "meta": {
                **self.meta,
                "resourceType": "User",
                "location": f"/scim/v2/Users/{self.id}",
            },
        }


def map_praxia_user_to_scim(user: Any) -> SCIMUser:
    """Praxia User → SCIMUser."""
    primary_email = []
    if getattr(user, "email", None):
        primary_email = [{"value": user.email, "primary": True, "type": "work"}]
    return SCIMUser(
        id=user.id,
        userName=user.username,
        active=getattr(user, "is_active", True),
        emails=primary_email,
        meta={
            "created": _to_iso(getattr(user, "created_at", None)),
            "lastModified": _to_iso(getattr(user, "last_login_at", None)),
        },
    )


def map_scim_user_to_praxia_kwargs(scim: dict[str, Any]) -> dict[str, Any]:
    """SCIM User payload → kwargs for AuthManager.create_user."""
    username = scim.get("userName")
    if not username:
        raise ValueError("SCIM User payload missing userName")

    email = None
    for e in scim.get("emails") or []:
        if e.get("primary") or e.get("type") == "work":
            email = e.get("value")
            break
    if not email and (scim.get("emails") or []):
        email = scim["emails"][0].get("value")

    # Default role: MEMBER. IdPs can later promote via PATCH or via PRAXIA_SCIM_DEFAULT_ROLE.
    default_role = os.getenv("PRAXIA_SCIM_DEFAULT_ROLE", "member").lower()
    try:
        role = Role(default_role)
    except ValueError:
        role = Role.MEMBER

    return {"username": username, "email": email, "role": role}


def _to_iso(t: Any) -> str | None:
    """Epoch float → ISO 8601 with 'Z'."""
    if t is None:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(t)))
    except (TypeError, ValueError):
        return None


# --- FastAPI router -------------------------------------------------------

def scim_router(
    auth: AuthManager | None = None,
    *,
    bearer_token_env: str = "PRAXIA_SCIM_TOKEN",
):
    """Build a FastAPI APIRouter for /scim/v2/.

    Example mount:
        from fastapi import FastAPI
        from praxia.scim import scim_router
        app = FastAPI()
        app.include_router(scim_router(), prefix="/scim/v2")
    """
    try:
        from fastapi import APIRouter, HTTPException, Header, Query
        from fastapi.responses import JSONResponse
    except ImportError as e:
        raise ImportError(
            "FastAPI is required for the SCIM router. "
            "Install with: pip install 'praxia[server]'"
        ) from e

    auth = auth or AuthManager()
    router = APIRouter()

    def _verify_token(authorization: str | None) -> None:
        token = os.getenv(bearer_token_env, "")
        if not token:
            raise HTTPException(503, "SCIM is not configured (PRAXIA_SCIM_TOKEN missing)")
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Missing bearer token")
        provided = authorization.split(" ", 1)[1].strip()
        # Constant-time compare
        from hmac import compare_digest
        if not compare_digest(provided, token):
            raise HTTPException(401, "Invalid SCIM token")

    @router.get("/ServiceProviderConfig")
    def service_provider_config():
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {"supported": True},
            "filter": {"supported": True, "maxResults": 200},
            "bulk": {"supported": False},
            "changePassword": {"supported": False},
            "etag": {"supported": False},
            "sort": {"supported": False},
            "authenticationSchemes": [{
                "name": "OAuth Bearer Token",
                "type": "oauthbearertoken",
                "primary": True,
            }],
        }

    @router.get("/Schemas")
    def schemas():
        return {
            "schemas": [LIST_RESPONSE_SCHEMA],
            "totalResults": 1,
            "Resources": [{"id": SCIM_USER_SCHEMA}],
        }

    @router.get("/ResourceTypes")
    def resource_types():
        return {
            "schemas": [LIST_RESPONSE_SCHEMA],
            "totalResults": 1,
            "Resources": [{
                "id": "User",
                "name": "User",
                "endpoint": "/Users",
                "schema": SCIM_USER_SCHEMA,
            }],
        }

    @router.get("/Users")
    def list_users(
        authorization: str | None = Header(default=None),
        filter: str | None = Query(default=None),
        startIndex: int = Query(default=1, ge=1),
        count: int = Query(default=100, ge=0, le=200),
    ):
        _verify_token(authorization)
        users = list(auth.users.all())

        # SCIM filter (very minimal — `userName eq "alice"`)
        if filter:
            m = re.match(r'^\s*userName\s+eq\s+"([^"]+)"\s*$', filter)
            if m:
                wanted = m.group(1)
                users = [u for u in users if u.username == wanted]

        total = len(users)
        # SCIM pages are 1-indexed
        page = users[startIndex - 1 : startIndex - 1 + count]
        return {
            "schemas": [LIST_RESPONSE_SCHEMA],
            "totalResults": total,
            "startIndex": startIndex,
            "itemsPerPage": len(page),
            "Resources": [map_praxia_user_to_scim(u).to_dict() for u in page],
        }

    @router.get("/Users/{user_id}")
    def get_user(
        user_id: str,
        authorization: str | None = Header(default=None),
    ):
        _verify_token(authorization)
        user = auth.users.get_by_id(user_id) if hasattr(auth.users, "get_by_id") else None
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        return map_praxia_user_to_scim(user).to_dict()

    @router.post("/Users", status_code=201)
    def create_user(
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ):
        _verify_token(authorization)
        try:
            kwargs = map_scim_user_to_praxia_kwargs(body)
        except ValueError as e:
            raise HTTPException(400, str(e))
        existing = auth.users.get_by_username(kwargs["username"])
        if existing:
            return JSONResponse(
                status_code=409,
                content={"schemas": [ERROR_SCHEMA], "detail": "User already exists", "status": "409"},
            )
        new_user, _ = auth.create_user(**kwargs)
        return map_praxia_user_to_scim(new_user).to_dict()

    @router.put("/Users/{user_id}")
    def replace_user(
        user_id: str,
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ):
        _verify_token(authorization)
        user = auth.users.get_by_id(user_id) if hasattr(auth.users, "get_by_id") else None
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        # Update fields
        try:
            kwargs = map_scim_user_to_praxia_kwargs(body)
            email = kwargs.get("email")
            updated = auth.update_user(user.username, email=email)
        except Exception as e:
            raise HTTPException(400, str(e))
        # Activation flip — both directions are honored.
        # Some IdPs (Okta, Entra) deprovision via SCIM and later reactivate
        # the same record; silently no-op'ing reactivation broke that flow.
        if "active" in body:
            target = bool(body["active"])
            if target and not updated.is_active:
                updated = auth.update_user(updated.username, is_active=True)
            elif not target and updated.is_active:
                auth.deactivate_user(updated.username)
                updated = auth.users.get_by_username(updated.username)
        return map_praxia_user_to_scim(updated).to_dict()

    @router.patch("/Users/{user_id}")
    def patch_user(
        user_id: str,
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ):
        _verify_token(authorization)
        user = auth.users.get_by_id(user_id) if hasattr(auth.users, "get_by_id") else None
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        # Apply each operation
        for op in body.get("Operations", []):
            path = (op.get("path") or "").lower()
            value = op.get("value")
            if path == "active" or (isinstance(value, dict) and "active" in value):
                active = value if isinstance(value, bool) else value.get("active")
                if active is False:
                    auth.deactivate_user(user.username)
        return map_praxia_user_to_scim(
            auth.users.get_by_username(user.username)
        ).to_dict()

    @router.delete("/Users/{user_id}", status_code=204)
    def delete_user(
        user_id: str,
        authorization: str | None = Header(default=None),
    ):
        _verify_token(authorization)
        user = auth.users.get_by_id(user_id) if hasattr(auth.users, "get_by_id") else None
        if not user:
            raise HTTPException(404, f"User {user_id} not found")
        auth.delete_user(user.username)
        return None

    return router
