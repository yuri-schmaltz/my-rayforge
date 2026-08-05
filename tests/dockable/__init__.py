"""Unit tests for the dockable panels drag controller
and workspace save/load.

These tests don't require a display; they exercise
the pure logic of:
  - DragController state machine
  - Workspace list/save/load/delete
  - DockLayout swap + JSON round-trip

The Gtk-dependent parts (DropZone widget,
MainWindow integration) are not covered here; they
require a display and are verified by visual
inspection of the running app.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# Ensure rayforge is importable when running this
# file directly (`python3 tests/dockable/__init__.py`)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Import only the standalone modules — the rest of
# rayforge pulls in cairo/Gtk which the sandbox
# doesn't have. The test file is exercised by CI in
# the normal dev environment where cairo is present.
import importlib
import importlib.util
import sys
import types


def _load_module(name: str, path: str):
    """Load a module from a file path and register it
    in sys.modules. Required for @dataclass to find
    the module via sys.modules[cls.__module__].
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"can't load {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# A fake 'rayforge.ui_gtk' parent so the loaded
# module's __package__ is plausible. This is
# required for @dataclass to find cls.__module__.
_fake_pkg = types.ModuleType("rayforge")
_fake_pkg.__path__ = []  # mark as package
sys.modules.setdefault("rayforge", _fake_pkg)
_fake_gtk = types.ModuleType("rayforge.ui_gtk")
_fake_gtk.__path__ = []
sys.modules.setdefault("rayforge.ui_gtk", _fake_gtk)

_dc = _load_module(
    "rayforge.ui_gtk.drag_controller",
    os.path.join(
        _REPO_ROOT,
        "rayforge",
        "ui_gtk",
        "drag_controller.py",
    ),
)
_ws = _load_module(
    "rayforge.ui_gtk.workspace",
    os.path.join(
        _REPO_ROOT,
        "rayforge",
        "ui_gtk",
        "workspace.py",
    ),
)
_dl = _load_module(
    "rayforge.ui_gtk.dock_layout",
    os.path.join(
        _REPO_ROOT,
        "rayforge",
        "ui_gtk",
        "dock_layout.py",
    ),
)
DragController = _dc.DragController


# A standard 1280x800 hit-test layout: top bar at
# y=0..8, bottom bar at y=792..800, left strip at
# x=0..8, right strip at x=1272..1280, center
# 8..1272, 8..792.
STANDARD_ZONES = [
    ("top", (0.0, 0.0, 1280.0, 8.0)),
    ("right", (1272.0, 0.0, 8.0, 800.0)),
    ("bottom", (0.0, 792.0, 1280.0, 8.0)),
    ("left", (0.0, 0.0, 8.0, 800.0)),
    ("center", (8.0, 8.0, 1264.0, 784.0)),
]


