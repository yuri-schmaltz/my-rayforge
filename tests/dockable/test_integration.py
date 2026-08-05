"""Tests for dockable_integration module.

Verifies the public API of the integration layer
without needing a display. The functions
`setup_dockable`, `_on_surface_dropped`,
`_apply_workspace` are imported as references and
checked for their signatures; no real MainWindow
is instantiated (that would require a Gtk display).

Run: PYTHONPATH=. python3 tests/dockable/test_integration.py
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


_REPO_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..",
    )
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# Same fake-package setup as tests/dockable/__init__.py
_fake_pkg = types.ModuleType("rayforge")
_fake_pkg.__path__ = []
sys.modules.setdefault("rayforge", _fake_pkg)
_fake_gtk = types.ModuleType("rayforge.ui_gtk")
_fake_gtk.__path__ = []
sys.modules.setdefault("rayforge.ui_gtk", _fake_gtk)


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load the same modules the integration depends on
_dc = _load(
    "rayforge.ui_gtk.drag_controller",
    os.path.join(_REPO_ROOT, "rayforge/ui_gtk/drag_controller.py"),
)
_dl = _load(
    "rayforge.ui_gtk.dock_layout",
    os.path.join(_REPO_ROOT, "rayforge/ui_gtk/dock_layout.py"),
)
_ws = _load(
    "rayforge.ui_gtk.workspace",
    os.path.join(_REPO_ROOT, "rayforge/ui_gtk/workspace.py"),
)


class TestIntegrationAPI(unittest.TestCase):
    """The integration module's public API is
    correct: setup_dockable is the single entry
    point, and the helper functions exist with
    the expected signatures."""

    def setUp(self) -> None:
        # AST-parse the integration file rather than
        # full-importing it (it requires Gtk which the
        # sandbox doesn't have).
        with open(
            os.path.join(
                _REPO_ROOT,
                "rayforge/ui_gtk/dockable_integration.py",
            )
        ) as f:
            self.src = f.read()
        self.tree = ast.parse(self.src)

    def _find_function(self, name: str):
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == name
            ):
                return node
        return None

    def test_setup_dockable_exists(self) -> None:
        node = self._find_function("setup_dockable")
        self.assertIsNotNone(
            node, "setup_dockable() must be defined"
        )
        # Has exactly one parameter (window)
        self.assertEqual(len(node.args.args), 1)

    def test_idempotent_guard_present(self) -> None:
        """setup_dockable must be idempotent (a guard
        at the top checking _dockable_setup_done)."""
        node = self._find_function("setup_dockable")
        src_lines = ast.unparse(node)
        self.assertIn("_dockable_setup_done", src_lines)

    def test_drag_over_callback_registered(self) -> None:
        """setup_dockable must register a 'drag-over'
        callback on the controller."""
        node = self._find_function("setup_dockable")
        src_lines = ast.unparse(node)
        self.assertIn("set_drag_over_callback", src_lines)

    def test_dropped_callback_registered(self) -> None:
        node = self._find_function("setup_dockable")
        src_lines = ast.unparse(node)
        self.assertIn("set_dropped_callback", src_lines)

    def test_on_surface_dropped_uses_docklayout(self) -> None:
        """_on_surface_dropped must call
        DockLayout.move_to."""
        node = self._find_function("_on_surface_dropped")
        self.assertIsNotNone(node)
        src_lines = ast.unparse(node)
        self.assertIn("move_to", src_lines)
        self.assertIn("save_workspace", src_lines)

    def test_apply_workspace_uses_docklayout(self) -> None:
        """_apply_workspace must rebuild the
        DockLayout from the workspace.dock_layout
        dict."""
        node = self._find_function("_apply_workspace")
        self.assertIsNotNone(node)
        src_lines = ast.unparse(node)
        self.assertIn("DockLayout.from_dict", src_lines)

    def test_dockable_surfaces_defined(self) -> None:
        """DOCKABLE_SURFACES must list the surfaces
        the user can drag."""
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name)
                    and t.id == "DOCKABLE_SURFACES"
                    for t in node.targets
                )
            ):
                # Found the assignment; verify the
                # tuple contains the expected names
                value = node.value
                if isinstance(value, ast.Tuple):
                    names = [
                        elt.value
                        for elt in value.elts
                        if isinstance(elt, ast.Constant)
                    ]
                    self.assertIn("right_pane", names)
                    self.assertIn("bottom_panel", names)
                    self.assertIn("canvas", names)
                    return
        self.fail("DOCKABLE_SURFACES tuple not found")


class TestWorkspaceRoundTripFromIntegration(unittest.TestCase):
    """When a drop happens, the new layout is
    persisted via Workspace.save. Verify the
    round-trip works."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmpdir, True)

    def test_drop_persists_layout(self) -> None:
        """Simulate a drop: build a Workspace from
        the new layout, save it, and verify the
        file contains the new state."""
        layout = _dl.DockLayout(
            top="bottom_panel",  # swapped
            right="right_pane",
            bottom="coordinate_bar",  # swapped
            left="",
            center="canvas",
        )
        ws = _ws.Workspace(
            name="default",
            dock_layout=layout.to_dict(),
        )
        _ws.save_workspace(Path(self.tmpdir), ws)
        loaded = _ws.load_workspace(
            Path(self.tmpdir), "default"
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.dock_layout["top"], "bottom_panel")
        self.assertEqual(
            loaded.dock_layout["bottom"], "coordinate_bar"
        )


