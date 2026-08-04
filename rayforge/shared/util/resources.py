"""Bundle-aware path resolution for ship-along resources.

When the app is run from a PyInstaller bundle, the install
location is unpacked into a temporary directory pointed at by
``sys._MEIPASS``. In dev or pixi-run environments, the location
is the on-disk checkout, and resources are found relative to
``__file__``.

Every helper in this module:

- Tries ``sys._MEIPASS`` first (handles the bundle case).
- Falls back to a path computed from ``__file__`` (handles dev).
- Returns ``None`` if the candidate doesn't exist on disk, so
  callers can degrade gracefully (e.g. show a fallback box
  instead of crashing).

This pattern was duplicated across at least three modules
(splash, mainwindow, app startup) before being extracted.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def resource_path(
    relative: str, *, anchor_file: Optional[str] = None
) -> Optional[Path]:
    """Locate a resource file by path relative to the package root.

    Args:
        relative: Path relative to the app root, e.g.
            ``"rayforge/resources/styles/forge.css"`` or
            ``"data/splash/splash.svg"``.
        anchor_file: The ``__file__`` of the caller. Required when
            the caller is in a sub-package and the relative path
            is to a sibling resource. If ``None``, the relative
            path is resolved against ``Path.cwd()`` for the dev
            fallback, which only works for the most common case
            (running the app from the repo root).

    Returns:
        The resolved Path if the file exists, ``None`` otherwise.
        Callers should treat ``None`` as "fall back to default
        behavior" rather than as an error.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        candidates.append(Path(meipass) / relative)
    if anchor_file is not None:
        # anchor_file is something like
        # /repo/rayforge/ui_gtk/splash.py — go up to repo root.
        candidates.append(
            Path(anchor_file).resolve().parent.parent.parent / relative
        )
    else:
        candidates.append(Path(relative))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