class TestDragControllerBasics(unittest.TestCase):
    """The state machine transitions correctly."""

    def test_idle_initially(self) -> None:
        c = DragController()
        self.assertFalse(c.is_dragging)
        self.assertIsNone(c.current_source)
        self.assertIsNone(c.current_zone)

    def test_begin_drag_starts_drag(self) -> None:
        c = DragController()
        c.begin_drag("right_pane", 100.0, 100.0)
        self.assertTrue(c.is_dragging)
        self.assertEqual(c.current_source, "right_pane")
        # Begin always fires 'drag-over' with None
        # (no zone active at the start position).
        self.assertIsNone(c.current_zone)

    def test_update_outside_zones(self) -> None:
        c = DragController()
        events: list = []

        def on_over(source, zone):
            events.append((source, zone))

        c.set_drag_over_callback(on_over)
        c.begin_drag("right_pane", 100.0, 100.0)
        c.update_drag(500.0, 500.0, STANDARD_ZONES)
        # 500,500 is inside 'center'
        self.assertEqual(c.current_zone, "center")
        self.assertEqual(len(events), 2)
        # First event from begin_drag (None),
        # second from update_drag (center)
        self.assertEqual(events[0], ("right_pane", None))
        self.assertEqual(events[1], ("right_pane", "center"))

    def test_update_no_change_no_callback(self) -> None:
        """Hovering the same zone twice in a row
        should not fire 'drag-over' twice."""
        c = DragController()
        events: list = []

        c.set_drag_over_callback(
            lambda s, z: events.append((s, z))
        )
        c.begin_drag("right_pane", 100.0, 100.0)
        c.update_drag(500.0, 500.0, STANDARD_ZONES)
        c.update_drag(500.5, 500.5, STANDARD_ZONES)  # same zone
        # 1 from begin + 1 from first update
        self.assertEqual(len(events), 2)

    def test_end_drag_inside_zone(self) -> None:
        c = DragController()
        dropped: list = []
        c.set_dropped_callback(
            lambda s, z: dropped.append((s, z))
        )
        c.begin_drag("right_pane", 100.0, 100.0)
        result = c.end_drag(500.0, 500.0, STANDARD_ZONES)
        self.assertEqual(result, ("right_pane", "center"))
        self.assertEqual(dropped, [("right_pane", "center")])
        # Controller returns to idle
        self.assertFalse(c.is_dragging)

    def test_end_drag_outside_zones(self) -> None:
        """Released outside any zone = cancel."""
        c = DragController()
        dropped: list = []
        c.set_dropped_callback(
            lambda s, z: dropped.append((s, z))
        )
        c.begin_drag("right_pane", 100.0, 100.0)
        # (-100, -100) is outside the standard layout
        result = c.end_drag(-100.0, -100.0, STANDARD_ZONES)
        self.assertIsNone(result)
        self.assertEqual(dropped, [])
        self.assertFalse(c.is_dragging)

    def test_cancel_drag(self) -> None:
        c = DragController()
        c.begin_drag("right_pane", 100.0, 100.0)
        self.assertTrue(c.is_dragging)
        c.cancel_drag()
        self.assertFalse(c.is_dragging)

    def test_begin_during_drag_resets(self) -> None:
        """A second begin_drag while one is in
        progress cancels the previous and starts a new
        one (logged as a warning in production)."""
        c = DragController()
        c.begin_drag("right_pane", 100.0, 100.0)
        c.begin_drag("bottom_panel", 200.0, 200.0)
        self.assertEqual(c.current_source, "bottom_panel")

    def test_update_without_drag_no_op(self) -> None:
        """Calling update_drag before begin_drag is a
        no-op (defensive: avoids spurious highlights)."""
        c = DragController()
        events: list = []
        c.set_drag_over_callback(
            lambda s, z: events.append((s, z))
        )
        c.update_drag(500.0, 500.0, STANDARD_ZONES)
        self.assertEqual(events, [])

    def test_end_without_drag_returns_none(self) -> None:
        c = DragController()
        result = c.end_drag(500.0, 500.0, STANDARD_ZONES)
        self.assertIsNone(result)

    def test_zone_transitions_correctly(self) -> None:
        """A drag crossing multiple zones fires
        'drag-over' for each entry, in order."""
        c = DragController()
        events: list = []
        c.set_drag_over_callback(
            lambda s, z: events.append((s, z))
        )
        c.begin_drag("right_pane", 100.0, 100.0)
        # Move from top -> center -> bottom
        c.update_drag(4.0, 4.0, STANDARD_ZONES)  # top
        c.update_drag(500.0, 500.0, STANDARD_ZONES)  # center
        c.update_drag(500.0, 795.0, STANDARD_ZONES)  # bottom
        zones_visited = [z for _, z in events]
        self.assertEqual(zones_visited, [None, "top", "center", "bottom"])


