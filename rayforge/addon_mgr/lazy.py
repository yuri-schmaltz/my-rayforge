"""Lazy-loading module proxy for addons.

The AddonManager currently loads every addon's frontend
module eagerly at startup via `spec.loader.exec_module`.
For 5+ addons this can add 100-500ms to cold start, even
when the user never opens the menu that uses those hooks.

This module provides `LazyModule` — a transparent proxy
that delays the actual `exec_module` call until the
first attribute is accessed. The proxy is registered
with the pluggy plugin manager in place of the real
module, so pluggy sees a module-shaped object. When
pluggy calls `getattr(proxy, "rayforge_init")` to look
up a hookimpl, the proxy loads the real module and
forwards the attribute access.

The trade-off:

  - Pro: cold start drops by N * 50ms where N is the
    number of addons that have heavy imports (PyOpenGL,
    pyvips, vtracer, etc.)
  - Pro: per-addon failures are still caught at first
    use, not at startup (the existing error handling
    in AddonManager keeps working)
  - Con: a 50-200ms hitch on the FIRST action that
    triggers a lazy-loaded addon (vs 0ms if it was
    eager). For most apps this is invisible (the user
    is still looking at the splash or a previous
    screen). For latency-sensitive paths it could be
    felt.
  - Con: the proxy is per-module, not per-hook. If the
    user opens a menu that lists all 10 addon
    commands, the menu construction triggers a load of
    all 10 modules.

Disabled by default. Enable via `config.addon_lazy_load`
(default False) or `RAYFORGE_LAZY_ADDONS=1` env var. The
default keeps the existing behavior so this is a pure
opt-in optimization; turning it on and finding a bug is
a 1-line revert.

Why a proxy and not `importlib.util.LazyLoader`? Python
ships `LazyLoader` but it only delays the module's
`__dict__` population, not its `exec_module`. For our
purpose (defer the actual file IO + import side effects)
we need a custom proxy that wraps `exec_module` itself.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LazyModule:
    """A module-shaped proxy that loads on first attribute access.

    Usage:

        proxy = LazyModule(
            module_name="rayforge_addons.laser_essentials.frontend",
            module_path=Path("/path/to/frontend.py"),
        )
        # Register with pluggy
        plugin_mgr.register(proxy)
        # First call to .rayforge_init triggers the load
        proxy.rayforge_init()  # ~50-200ms hit, only once

    Thread-safe: the first concurrent access wins, others
    wait on the lock and see the loaded module.
    """

    def __init__(self, module_name: str, module_path: Any) -> None:
        self.__name__ = module_name
        self.__file__ = str(module_path)
        self.__path__ = []  # not a package
        self.__loader__ = None
        self.__package__ = module_name.rsplit(".", 1)[0]
        self._module_name = module_name
        self._module_path = module_path
        self._real_module: Optional[Any] = None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> Any:
        """Load the real module if not already loaded. Idempotent."""
        if self._real_module is not None:
            return self._real_module
        with self._lock:
            # Double-checked: another thread may have loaded it
            if self._real_module is not None:
                return self._real_module
            logger.debug(
                "LazyModule: loading %s from %s",
                self._module_name,
                self._module_path,
            )
            spec = importlib.util.spec_from_file_location(
                self._module_name, self._module_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    f"Could not create spec for {self._module_name}"
                )
            module = importlib.util.module_from_spec(spec)
            # Insert into sys.modules so relative imports
            # inside the addon (e.g. `from . import x`)
            # resolve correctly.
            sys.modules[self._module_name] = module
            spec.loader.exec_module(module)
            self._real_module = module
            return module

    def __getattr__(self, name: str) -> Any:
        # Don't intercept dunder attributes that pluggy looks
        # for before loading — they should be available
        # without triggering the load.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        module = self._ensure_loaded()
        return getattr(module, name)

    def __dir__(self) -> list:
        # Make dir() useful for debugging.
        if self._real_module is None:
            return list(self.__dict__.keys()) + [
                "_ensure_loaded",
                "_real_module",
                "_module_name",
                "_module_path",
            ]
        return dir(self._real_module)

    def __repr__(self) -> str:
        state = "loaded" if self._real_module else "pending"
        return f"<LazyModule {self._module_name!r} ({state})>"

    def is_loaded(self) -> bool:
        """True if the real module has been loaded."""
        return self._real_module is not None
