"""Generic extension registry with lazy imports + entry-point discovery.

`Registry[T]` is the single mechanism behind every Praxia extension point:
connectors, memory backends, business skills, flows. It supports three
ways to register:

    1. **Direct registration** (in-code):
       reg.register("box", BoxConnector)

    2. **Lazy registration** (defer import until used):
       reg.register("box", lazy("praxia.connectors.box:BoxConnector"))

    3. **Entry points** (third-party plug-ins):
       In your pyproject.toml:
         [project.entry-points."praxia.connectors"]
         my_crm = "my_pkg.my_crm:MyCRMConnector"
       Praxia auto-discovers it when `Registry.discover()` runs.

Looking up by name returns the loaded class, importing it on first access
and caching for subsequent lookups.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class _LazyRef:
    """Internal: deferred import descriptor used by Registry.register().

    Stores `module:Class` reference; resolves on first `.load()` call.
    """

    __slots__ = ("_target", "_loaded")

    def __init__(self, target: str) -> None:
        self._target = target
        self._loaded: type | None = None

    def load(self) -> type:
        if self._loaded is None:
            module_name, _, class_name = self._target.partition(":")
            if not class_name:
                raise ValueError(
                    f"Invalid lazy reference {self._target!r}; expected 'module:ClassName'"
                )
            module = importlib.import_module(module_name)
            self._loaded = getattr(module, class_name)
        return self._loaded

    def __repr__(self) -> str:
        return f"lazy({self._target!r})"


def lazy(target: str) -> _LazyRef:
    """Return a deferred-import handle for use with `Registry.register()`.

    Example:
        reg.register("box", lazy("praxia.connectors.box:BoxConnector"))
    """
    return _LazyRef(target)


class Registry(Generic[T]):
    """A typed plugin registry.

    Args:
        name:                friendly name (used in error messages)
        entry_point_group:   PEP-621 entry-point group, e.g. "praxia.connectors".
                              Set to None to disable third-party discovery.

    Methods:
        register(name, cls)  — direct or lazy registration
        get(name)            — instantiate-by-name; returns the class
        list()               — list registered names (triggers discovery once)
        items()              — iterate (name, class) pairs

    Decorator form:
        @reg.register_decorator("my_name")
        class MyClass: ...
    """

    def __init__(self, name: str, *, entry_point_group: str | None = None) -> None:
        self.name = name
        self.entry_point_group = entry_point_group
        self._entries: dict[str, type[T] | _LazyRef] = {}
        self._discovered = False

    def register(self, name: str, cls_or_ref: type[T] | _LazyRef) -> None:
        """Register a class (eager) or lazy reference (deferred import)."""
        if name in self._entries:
            # Allow override but warn — important for plug-in conflict detection
            import warnings
            warnings.warn(
                f"Registry {self.name!r}: overriding existing entry {name!r}", stacklevel=2
            )
        self._entries[name] = cls_or_ref

    def register_decorator(self, name: str) -> Callable[[type[T]], type[T]]:
        """`@registry.register_decorator("foo")` — decorate a class to register it."""

        def _wrap(cls: type[T]) -> type[T]:
            self.register(name, cls)
            return cls

        return _wrap

    def unregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def get(self, name: str) -> type[T]:
        """Resolve a name to its (loaded) class. Triggers discovery."""
        self._discover()
        if name not in self._entries:
            raise KeyError(
                f"Unknown {self.name} {name!r}. Available: {sorted(self._entries)}"
            )
        entry = self._entries[name]
        if isinstance(entry, _LazyRef):
            cls = entry.load()
            self._entries[name] = cls  # cache the loaded class
            return cls
        return entry

    def list(self) -> list[str]:
        """Return all registered names (sorted, deterministic)."""
        self._discover()
        return sorted(self._entries.keys())

    def items(self) -> list[tuple[str, type[T]]]:
        """Iterate (name, class) — triggers full loading of every lazy entry."""
        self._discover()
        return [(n, self.get(n)) for n in sorted(self._entries.keys())]

    def has(self, name: str) -> bool:
        self._discover()
        return name in self._entries

    def create(self, name: str, *args: Any, **kwargs: Any) -> T:
        """Convenience: get + instantiate."""
        cls = self.get(name)
        return cls(*args, **kwargs)

    # --- Discovery ---------------------------------------------------------

    def _discover(self) -> None:
        """Auto-discover entry-points (idempotent)."""
        if self._discovered or not self.entry_point_group:
            return
        self._discovered = True
        try:
            from importlib.metadata import entry_points  # type: ignore[import-not-found]
        except ImportError:
            return
        try:
            eps = entry_points(group=self.entry_point_group)
        except TypeError:
            # Older Python: entry_points() returns a dict
            eps = entry_points().get(self.entry_point_group, [])
        for ep in eps:
            if ep.name in self._entries:
                continue  # in-code registrations take precedence
            try:
                cls = ep.load()
                self._entries[ep.name] = cls
            except Exception as e:
                import warnings
                warnings.warn(
                    f"Failed to load entry point {ep.name!r} for {self.name}: {e}",
                    stacklevel=2,
                )

    def reset_discovery(self) -> None:
        """Force re-discovery on the next call. Mostly for tests."""
        self._discovered = False
