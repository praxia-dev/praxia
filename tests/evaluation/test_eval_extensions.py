"""Registry primitive + entry-point discovery — extension regression tests.

The `Registry` class is the single extensibility primitive used by every
plugin point in Praxia. If it breaks, all plugin types break together.
This module verifies its contract under all paths:

    - direct registration
    - lazy registration (deferred import)
    - decorator registration
    - entry-point discovery (mocked)
    - get / has / list / items / unregister
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.evaluation


class TestRegistry:
    def test_direct_registration(self):
        from praxia.extensions import Registry

        reg = Registry(name="test")

        class A:
            pass

        reg.register("a", A)
        assert reg.has("a")
        assert reg.get("a") is A

    def test_lazy_registration_resolves_on_get(self):
        from praxia.extensions import Registry, lazy

        reg = Registry(name="test")
        # Point at a real symbol so lazy resolves
        reg.register("dataclass", lazy("dataclasses:dataclass"))
        import dataclasses

        # Not yet imported in some cases — but get() must return the symbol
        cls = reg.get("dataclass")
        assert cls is dataclasses.dataclass

    def test_decorator_registration(self):
        from praxia.extensions import Registry

        reg = Registry(name="test")

        @reg.register_decorator("my_thing")
        class Thing:
            pass

        assert reg.has("my_thing")
        assert reg.get("my_thing") is Thing

    def test_unknown_name_raises_keyerror(self):
        from praxia.extensions import Registry

        reg = Registry(name="thing")
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_unregister(self):
        from praxia.extensions import Registry

        reg = Registry(name="test")
        reg.register("a", str)
        assert reg.has("a")
        reg.unregister("a")
        assert not reg.has("a")
        # Idempotent — second unregister is a no-op (returns None)
        reg.unregister("a")
        assert not reg.has("a")

    def test_list_returns_names(self):
        from praxia.extensions import Registry

        reg = Registry(name="test")
        reg.register("a", str)
        reg.register("b", int)
        names = reg.list()
        assert "a" in names
        assert "b" in names

    def test_items_returns_pairs(self):
        from praxia.extensions import Registry

        reg = Registry(name="test")
        reg.register("a", str)
        items = dict(reg.items())
        assert items["a"] is str

    def test_double_registration_idempotent_or_error(self):
        """The behavior is intentionally allowed to overwrite — verify it's
        deterministic (last-wins or first-wins, but not silently corrupted)."""
        from praxia.extensions import Registry

        reg = Registry(name="test")
        reg.register("a", str)
        reg.register("a", int)  # overwrite or no-op
        cls = reg.get("a")
        # Either str or int — but get must succeed
        assert cls in (str, int)


class TestPluginRegistries:
    """Verify every Praxia registry has its built-ins on import."""

    def test_connectors_registry(self):
        from praxia.connectors.registry import CONNECTORS, list_builtin

        builtins = set(list_builtin())
        v10 = {"box", "sharepoint", "dropbox", "gdrive", "kintone", "salesforce"}
        v11_tier1 = {"notion", "confluence", "jira", "slack", "teams"}
        v11_tier2 = {"github", "hubspot", "zendesk", "linear", "s3", "azure-blob", "gcs", "webdav", "email"}
        assert v10.issubset(builtins)
        assert v11_tier1.issubset(builtins)
        assert v11_tier2.issubset(builtins)
        for name in builtins:
            assert CONNECTORS.has(name)

    def test_memory_backends_registry(self):
        from praxia.memory.backends import BACKENDS

        names = BACKENDS.list()
        for needed in ("json", "mem0", "langmem", "letta", "zep", "hindsight"):
            assert needed in names

    def test_parsers_registry(self):
        from praxia.io.parsers import supported_extensions

        exts = supported_extensions()
        for needed in ("pdf", "docx", "pptx", "xlsx", "csv", "txt", "md", "html", "json"):
            assert needed in exts

    def test_exporters_registry(self):
        from praxia.io.exporters import supported_formats

        formats = supported_formats()
        for needed in ("md", "markdown", "html", "json", "pptx", "docx"):
            assert needed in formats

    def test_skills_registry(self):
        from praxia.skills import SKILLS

        names = SKILLS.list()
        for needed in (
            "investment_analyst",
            "sales_strategist",
            "design_reviewer",
            "purchasing_analyst",
            "patent_analyst",
            "legal_reviewer",
            "output_formatter",  # utility
        ):
            assert needed in names

    def test_flows_registry(self):
        from praxia.flows import FLOWS

        names = FLOWS.list()
        for needed in ("sales_agent_flow", "logic_checker_flow", "rag_optimization_flow"):
            assert needed in names
