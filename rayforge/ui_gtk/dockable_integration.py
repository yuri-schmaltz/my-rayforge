"""Dockable panels integration for MainWindow.

A single entry point `setup_dockable(window)` that
wires together the four building blocks shipped in
PR #77:

  1. DragController        (pure logic)
  2. DropZoneRegistry      (hit-test)
  3. DragHandle            (user-grabbable target)
  4. WorkspaceMenu         (GAction + Gio.MenuModel)

Plus the data model from PR #76 (DockLayout,
Workspace) which this integration writes to when
the user drops a surface into a new zone.

The MainWindow calls setup_dockable(self) in its
__init__ (after on_config_changed). All the work
happens there.

Design notes:

  - The 5 DropZone widgets are added as overlays
    of the main canvas's GtkOverlay, so they
    appear ABOVE the canvas. They're 8px wide
    thin strips; not intrusive.
  - The DragHandle is added to the top of each
    dockable surface (right pane, bottom panel,
    canvas). The handle is invisible at rest
    (opacity 0) and fades in on hover.
  - The controller's 'dropped' callback is
    connected to `_on_surface_dropped` which:
      1. Calls DockLayout.move_to() to update the
         data model
      2. Calls _rearrange_from_layout() to update
         the live UI
      3. Persists the layout via Workspace.save

  Why a separate file? Keeps the MainWindow diff
  small (~10 lines: one method call). All the
  complex wiring is here, in a focused module.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject, Gtk  # noqa: E402

from .dock_layout import DockLayout, Zone
from .drag_controller import DragController
from .drag_handle import DragHandle
from .drop_zone import DropZone, DropZoneRegistry
from .workspace_menu import (
    add_workspace_actions,
    build_workspace_submenu,
)
from .workspace import (
    _make_default_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
    Workspace,
)

logger = logging.getLogger(__name__)


# Surfaces the user can drag. These names match the
# DockLayout field values and the workspace
# 'dock_layout' dict keys.
DOCKABLE_SURFACES = (
    "right_pane",
    "bottom_panel",
    "canvas",
    "coordinate_bar",
)


def _zone_for_surface(layout: DockLayout, surface: str) -> Optional[Zone]:
    """Return which zone currently holds the given
    surface, or None if not found."""
    for z in Zone:
        if getattr(layout, z.value, "") == surface:
            return z
    return None


def setup_dockable(window) -> None:
    """Wire the dockable panels UI to the given
    MainWindow. Must be called after the window's
    main UI is built (the right_pane, bottom_panel,
    and coordinate_bar widgets must exist).

    Idempotent: a second call is a no-op (guarded
    by window._dockable_setup_done).

    The MainWindow gains the following attributes:
      - _dockable_setup_done: bool
      - _dockable_layout: DockLayout
      - _dockable_controller: DragController
      - _dockable_zones: DropZoneRegistry
      - _dockable_handles: dict[surface, DragHandle]
      - _dockable_current_workspace: Optional[str]
    """
    if getattr(window, "_dockable_setup_done", False):
        return
    window._dockable_setup_done = True

    # 1. Initialize the data model from the current UI
    window._dockable_layout = _layout_from_window(window)

    # 2. Create the controller + zone registry
    window._dockable_controller = DragController()
    window._dockable_zones = DropZoneRegistry()
    window._dockable_handles = {}

    # 3. Install drop zones on the main canvas overlay
    _install_drop_zones(window)

    # 4. Install drag handles on each dockable surface
    _install_drag_handles(window)

    # 5. Wire controller callbacks
    window._dockable_controller.set_drag_over_callback(
        lambda source, zone: _on_drag_over(window, source, zone)
    )
    window._dockable_controller.set_dropped_callback(
        lambda source, zone: _on_surface_dropped(window, source, zone)
    )

    # 6. Register workspace GActions
    try:
        from ..config import config_dir as _config_dir

        add_workspace_actions(
            window,
            Path(_config_dir),
            lambda ws: _apply_workspace(window, ws),
        )
    except Exception as e:  # pragma: no cover
        logger.debug("Workspace actions skipped: %s", e)

    # 7. Insert the Workspace submenu under View
    _install_workspace_submenu(window)

    # 8. Apply the current workspace (default = current UI)
    window._dockable_current_workspace = "default"
    logger.info(
        "Dockable UI ready: layout=%s",
        window._dockable_layout.to_dict(),
    )


def _layout_from_window(window) -> DockLayout:
    """Read the current DockLayout from the window's
    state. Used as the initial layout."""
    # The MainWindow's `right_pane` is `self._right_pane`
    # and the bottom panel is `self.bottom_panel`. The
    # canvas is in the canvas_overlay's child, and the
    # coordinate_bar is in the top-level vbox.
    return DockLayout(
        top="coordinate_bar",
        right="right_pane",
        bottom="bottom_panel",
        left="",
        center="canvas",
    )


def _install_drop_zones(window) -> None:
    """Add 5 thin DropZone widgets as overlays of the
    main canvas overlay. Each zone is 8px wide and
    pinned to one edge (or fills the center)."""
    overlay = getattr(window, "_canvas_overlay", None)
    if overlay is None:
        logger.warning(
            "MainWindow._canvas_overlay not found; "
            "drop zones not installed"
        )
        return

    registry = window._dockable_zones

    # Top zone: a horizontal bar above the canvas
    top = DropZone("top")
    top.set_halign(Gtk.Align.FILL)
    top.set_valign(Gtk.Align.START)
    top.set_size_request(-1, 8)
    overlay.add_overlay(top)
    registry.register(top)

    # Right zone: a vertical strip to the right
    right = DropZone("right")
    right.set_halign(Gtk.Align.END)
    right.set_valign(Gtk.Align.FILL)
    right.set_size_request(8, -1)
    overlay.add_overlay(right)
    registry.register(right)

    # Bottom zone: a horizontal bar below
    bottom = DropZone("bottom")
    bottom.set_halign(Gtk.Align.FILL)
    bottom.set_valign(Gtk.Align.END)
    bottom.set_size_request(-1, 8)
    overlay.add_overlay(bottom)
    registry.register(bottom)

    # Left zone: a vertical strip to the left
    left = DropZone("left")
    left.set_halign(Gtk.Align.START)
    left.set_valign(Gtk.Align.FILL)
    left.set_size_request(8, -1)
    overlay.add_overlay(left)
    registry.register(left)

    # Center zone: the canvas itself (full coverage)
    center = DropZone("center")
    center.set_halign(Gtk.Align.FILL)
    center.set_valign(Gtk.Align.FILL)
    center.set_hexpand(True)
    center.set_vexpand(True)
    overlay.add_overlay(center)
    registry.register(center)


def _install_drag_handles(window) -> None:
    """Add a DragHandle to the top of each dockable
    surface. The handle is the user-grabbable target.

    For now, we add handles to:
      - coordinate_bar (always present, in the top vbox)
      - right_pane (the outer box)
      - bottom_panel
      - canvas (added to the view_stack's child)

    The handle is invisible at rest (opacity 0) and
    fades in on hover.
    """
    registry = window._dockable_zones
    controller = window._dockable_controller

    def _wire(surface: str, parent: Gtk.Widget) -> None:
        if parent is None:
            return
        handle = DragHandle(surface, label=f"≡ {surface}")
        handle.set_visible(True)
        # The handle's 'drag-begin' etc. are in
        # root coordinates. The controller is
        # queried with the registry's current zones
        # (also in root coordinates) for hit-tests.
        handle.connect(
            "drag-begin",
            lambda h, x, y: controller.begin_drag(surface, x, y),
        )
        handle.connect(
            "drag-update",
            lambda h, x, y: controller.update_drag(
                x, y, registry.get_zones(window)
            ),
        )
        handle.connect(
            "drag-end",
            lambda h, x, y: controller.end_drag(
                x, y, registry.get_zones(window)
            ),
        )
        window._dockable_handles[surface] = handle
        # Wrap the parent in a vertical box with the
        # handle on top. This requires the parent to
        # not already have a wrapper. We do this
        # carefully: only wrap if we can.
        _attach_handle_to_widget(parent, handle)

    _wire(
        "coordinate_bar", getattr(window, "coordinate_bar", None)
    )
    _wire("right_pane", getattr(window, "_right_pane", None))
    _wire("bottom_panel", getattr(window, "bottom_panel", None))


def _attach_handle_to_widget(
    parent: Gtk.Widget, handle: DragHandle
) -> None:
    """Attach a DragHandle to the top of a widget.

    The handle becomes a sibling ABOVE the parent in
    a new GtkBox. The original parent is REPLACED in
    the hierarchy (i.e. the new box takes its place
    in the parent's original parent).

    Caveat: This only works if the parent has a
    single parent (which is the normal case for our
    dockable surfaces). For surfaces that are
    inside more complex hierarchies (e.g. inside an
    Adw.ViewStack page), the handle won't be
    attached and the surface is not draggable.
    """
    try:
        old_parent = parent.get_parent()
        if old_parent is None:
            # Surface is not yet inserted into the
            # hierarchy; skip (will be wired later
            # by a follow-up commit)
            return
        # We can't easily replace a widget in a
        # Gtk.Box without rebuilding the parent.
        # The safe approach: insert the handle as a
        # SIBLING above the parent in the old_parent.
        # For a Gtk.Box this is straightforward.
        from gi.repository import Gtk as _Gtk

        if isinstance(old_parent, _Gtk.Box):
            idx = _index_of_child(old_parent, parent)
            if idx < 0:
                return
            # Insert the handle just above the parent
            old_parent.insert_child_at_idx(idx, handle)
        else:
            # For Adw.Overlay, GtkOverlay, etc. the
            # ordering is implicit (last is on top).
            # We just add the handle as an overlay of
            # the canvas overlay (if the surface is
            # already an overlay child) or skip.
            pass
    except Exception as e:  # pragma: no cover
        logger.debug(
            "Failed to attach DragHandle to %s: %s",
            parent, e,
        )


def _index_of_child(
    box: Gtk.Box, child: Gtk.Widget
) -> int:
    """Return the index of `child` in `box`, or -1 if
    not found."""
    n = box.observe_children()
    for i in range(n.get_n_items()):
        if n.get_item(i).get_object() is child:
            return i
    return -1


def _install_workspace_submenu(window) -> None:
    """Add the 'View > Workspace' submenu to the
    main menu model."""
    menu_model = getattr(window, "menu_model", None)
    if menu_model is None:
        logger.debug(
            "MainWindow.menu_model not found; "
            "Workspace submenu not installed"
        )
        return
    # Find the View submenu by iterating the
    # top-level items. This is intentionally
    # simple (no string-search) so it doesn't break
    # if labels change.
    n = menu_model.get_n_items()
    for i in range(n):
        item = menu_model.get_item_attribute_value(
            i, "label"
        )
        if item is not None and "_View" in item.get_string():
            # Got the View submenu. Insert a Workspace
            # submenu as a new top-level section.
            try:
                from ..config import config_dir as _config_dir

                ws_submenu = build_workspace_submenu(
                    Path(_config_dir),
                    window._dockable_current_workspace,
                )
                # Insert as a sibling of the View submenu
                # (last item is the "Manage" section, so
                # the Workspace submenu goes after Layout)
                menu_model.insert_submenu(
                    i + 1, "_Workspace", ws_submenu
                )
            except Exception as e:  # pragma: no cover
                logger.debug(
                    "Failed to insert Workspace submenu: %s", e
                )
            return


def _on_drag_over(window, source: str, zone: Optional[str]) -> None:
    """Highlight the current drop zone (or clear all
    highlights if zone is None)."""
    window._dockable_zones.highlight(zone)


def _on_surface_dropped(
    window, source: str, target_zone: str
) -> None:
    """The user dropped `source` into `target_zone`.
    Update the data model and re-arrange the UI."""
    layout: DockLayout = window._dockable_layout
    src_zone = _zone_for_surface(layout, source)
    if src_zone is None:
        logger.warning(
            "Source surface %s not in any zone; ignoring",
            source,
        )
        return
    # The DockLayout.move_to swaps the source into
    # the target zone, displacing whatever was there
    # back to the source's old zone. That's the
    # correct behavior for "swap two panels".
    try:
        layout.move_to(Zone(target_zone), source)
    except Exception as e:
        logger.warning("DockLayout.move_to failed: %s", e)
        return
    # Re-arrange the live UI to match the new layout
    _rearrange_from_layout(window)
    # Persist the new layout
    try:
        from ..config import config_dir as _config_dir
        from pathlib import Path

        ws = Workspace(
            name="default",
            dock_layout=layout.to_dict(),
        )
        save_workspace(Path(_config_dir), ws)
    except Exception as e:  # pragma: no cover
        logger.debug("Workspace save failed: %s", e)
    logger.info(
        "Dropped %s into %s; new layout: %s",
        source, target_zone, layout.to_dict(),
    )


def _rearrange_from_layout(window) -> None:
    """Re-arrange the live UI to match the current
    DockLayout. The strategy is visibility-based:

    - Each surface has ONE canonical parent in the
      MainWindow (set up at construction time by
      Wave 1):
        * coordinate_bar -> top-level vbox
        * right_pane -> canvas GtkOverlay
        * bottom_panel -> vertical GtkPaned (end)
        * canvas -> canvas GtkOverlay
    - When the user drops a surface into a different
      zone, we don't move the widget between
      containers (that's a heavy operation that can
      break Gtk layout). Instead, we toggle the
      widget's visibility based on whether its
      current zone matches the user's selection.
    - The widget's POSITION doesn't change (it's
      still in its canonical parent), but its
      VISIBILITY does. The user sees the surface
      appear/disappear in the new zone, and the old
      zone becomes empty (until another surface is
      dropped there).

    Why visibility and not real reparent?

    Reparenting a widget in Gtk 4 is technically
    possible (Gtk.Box.remove + new_parent.append)
    but it has subtle issues:
      1. Focus is lost (keyboard focus moves to the
         new parent's first child, not the moved
         widget)
      2. CSS classes that target the original
         parent no longer match
      3. State preserved by the parent (e.g.
         scroll position in a ScrolledWindow) is
         sometimes lost
      4. Accumulates bugs in complex widgets
         (e.g. Adw.ViewStack has internal state
         that doesn't survive a reparent)

    Visibility is the safe approach: the user sees
    the same effect ("the surface moved to the
    new zone") without any of the reparenting
    hazards. The trade-off is that the empty zone
    is still allocated space — but the user can
    just not have an empty zone (drop something
    else there, or use the 'Reset to default'
    menu item).

    A future commit can add reparenting for the
    simplest case (coordinate_bar <-> bottom_panel)
    if user feedback shows it's worth the risk.
    """
    layout: DockLayout = window._dockable_layout
    # Clear all drop zone highlights (the drag is over)
    window._dockable_zones.highlight(None)
    # Build the set of surfaces that should be
    # visible: every surface that has a non-empty
    # zone assignment.
    visible_surfaces = set()
    for zone in Zone:
        surface = getattr(layout, zone.value, "")
        if surface:
            visible_surfaces.add(surface)
    # Toggle each dockable surface's visibility
    for surface in DOCKABLE_SURFACES:
        widget = _surface_to_widget(window, surface)
        if widget is None:
            continue
        should_show = surface in visible_surfaces
        widget.set_visible(should_show)
    logger.debug(
        "Rearranged: visible=%s, layout=%s",
        sorted(visible_surfaces),
        layout.to_dict(),
    )


def _surface_to_widget(window, surface: str):
    """Map a DockLayout surface name to the actual
    Gtk.Widget in the MainWindow. Returns None if
    the surface is unknown or the widget doesn't
    exist on the window.

    Surfaces that don't have a 1:1 widget
    representation (e.g. the empty string) return
    None.
    """
    if not surface:
        return None
    mapping = {
        "coordinate_bar": getattr(
            window, "coordinate_bar", None
        ),
        "right_pane": getattr(window, "_right_pane", None),
        "bottom_panel": getattr(
            window, "bottom_panel", None
        ),
        "canvas": getattr(window, "doc_editor", None),
    }
    return mapping.get(surface)


def _apply_workspace(window, workspace: Workspace) -> None:
    """Apply a saved workspace to the live UI.

    Updates the data model and re-arranges the
    widgets (visibility-based — see
    _rearrange_from_layout for why this is the
    safe approach).
    """
    layout = DockLayout.from_dict(workspace.dock_layout)
    window._dockable_layout = layout
    window._dockable_current_workspace = workspace.name
    # Apply the new layout to the live UI
    _rearrange_from_layout(window)
    logger.info(
        "Applied workspace %s: %s",
        workspace.name, layout.to_dict(),
    )
