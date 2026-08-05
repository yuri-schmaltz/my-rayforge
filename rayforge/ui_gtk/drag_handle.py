"""Drag handle widget — a small bar on a surface
that the user can grab to start a drag operation.

A surface (right_pane, bottom_panel, canvas) gets a
DragHandle added. The DragHandle is a thin (16px)
Gtk.Box with a hover state and a GestureDrag that
fires 'drag-begin' / 'drag-update' / 'drag-end'
signals. The MainWindow connects these to the
DragController.

Visual:

  ┌────────────────────────────┐
  │ ≡  right_pane              │   <- DragHandle (top of widget)
  ├────────────────────────────┤
  │                            │
  │     (the actual surface)   │
  │                            │
  └────────────────────────────┘

The handle is 16px tall by default, with a 'grab'
cursor. On hover, the background darkens slightly
(theme-driven via CSS). The '≡' icon (Unicode
'HORIZONTAL LINE STACK') signals 'draggable'.

Why a separate widget (not the surface itself)?
The user needs an explicit, easy-to-grab target.
The surface is large but most of it is content
(buttons, text, etc.) that has its own click
behavior. Putting a dedicated handle at the top
of each dockable surface makes the drag affordance
discoverable without interfering with the
surface's own interactions.
"""
from __future__ import annotations

import logging
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject, Gtk  # noqa: E402

logger = logging.getLogger(__name__)


# Visual constants
HANDLE_HEIGHT = 16  # px
HANDLE_OPACITY_IDLE = 0.0
HANDLE_OPACITY_HOVER = 0.3


class DragHandle(Gtk.Box):
    """A drag handle for a dockable surface.

    Emits three signals (GObject signals):
      - 'drag-begin' (start_x_root, start_y_root)
      - 'drag-update' (current_x_root, current_y_root)
      - 'drag-end' (end_x_root, end_y_root)
    The coordinates are in root window coordinates
    (Gtk root or toplevel), ready to feed to
    DragController.

    The handle is a horizontal Gtk.Box with one
    Label child (a '≡' glyph). It's invisible by
    default (opacity 0) and fades in on hover.
    """

    __gsignals__ = {
        "drag-begin": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (float, float),
        ),
        "drag-update": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (float, float),
        ),
        "drag-end": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (float, float),
        ),
    }

    def __init__(
        self,
        surface_name: str,
        label: str = "≡",
        **kwargs,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL, **kwargs
        )
        self._surface_name = surface_name
        self.set_size_request(-1, HANDLE_HEIGHT)
        self.set_opacity(HANDLE_OPACITY_IDLE)
        self.add_css_class("drag-handle")
        # The grab cursor
        self.set_cursor(
            Gtk.Cursor.new_from_name("grab", None)
        )

        # The icon label
        self._icon = Gtk.Label(label=label)
        self._icon.set_xalign(0.5)
        self._icon.set_hexpand(True)
        self.append(self._icon)

        # Hover highlight
        self._motion_controller = Gtk.EventControllerMotion()
        self._motion_controller.connect(
            "enter", self._on_hover_enter
        )
        self._motion_controller.connect(
            "leave", self._on_hover_leave
        )
        self.add_controller(self._motion_controller)

        # The actual drag gesture
        self._drag_gesture = Gtk.GestureDrag()
        self._drag_gesture.set_button(1)  # left mouse
        self._drag_gesture.connect(
            "drag-begin", self._on_gesture_begin
        )
        self._drag_gesture.connect(
            "drag-update", self._on_gesture_update
        )
        self._drag_gesture.connect(
            "drag-end", self._on_gesture_end
        )
        self.add_controller(self._drag_gesture)

    @property
    def surface_name(self) -> str:
        return self._surface_name

    def _on_hover_enter(
        self, _controller, _x: float, _y: float
    ) -> None:
        self.set_opacity(HANDLE_OPACITY_HOVER)
        self.add_css_class("drag-handle-hover")

    def _on_hover_leave(self, _controller) -> None:
        self.set_opacity(HANDLE_OPACITY_IDLE)
        self.remove_css_class("drag-handle-hover")

    def _on_gesture_begin(
        self, gesture: Gtk.GestureDrag, x: float, y: float
    ) -> None:
        # Translate to root coordinates
        ok, rx, ry = self.translate_coordinates(
            Gtk.Widget.get_root(self), x, y
        )
        if not ok:
            rx, ry = x, y
        # Switch the cursor to 'grabbing'
        self.set_cursor(
            Gtk.Cursor.new_from_name("grabbing", None)
        )
        self.emit("drag-begin", rx, ry)

    def _on_gesture_update(
        self, gesture: Gtk.GestureDrag, x: float, y: float
    ) -> None:
        # Use the offset from drag-begin; convert
        # to absolute root coordinates by adding
        # the begin position stored on the gesture.
        # Gtk.GestureDrag.get_offset returns the
        # delta; we want absolute position which
        # is (start_root + offset).
        # Simpler: we re-translate from the widget
        # origin every time.
        ok, rx, ry = self.translate_coordinates(
            Gtk.Widget.get_root(self), 0, 0
        )
        if ok:
            rx += x
            ry += y
        else:
            rx, ry = x, y
        self.emit("drag-update", rx, ry)

    def _on_gesture_end(
        self, gesture: Gtk.GestureDrag, x: float, y: float
    ) -> None:
        ok, rx, ry = self.translate_coordinates(
            Gtk.Widget.get_root(self), 0, 0
        )
        if ok:
            rx += x
            ry += y
        else:
            rx, ry = x, y
        self.set_cursor(
            Gtk.Cursor.new_from_name("grab", None)
        )
        self.emit("drag-end", rx, ry)
