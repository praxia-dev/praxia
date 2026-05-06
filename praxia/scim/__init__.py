"""SCIM 2.0 provisioning — auto-create / update / deactivate Praxia users
from your IdP (Okta, Azure AD / Entra ID, JumpCloud, OneLogin).

This module exposes a SCIM 2.0 v2 server that an external IdP can target
for User provisioning. Praxia maps:

    SCIM User  →  praxia.auth.User
    active     →  is_active
    emails[primary]  →  email
    userName        →  username
    SCIM ID    →  Praxia user.id

Endpoints (mounted under `/scim/v2/` by default):

    GET  /scim/v2/Users        — list / filter (?filter=userName eq "alice")
    GET  /scim/v2/Users/{id}   — read one
    POST /scim/v2/Users        — create
    PUT  /scim/v2/Users/{id}   — replace
    PATCH /scim/v2/Users/{id}  — update select fields (deactivate)
    DELETE /scim/v2/Users/{id} — hard delete
    GET  /scim/v2/ServiceProviderConfig
    GET  /scim/v2/Schemas
    GET  /scim/v2/ResourceTypes

Auth: SCIM endpoints require a **separate bearer token** (not user JWT).
Operators set `PRAXIA_SCIM_TOKEN` and configure their IdP to send it.
This token is rate-limited and audit-logged. Rotate via:
    praxia admin scim rotate-token

Compatible with:
    - Okta SCIM 2.0
    - Azure AD / Entra ID SCIM
    - JumpCloud SCIM
    - OneLogin SCIM
    - Custom IdPs implementing the standard
"""
from praxia.scim.server import (
    SCIMUser,
    map_praxia_user_to_scim,
    map_scim_user_to_praxia_kwargs,
    scim_router,
)

__all__ = [
    "SCIMUser",
    "map_praxia_user_to_scim",
    "map_scim_user_to_praxia_kwargs",
    "scim_router",
]
