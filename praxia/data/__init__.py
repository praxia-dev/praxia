"""User-level data scope management.

A `DataScope` is a named bundle of files that a user can target at
execution time (Flow / Skill / Agent). Two kinds are supported:

  - kind="local"     — files uploaded through the UI; live on disk
                        under .praxia/data/<user_id>/<scope_id>/
  - kind="connector" — a specific path inside an external connector
                        (Box, SharePoint, Notion, ...). Registration
                        is metadata only; the actual pull happens
                        at execution time.

Public API:

    from praxia.data.scopes import DataScope, ScopeRegistry
"""
from praxia.data.scopes import DataScope, ScopeRegistry

__all__ = ["DataScope", "ScopeRegistry"]
