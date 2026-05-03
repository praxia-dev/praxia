"""Role-based access control.

Four built-in roles — most deployments only need these. Custom roles can be
added by extending PERMISSIONS_BY_ROLE.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"        # full control + user management
    OPERATOR = "operator"  # promote skills, freeze blocks, run consolidator
    MEMBER = "member"      # default: run flows, write to own personal memory
    VIEWER = "viewer"      # read-only: search shared memory, list skills


# Permission catalog. Keep names verb-noun (e.g., "promote_skills").
PERMISSIONS_BY_ROLE: dict[Role, set[str]] = {
    Role.ADMIN: {
        # User management (admin only)
        "manage_users",
        "rotate_api_keys",
        "view_audit_log",
        # Operator-level
        "promote_skills",
        "freeze_blocks",
        "run_consolidator",
        "edit_shared_memory",
        # Member-level
        "run_flows",
        "run_skills",
        "write_personal_memory",
        # Viewer-level
        "read_shared_memory",
        "read_personal_memory",
    },
    Role.OPERATOR: {
        "promote_skills",
        "freeze_blocks",
        "run_consolidator",
        "edit_shared_memory",
        "run_flows",
        "run_skills",
        "write_personal_memory",
        "read_shared_memory",
        "read_personal_memory",
    },
    Role.MEMBER: {
        "run_flows",
        "run_skills",
        "write_personal_memory",
        "read_shared_memory",
        "read_personal_memory",
    },
    Role.VIEWER: {
        "read_shared_memory",
        "read_personal_memory",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Return True if the role grants the given permission."""
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    return permission in PERMISSIONS_BY_ROLE[role_enum]
