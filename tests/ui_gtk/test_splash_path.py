# flake8: noqa: E402
"""Tests for the splash-screen path resolver.

The SplashScreen class loads data/splash/splash.svg from disk. The
path resolution has to handle three layouts:

    1. dev:        <repo>/data/splash/splash.svg
    2. pixi:       same as dev (path is computed from __file__)
    3. PyInstaller: <sys._MEIPASS>/data/splash/splash.svg

We exercise the resolver directly so the test doesn't need a real
Gtk display, a splash class instance, or the splash.svg file
present (the resolver returns None when the file is missing, which
is part of the public contract).
"""
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# Skip the whole module on Linux without a display: importing
# rayforge.ui_gtk.splash pulls in gi / Gtk, which fails on bare CI.
# We allow the import path here because splash.py does the gi
# require_version calls but the resolver itself is pure Python.
# If the import explodes, we just skip — the user should run
# these tests on a workstation with GTK available.
try:
    from rayforge.ui_gtk.splash import _resolve_splash_svg
except Exception as exc:  # pragma: no cover - environment-dependent
    pytest.skip(
        f"splash module not importable in this environment: {exc}",
        allow_module_level=True,
    )


def test_resolve_returns_none_when_svg_missing(tmp_path, monkeypatch):
    """When the splash file is absent, the resolver returns None.

    This is the public contract used by SplashScreen.__init__ to
    decide whether to call set_filename on the Gtk.Picture or
    fall back to a black 800x500 box.
    """
    # Point the resolver at a directory tree that does NOT contain
    # the splash file. We patch __file__ indirectly by reloading
    # the module with a fake base path.
    fake_repo = tmp_path / "no_splash_here"
    fake_repo.mkdir()

    # Re-route sys._MEIPASS to a non-existent dir so the bundle
    # path is also rejected. Use monkeypatch so we don't leak state.
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "no_bundle"), raising=False)

    # Re-import the module so it picks up the new __file__-relative
    # path computed from `Path(__file__).resolve().parent.parent.parent`.
    # We don't reload; we directly patch the relevant globals by
    # calling the resolver with __file__ overridden via the package
    # attribute.
    import rayforge.ui_gtk.splash as splash_mod

    original_file = splash_mod.__file__
    try:
        # Simulate the module being located at fake_repo/.../splash.py
        # (i.e. three parents up is the repo root that we just made
        # empty).
        fake_splash_path = fake_repo / "rayforge" / "ui_gtk" / "splash.py"
        fake_splash_path.parent.mkdir(parents=True)
        fake_splash_path.write_text("")  # empty placeholder
        splash_mod.__file__ = str(fake_splash_path)
        # Clear _MEIPASS so the resolver falls back to the file-relative path.
        if hasattr(sys, "_MEIPASS"):
            delattr(sys, "_MEIPASS")

        result = splash_mod._resolve_splash_svg()
        assert result is None, (
            f"Expected None when splash.svg is missing, got {result!r}"
        )
    finally:
        splash_mod.__file__ = original_file


def test_resolve_finds_svg_in_dev_layout(tmp_path, monkeypatch):
    """When the splash file exists in the dev layout, the resolver
    returns the correct Path.
    """
    # Create a dev-style tree:
    #   <tmp>/rayforge/ui_gtk/splash.py    (placeholder)
    #   <tmp>/data/splash/splash.svg       (target)
    fake_repo = tmp_path
    pkg_dir = fake_repo / "rayforge" / "ui_gtk"
    pkg_dir.mkdir(parents=True)
    splash_py = pkg_dir / "splash.py"
    splash_py.write_text("")
    data_svg = fake_repo / "data" / "splash" / "splash.svg"
    data_svg.parent.mkdir(parents=True)
    data_svg.write_text("<svg></svg>")

    # Clear _MEIPASS so the resolver takes the file-relative branch.
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS")

    import rayforge.ui_gtk.splash as splash_mod

    original_file = splash_mod.__file__
    try:
        splash_mod.__file__ = str(splash_py)
        result = splash_mod._resolve_splash_svg()
        assert result is not None, "Expected to find splash.svg in dev layout"
        assert result.name == "splash.svg"
        assert result.parent.name == "splash"
        assert result.parent.parent.name == "data"
    finally:
        splash_mod.__file__ = original_file


def test_resolve_prefers_meipass_over_dev(tmp_path, monkeypatch):
    """When _MEIPASS is set (PyInstaller bundle), the resolver uses
    that path even if a dev-tree copy also exists.
    """
    bundle_root = tmp_path / "bundle"
    bundle_data = bundle_root / "data" / "splash"
    bundle_data.mkdir(parents=True)
    bundle_svg = bundle_data / "splash.svg"
    bundle_svg.write_text("<svg>bundle</svg>")

    # Set up a (separate) dev tree that we do NOT expect to win.
    dev_root = tmp_path / "dev"
    dev_data = dev_root / "data" / "splash"
    dev_data.mkdir(parents=True)
    dev_svg = dev_data / "splash.svg"
    dev_svg.write_text("<svg>dev</svg>")
    dev_splash_py = dev_root / "rayforge" / "ui_gtk" / "splash.py"
    dev_splash_py.parent.mkdir(parents=True)
    dev_splash_py.write_text("")

    import rayforge.ui_gtk.splash as splash_mod

    original_file = splash_mod.__file__
    original_meipass = getattr(sys, "_MEIPASS", None)
    try:
        splash_mod.__file__ = str(dev_splash_py)
        monkeypatch.setattr(sys, "_MEIPASS", str(bundle_root))
        result = splash_mod._resolve_splash_svg()
        assert result is not None
        # The bundle copy should win, not the dev copy.
        assert "bundle" in str(result), (
            f"Expected bundle path, got {result!r}"
        )
    finally:
        splash_mod.__file__ = original_file
        if original_meipass is not None:
            monkeypatch.setattr(sys, "_MEIPASS", original_meipass)
        else:
            if hasattr(sys, "_MEIPASS"):
                delattr(sys, "_MEIPASS")