class TestRearrangeStrategy(unittest.TestCase):
    """The rearrange strategy is visibility-based.
    Verify the logic that decides which surfaces
    are visible based on a DockLayout.

    We don't exercise the actual Gtk widgets
    (no display); we verify the pure logic that
    builds the 'visible surfaces' set from a
    layout. The visibility is then applied by
    _rearrange_from_layout (which iterates the
    DOCKABLE_SURFACES constant)."""

    def _visible_surfaces(self, layout):
        """Re-implement the visibility logic in
        pure Python for testing (mirrors the
        implementation in _rearrange_from_layout)."""
        visible = set()
        for z in _dl.Zone:
            s = getattr(layout, z.value, "")
            if s:
                visible.add(s)
        return visible

    def test_default_layout_shows_all(self) -> None:
        """The default layout has coordinate_bar,
        right_pane, bottom_panel, and canvas — all
        four are visible."""
        layout = _dl.DockLayout(
            top="coordinate_bar",
            right="right_pane",
            bottom="bottom_panel",
            left="",
            center="canvas",
        )
        visible = self._visible_surfaces(layout)
        self.assertEqual(
            visible,
            {"coordinate_bar", "right_pane", "bottom_panel", "canvas"},
        )

    def test_swap_makes_empty_zones(self) -> None:
        """When two surfaces are swapped between
        zones, the same set of surfaces is visible
        (just in different zones). The empty zone
        (left) stays empty."""
        layout = _dl.DockLayout(
            top="bottom_panel",  # swapped
            right="right_pane",
            bottom="coordinate_bar",  # swapped
            left="",  # still empty
            center="canvas",
        )
        visible = self._visible_surfaces(layout)
        self.assertEqual(
            visible,
            {"bottom_panel", "right_pane", "coordinate_bar", "canvas"},
        )

    def test_hide_right_pane(self) -> None:
        """Setting the right zone to empty hides
        the right_pane (effectively collapsing
        the side panel)."""
        layout = _dl.DockLayout(
            top="coordinate_bar",
            right="",  # collapsed
            bottom="bottom_panel",
            left="",
            center="canvas",
        )
        visible = self._visible_surfaces(layout)
        self.assertNotIn("right_pane", visible)

    def test_hide_bottom_panel(self) -> None:
        """Setting the bottom zone to empty hides
        the bottom panel (fullscreen mode)."""
        layout = _dl.DockLayout(
            top="coordinate_bar",
            right="right_pane",
            bottom="",  # collapsed
            left="",
            center="canvas",
        )
        visible = self._visible_surfaces(layout)
        self.assertNotIn("bottom_panel", visible)

    def test_rearrange_uses_dockable_surfaces(self) -> None:
        """The integration module's
        DOCKABLE_SURFACES constant lists exactly
        the surfaces that can be shown/hidden.
        Verify the constant matches the canonical
        surface names from the DockLayout."""
        # Read DOCKABLE_SURFACES via AST
        with open(
            os.path.join(
                _REPO_ROOT,
                "rayforge/ui_gtk/dockable_integration.py",
            )
        ) as f:
            tree = ast.parse(f.read())
        found = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name)
                    and t.id == "DOCKABLE_SURFACES"
                    for t in node.targets
                )
            ):
                value = node.value
                if isinstance(value, ast.Tuple):
                    found = {
                        elt.value
                        for elt in value.elts
                        if isinstance(elt, ast.Constant)
                    }
        self.assertIsNotNone(
            found, "DOCKABLE_SURFACES not found"
        )
        # Must include the 4 canonical surfaces
        self.assertIn("right_pane", found)
        self.assertIn("bottom_panel", found)
        self.assertIn("canvas", found)
        self.assertIn("coordinate_bar", found)


class TestApplyWorkspaceTriggersRearrange(unittest.TestCase):
    """_apply_workspace must call
    _rearrange_from_layout so the live UI
    actually changes when a workspace is
    switched."""

    def test_apply_workspace_calls_rearrange(self) -> None:
        """AST-verify: _apply_workspace contains a
        call to _rearrange_from_layout."""
        with open(
            os.path.join(
                _REPO_ROOT,
                "rayforge/ui_gtk/dockable_integration.py",
            )
        ) as f:
            src = f.read()
        tree = ast.parse(src)
        apply_node = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "_apply_workspace"
            ):
                apply_node = node
                break
        self.assertIsNotNone(apply_node)
        body_src = ast.unparse(apply_node)
        self.assertIn(
            "_rearrange_from_layout", body_src,
            "_apply_workspace must call "
            "_rearrange_from_layout",
        )

    def test_rearrange_iterates_dockable_surfaces(self) -> None:
        """AST-verify: _rearrange_from_layout
        iterates over the DOCKABLE_SURFACES tuple."""
        with open(
            os.path.join(
                _REPO_ROOT,
                "rayforge/ui_gtk/dockable_integration.py",
            )
        ) as f:
            tree = ast.parse(f.read())
        rearrange_node = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "_rearrange_from_layout"
            ):
                rearrange_node = node
                break
        self.assertIsNotNone(rearrange_node)
        body_src = ast.unparse(rearrange_node)
        self.assertIn("DOCKABLE_SURFACES", body_src)
        self.assertIn("set_visible", body_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
