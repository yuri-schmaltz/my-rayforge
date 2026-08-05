"""Drag controller for dockable panels.

Coordinates the drag-and-drop of surfaces between
zones. This is the logic layer; the visual layer
(drop zones, drag handles) is separate and lives
in the MainWindow.

Lifecycle:

  1. User presses a drag handle on a surface
     (GestureDrag emits 'drag-begin')
  2. The controller stores (source_surface, start_xy)
  3. As the user moves, the controller queries the
     DropZoneRegistry for which zone the cursor is over
  4. When the user releases, the controller calls
     DockLayout.move_to(target_zone, source_surface)
     and emits the 'dropped' signal

The controller is UI-framework agnostic (no Gtk
imports in this file). The MainWindow provides a
concrete DropZoneRegistry and DragHandle widget that
call into the controller.

Why no Gtk imports here? The controller is
unit-testable without a display. The MainWindow
integration is a separate layer (more complex, more
fragile, harder to test). Keeping them separate means
the logic is verified by fast unit tests and the UI
is verified by visual inspection.
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# A surface is just a string identifier (matches the
# DockLayout fields: 'right_pane', 'bottom_panel',
# 'canvas', 'coordinate_bar', etc).
Surface = str


# A hit-test zone is (zone_name, bounds_rect). The
# DropZoneRegistry is queried on each drag-motion to
# determine which zone the cursor is over. The
# bounds are (x, y, width, height) in the same
# coordinate space as the drag events.
ZoneBounds = Tuple[str, Tuple[float, float, float, float]]


class DragController:
    """State machine for a single drag operation.

    Not thread-safe. One instance per MainWindow; the
    controller is reused across drag operations (a
    'begin' on a finished controller is a new drag).

    The controller doesn't own any widgets; it's a
    pure logic component. The caller (MainWindow)
    connects GestureDrag events to the begin/update/end
    methods and observes the signals.
    """

    def __init__(self) -> None:
        self._source: Optional[Surface] = None
        self._start_xy: Optional[Tuple[float, float]] = None
        self._current_zone: Optional[str] = None
        # Listener for 'dropped' (source, target_zone)
        self._on_dropped: Optional[
            Callable[[Surface, str], None]
        ] = None
        # Listener for 'drag-over' (source, zone or None)
        self._on_drag_over: Optional[
            Callable[[Surface, Optional[str]], None]
        ] = None

    def set_dropped_callback(
        self, fn: Callable[[Surface, str], None]
    ) -> None:
        """Register a callback for 'dropped' events.

        The callback is invoked from end_drag() with
        (source_surface, target_zone). The callback
        should:
          1. Update the DockLayout
          2. Re-arrange the UI to match
          3. Persist the new layout
        """
        self._on_dropped = fn

    def set_drag_over_callback(
        self, fn: Callable[[Surface, Optional[str]], None]
    ) -> None:
        """Register a callback for 'drag-over' events.

        Called on every drag-motion with the new
        current_zone (or None if the cursor is outside
        any drop zone). The callback typically updates
        visual feedback (highlight the active zone).
        """
        self._on_drag_over = fn

    def begin_drag(
        self, source: Surface, x: float, y: float
    ) -> None:
        """Start a drag operation.

        The controller stores the source surface and
        the cursor position. The 'drag-over' callback
        is invoked once with zone=None (no zone is
        active yet at the start position).
        """
        if self._source is not None:
            logger.warning(
                "begin_drag called while drag in progress; "
                "force-cancelling previous drag"
            )
        self._source = source
        self._start_xy = (x, y)
        self._current_zone = None
        if self._on_drag_over:
            self._on_drag_over(source, None)

    def update_drag(
        self, x: float, y: float, zones: List[ZoneBounds]
    ) -> None:
        """Update the drag with the current cursor position.

        Iterates over the registered zones and finds
        the one whose bounds contain (x, y). Calls the
        'drag-over' callback with the matched zone (or
        None if the cursor is outside all zones).
        """
        if self._source is None:
            return  # no drag in progress
        new_zone = None
        for zone_name, (zx, zy, zw, zh) in zones:
            if zx <= x <= zx + zw and zy <= y <= zy + zh:
                new_zone = zone_name
                break
        if new_zone != self._current_zone:
            self._current_zone = new_zone
            if self._on_drag_over:
                self._on_drag_over(self._source, new_zone)

    def end_drag(
        self, x: float, y: float, zones: List[ZoneBounds]
    ) -> Optional[Tuple[Surface, str]]:
        """End the drag. Returns (source, target_zone) on
        a successful drop, or None if the drag was
        cancelled (released outside any zone, or no
        drag in progress).

        Side effect: invokes the 'dropped' callback if
        a drop occurred.
        """
        if self._source is None:
            return None
        # Re-run hit test with the final position
        target_zone = None
        for zone_name, (zx, zy, zw, zh) in zones:
            if zx <= x <= zx + zw and zy <= y <= zy + zh:
                target_zone = zone_name
                break
        source = self._source
        self._source = None
        self._start_xy = None
        self._current_zone = None
        if target_zone is not None and self._on_dropped:
            self._on_dropped(source, target_zone)
            return (source, target_zone)
        return None

    def cancel_drag(self) -> None:
        """Cancel the drag without firing 'dropped'."""
        self._source = None
        self._start_xy = None
        self._current_zone = None

    @property
    def is_dragging(self) -> bool:
        return self._source is not None

    @property
    def current_source(self) -> Optional[Surface]:
        return self._source

    @property
    def current_zone(self) -> Optional[str]:
        return self._current_zone
