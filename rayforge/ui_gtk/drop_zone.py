"""Drop zone registry — tracks the hit-test zones for
the DragController.

GTK 4 has no built-in docking manager; instead we
build a minimal one out of GtkOverlay + a registry
of GtkDrawingArea 'drop zones' that the controller
queries for hit-tests.

How it works:

  1. The MainWindow places a DropZoneOverlay on
     top of the main UI (a transparent GtkOverlay
     with a list of DropZone children)
  2. Each DropZone is a thin (4-8px wide) Gtk.Box on
     one edge of the main UI:
       - top: a horizontal bar above the canvas
       - right: a vertical strip to the right
       - bottom: a horizontal bar below
       - left: a vertical strip to the left
       - center: the canvas itself
  3. Each DropZone is registered with the registry
     in its 'realize' signal (when its bounds are
     known)
  4. The DragController calls get_zones() on every
     drag-motion to get the current hit-test list
  5. The MainWindow observes the controller's
     'drag-over' signal and shows a highlight on the
     active zone

The zones are LAYOUT-RELATIVE, not pixel-relative.
The registry uses the widget's allocation
(x, y, width, height) to compute pixel bounds each
time get_zones() is called. This means moving or
resizing the window keeps the hit-test correct
without explicit re-registration.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .drag_controller import ZoneBounds

logger = logging.getLogger(__name__)


# Visual constants — kept here so the UI and the
# hit-test stay in sync
DROP_ZONE_THICKNESS = 8  # px, the visible strip width
HIGHLIGHT_OPACITY_ACTIVE = 0.4  # when this zone is the drop target
HIGHLIGHT_OPACITY_IDLE = 0.0  # default


class DropZone(Gtk.Box):
    """A single drop zone widget.

    A thin strip on one edge of the main UI. The
    strip is transparent most of the time; the
    registry paints a highlight on the active one.

    Subclasses or inline implementations can
    customize the visual (e.g. a center zone might
    be a full-overlay rectangle, not a strip).
    """

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._zone_name = name
        self._highlight = 0.0
        # The highlight is a CSS class toggled on/off
        # to keep this widget framework-agnostic
        self.add_css_class("drop-zone")
        self.set_opacity(HIGHLIGHT_OPACITY_IDLE)

    @property
    def zone_name(self) -> str:
        return self._zone_name

    def set_highlighted(self, active: bool) -> None:
        """Toggle the visual highlight on this zone.

        Called by the MainWindow on every
        'drag-over' event from the controller.
        """
        if active:
            self.set_opacity(HIGHLIGHT_OPACITY_ACTIVE)
            self.add_css_class("drop-zone-active")
        else:
            self.set_opacity(HIGHLIGHT_OPACITY_IDLE)
            self.remove_css_class("drop-zone-active")


class DropZoneRegistry:
    """Hit-test registry for drop zones.

    Maps zone name (e.g. 'top', 'right') to the
    DropZone widget. The get_zones() method returns
    the current pixel bounds of each zone, ready to
    feed to DragController.update_drag.

    Hit-test coordinates are in the same coordinate
    space as GtkEventMotion x/y (root window
    coordinates). Each DropZone's allocation is
    translated to root coordinates via
    Gtk.Widget.translate_coordinates.
    """

    def __init__(self) -> None:
        self._zones: Dict[str, DropZone] = {}

    def register(self, zone: DropZone) -> None:
        """Register a DropZone with the registry.

        The zone is added by zone_name. Re-registering
        a zone with the same name replaces the
        previous entry.
        """
        self._zones[zone.zone_name] = zone
        logger.debug("Registered drop zone: %s", zone.zone_name)

    def unregister(self, name: str) -> None:
        self._zones.pop(name, None)

    def get_zone(self, name: str) -> Optional[DropZone]:
        return self._zones.get(name)

    def get_all_zones(self) -> List[DropZone]:
        return list(self._zones.values())

    def get_zones(
        self, root: Gtk.Widget
    ) -> List[ZoneBounds]:
        """Return the current pixel bounds of all zones.

        Each entry is (zone_name, (x, y, width, height))
        in root window coordinates. The DragController
        consumes this list to do hit-tests.

        `root` is the widget that owns the drop zones
        (typically the MainWindow). It's used to
        translate child widget coordinates to root
        coordinates.

        A zone with no allocation (not yet realized,
        or hidden) is omitted from the result so the
        controller can't try to drop on it.
        """
        result: List[ZoneBounds] = []
        for name, zone in self._zones.items():
            if not zone.get_visible() or not zone.get_realized():
                continue
            alloc = zone.get_allocation()
            # Translate to root coordinates
            ok, rx, ry = zone.translate_coordinates(
                root, 0, 0
            )
            if not ok:
                continue
            # translate_coordinates gives the position
            # of the child's origin (0, 0) in the
            # parent's coordinate system. Width/height
            # are not translated.
            result.append(
                (name, (rx, ry, alloc.width, alloc.height))
            )
        return result

    def highlight(self, name: Optional[str]) -> None:
        """Highlight the named zone; clear all others.

        `name=None` clears all highlights (drag
        finished, or cursor outside any zone).
        """
        for zone_name, zone in self._zones.items():
            zone.set_highlighted(zone_name == name)