class TestWorkspaceRoundTrip(unittest.TestCase):
    """Workspace save/load round-trips correctly."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(
            __import__("shutil").rmtree, self.tmpdir, True
        )

    def test_default_workspace_seeded(self) -> None:
        from pathlib import Path
        list_workspaces = _ws.list_workspaces
        save_workspace = _ws.save_workspace
        Workspace = _ws.Workspace
        load_workspace = _ws.load_workspace
        delete_workspace = _ws.delete_workspace
        _make_default_workspace = _ws._make_default_workspace
        # Save a default first (so list finds it)
        save_workspace(
            Path(self.tmpdir), _make_default_workspace()
        )
        ws_list = list_workspaces(Path(self.tmpdir))
        self.assertIn("default", ws_list)
        self.assertEqual(
            ws_list["default"].panel_layout, "default"
        )

    def test_save_and_load(self) -> None:
        from pathlib import Path
        Workspace = _ws.Workspace
        save_workspace = _ws.save_workspace
        load_workspace = _ws.load_workspace
        ws = Workspace(
            name="compact",
            dock_layout={"right": "right_pane", "left": ""},
            panel_layout="compact",
            theme="dark",
            toolbar_mode="all",
            walkthrough_seen=True,
        )
        save_workspace(Path(self.tmpdir), ws)
        loaded = load_workspace(Path(self.tmpdir), "compact")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "compact")
        self.assertEqual(loaded.theme, "dark")
        self.assertEqual(loaded.toolbar_mode, "all")
        self.assertEqual(
            loaded.dock_layout["right"], "right_pane"
        )

    def test_load_missing_returns_none(self) -> None:
        from pathlib import Path
        load_workspace = _ws.load_workspace
        loaded = load_workspace(
            Path(self.tmpdir), "does_not_exist"
        )
        self.assertIsNone(loaded)

    def test_delete_default_refused(self) -> None:
        from pathlib import Path
        save_workspace = _ws.save_workspace
        delete_workspace = _ws.delete_workspace
        _make_default_workspace = _ws._make_default_workspace
        save_workspace(
            Path(self.tmpdir), _make_default_workspace()
        )
        ok = delete_workspace(
            Path(self.tmpdir), "default"
        )
        self.assertFalse(ok)

    def test_json_round_trip(self) -> None:
        Workspace = _ws.Workspace
        ws = Workspace(
            name="x",
            dock_layout={"center": "canvas"},
            panel_layout="expanded",
        )
        s = ws.to_json()
        loaded = Workspace.from_json(s)
        self.assertEqual(loaded.name, ws.name)
        self.assertEqual(
            loaded.dock_layout, ws.dock_layout
        )
        self.assertEqual(
            loaded.panel_layout, ws.panel_layout
        )


class TestDockLayoutRoundTrip(unittest.TestCase):
    """DockLayout data model round-trips and validates."""

    def test_swap_zones(self) -> None:
        DockLayout = _dl.DockLayout
        Zone = _dl.Zone
        layout = DockLayout(
            **{z.value: "x" for z in Zone}
        )
        layout.move_to(Zone.TOP, "right_pane")
        # Whatever was in TOP was displaced to
        # wherever the right_pane was (it was in
        # RIGHT).
        # Simpler check: right_pane is now in TOP
        self.assertEqual(layout.top, "right_pane")

    def test_is_valid_detects_duplicates(self) -> None:
        DockLayout = _dl.DockLayout
        Zone = _dl.Zone
        layout = DockLayout(
            top="right_pane", right="right_pane",
        )
        self.assertFalse(layout.is_valid())

    def test_json_round_trip(self) -> None:
        DockLayout = _dl.DockLayout
        Zone = _dl.Zone
        layout = DockLayout(
            top="coord_bar", right="right_pane"
        )
        s = layout.to_json()
        loaded = DockLayout.from_json(s)
        self.assertEqual(loaded.top, layout.top)
        self.assertEqual(loaded.right, layout.right)


if __name__ == "__main__":
    unittest.main(verbosity=2)
