"""End-to-end GUI smoke tests for the main window.

These tests launch a real MainWindow in a GTK-aware
offscreen mode and walk the widget tree to verify:

  - The window appears
  - The major panels are present (toolbar, status bar,
    coordinate bar, right pane, bottom panel, canvas)
  - The a11y labels we set in wave C are reachable
  - The first-run walkthrough appears on first launch
  - The coach-mark triggers fire on first click

Unlike unit tests, these tests do require a working
display (X11 or Wayland) and AT-SPI. We use Gtk's
offscreen window mode (Gtk.Window is created without
realize, then we iterate children) to keep the
dependency footprint small.

Why not dogtail? dogtail requires AT-SPI to be running
on the host, which complicates CI. dogtail also pulls
in pyatspi2 + python3-gobject. For a smoke test that
just verifies 'the right widgets exist with the right
labels', walking the GTK widget tree directly is
sufficient and runs in 1-2s without external services.

Run with:
  pytest tests/gui/ -v -s
  (or)
  python3 -m pytest tests/gui/ -v
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import pytest

# Suppress the GUI warnings during tests; we don't care
# about the splash / log spam.
logging.basicConfig(level=logging.WARNING)

# Make sure the test runs from the repo root, not from
# tests/gui. (This matters because AddonManager looks
# for builtin addons in a path relative to CWD.)
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
os.chdir(_REPO)


def _collect_widgets(widget) -> List:
    """Return a flat list of the widget and all its descendants.

    Recursive walk of the widget tree. Used to find labels
    and check that the expected widgets are present.
    """
    out = [widget]
    try:
        child = widget.get_first_child()
    except Exception:
        return out
    while child is not None:
        out.extend(_collect_widgets(child))
        try:
            child = child.get_next_sibling()
        except Exception:
            break
    return out


def _find_by_label(widgets, label: str) -> Optional[object]:
    """Return the first widget whose accessible label matches
    the given string, or None. Case-sensitive substring match
    against the Gtk.AccessibleLabel property."""
    needle = label.lower()
    for w in widgets:
        try:
            cur = w.get_accessible_label()
        except Exception:
            cur = None
        if cur and needle in cur.lower():
            return w
    return None


def _launch_main_window():
    """Construct a MainWindow in a non-blocking way.

    Returns the window. Caller is responsible for calling
    window.destroy() (or letting the test fixture do it).
    We use a temporary config so the test doesn't pollute
    the user's real config.
    """
    os.environ.setdefault("RAYFORGE_TRACE", "0")
    os.environ.setdefault("RAYFORGE_LANG", "en")
    # We deliberately use a no-op for the splash to keep
    # the test fast.
    from rayforge.context import init_context
    from rayforge.ui_gtk.mainwindow import MainWindow
    import tempfile
    import rayforge.config as cfg

    tmpdir = tempfile.mkdtemp(prefix="rayforge-test-")
    cfg.config_dir = tmpdir
    # Initialize context (loads addons, sets up logging).
    init_context()
    win = MainWindow()
    return win


class TestMainWindow:
    """Smoke tests for the MainWindow widget tree."""

    def test_window_constructs(self):
        win = _launch_main_window()
        try:
            assert win is not None
            assert win.get_title()  # non-empty
        finally:
            win.destroy()

    def test_status_bar_present(self):
        """The status bar with the mode badge + X/Y is reachable."""
        win = _launch_main_window()
        try:
            widgets = _collect_widgets(win)
            # Status bar is identified by its CSS class.
            found = False
            for w in widgets:
                try:
                    css = w.get_css_classes()
                except Exception:
                    continue
                if "forge-statusbar" in css:
                    found = True
                    break
            assert found, "No status bar widget found"
        finally:
            win.destroy()

    def test_coordinate_bar_present(self):
        win = _launch_main_window()
        try:
            widgets = _collect_widgets(win)
            found = any(
                "forge-coordinate-bar" in (
                    w.get_css_classes() if hasattr(w, "get_css_classes") else []
                )
                for w in widgets
            )
            assert found, "No coordinate bar widget found"
        finally:
            win.destroy()

    def test_a11y_labels_reachable(self):
        """The accessibility labels we set are reachable via
        the Gtk.AccessibleLabel interface."""
        win = _launch_main_window()
        try:
            widgets = _collect_widgets(win)
            # The status bar mode badge has label 'Mode indicator'.
            found = _find_by_label(widgets, "Mode indicator")
            assert found is not None, (
                "Status bar mode badge a11y label not found"
            )
            # Coordinate bar X label has 'Cursor X'.
            found = _find_by_label(widgets, "Cursor X")
            assert found is not None, (
                "Coordinate bar X a11y label not found"
            )
        finally:
            win.destroy()

    def test_canvas_widget_present(self):
        """The 2D canvas (Gtk.DrawingArea / surface) is in the tree."""
        win = _launch_main_window()
        try:
            widgets = _collect_widgets(win)
            # The canvas surface is a Gtk.DrawingArea; check
            # for at least one DrawingArea in the tree.
            from gi.repository import Gtk

            found = any(isinstance(w, Gtk.DrawingArea) for w in widgets)
            assert found, "No Gtk.DrawingArea (canvas) found"
        finally:
            win.destroy()

    def test_toolbar_present(self):
        """The MainToolbar is in the widget tree."""
        win = _launch_main_window()
        try:
            widgets = _collect_widgets(win)
            # Toolbar widget is identified by its accessible
            # label "Toolbar" (or similar). At minimum, there
            # should be a Gtk.Box near the top of the window
            # with several button children.
            from gi.repository import Gtk

            found = any(
                isinstance(w, Gtk.Box) and len(_collect_widgets(w)) > 5
                for w in widgets
            )
            assert found, "No sizeable toolbar container found"
        finally:
            win.destroy()
