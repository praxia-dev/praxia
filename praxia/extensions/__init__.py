"""Praxia extension system — unified plugin registry.

All four extension points (connectors, memory backends, business skills,
flows) share one mechanism so adding a new plugin is a single pattern:

    1. Subclass the appropriate base class.
    2. Either:
       a. Add a decorator: `@register_connector("box")`
       b. Or declare an entry-point in pyproject.toml:
          [project.entry-points."praxia.connectors"]
          box = "my_pkg.box:BoxConnector"

The core framework discovers the new plugin automatically — no edit to
`praxia/connectors/registry.py`, `__init__.py`, or any other core file.

This module exports the generic primitive `Registry[T]`. The four concrete
registries live with their domains:

    praxia.connectors.registry        — connector registry
    praxia.memory.backends            — backend registry
    praxia.skills                     — skill registry
    praxia.flows                      — flow registry
"""
from praxia.extensions.registry import Registry, lazy

__all__ = ["Registry", "lazy"]
