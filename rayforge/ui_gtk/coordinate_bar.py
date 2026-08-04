"""Coordinate bar widget for the main window.

Sits at the top of the canvas, just below the header. Shows:

- X, Y: cursor position in the configured unit (live, updated on
  mouse-move events from the canvas).
- L, W, H: length, width, height of the selection (live,
  updated on selection change).

A unit selector dropdown (mm / in / px) lets the user change
the display unit on the fly. The choice is persisted to config
(unit_preferences.length).

The widget is a thin presentation layer. It receives updates
via the public methods set_cursor_position and
set_selection_dimensions; it does not own the selection or the
canvas.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

logger = logging.getLogger(__name__)


_VALID_UNITS = ("mm", "in", "px")


class CoordinateBar(Gtk.Box):
    """Persistent coordinate readout above the canvas.

    Layout: X  Y  L  W  H  [unit]
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12, **kwargs
        )
        self.add_css_class("forge-coordinate-bar")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(2)
        self.set_margin_bottom(2)

        # Helper to build a labeled readout. label_text is the
        # fixed part (e.g. "X:"); value_text is the dynamic part.
        def _make_field(label_text: str, css_class: str) -> Gtk.Label:
            lbl = Gtk.Label(label=f"{label_text} —")
            lbl.add_css_class(css_class)
            self.append(lbl)
            return lbl

        self._x_label = _make_field("X:", "forge-coord-mono")
        self._y_label = _make_field("Y:", "forge-coord-mono")

        self._separator1 = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL
        )
        self._separator1.set_margin_start(4)
        self._separator1.set_margin_end(4)
        self.append(self._separator1)

        self._l_label = _make_field("L:", "forge-coord-mono")
        self._w_label = _make_field("W:", "forge-coord-mono")
        self._h_label = _make_field("H:", "forge-coord-mono")

        # Spacer pushes the unit selector to the right.
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.append(spacer)

        # Unit selector
        self._unit_combo = Gtk.ComboBoxText()
        for unit in _VALID_UNITS:
            self._unit_combo.append_text(unit)
        self._unit_combo.set_active(0)  # mm
        self._unit_combo.connect("changed", self._on_unit_changed)
        self._unit_combo.set_tooltip_text(
            _("Display unit for coordinates and dimensions")
        )
        self.append(self._unit_combo)

    # ---- Public API ----

    def set_cursor_position(self, x: Optional[float], y: Optional[float]) -> None:
        """Update the X/Y cursor readouts. Pass None to clear."""
        self._x_label.set_text(f"X: {self._fmt(x)}")
        self._y_label.set_text(f"Y: {self._fmt(y)}")

    def set_selection_dimensions(
        self, length: Optional[float], width: Optional[float], height: Optional[float]
    ) -> None:
        """Update the L/W/H selection readouts. Pass None to clear."""
        self._l_label.set_text(f"L: {self._fmt(length)}")
        self._w_label.set_text(f"W: {self._fmt(width)}")
        self._h_label.set_text(f"H: {self._fmt(height)}")

    def set_unit(self, unit: str) -> None:
        """Set the display unit programmatically. The selection is
        read back via the unit signal so the caller (MainWindow)
        can re-render the canvas in the new unit."""
        if unit not in _VALID_UNITS:
            unit = "mm"
        idx = _VALID_UNITS.index(unit)
        # set_active triggers 'changed'; we guard inside the handler
        # so a no-op re-set doesn't trigger a config write.
        if self._unit_combo.get_active() != idx:
            self._unit_combo.set_active(idx)

    def get_unit(self) -> str:
        return _VALID_UNITS[self._unit_combo.get_active()]

    def connect_unit_changed(self, callback):
        """Connect a listener that fires when the user changes the
        unit. Callback receives the new unit string (e.g. 'mm')."""
        return self._unit_combo.connect("changed", self._wrap_unit_signal(callback))

    # ---- Internal ----

    def _wrap_unit_signal(self, callback):
        """Adapter: emit a simple (unit) signal instead of ComboBox's
        raw 'changed' event with no payload."""
        def _on_change(combo):
            callback(self.get_unit())
        return _on_change

    def _on_unit_changed(self, combo):
        # Local-side hook; the actual config persistence is
        # done by the callback connected via connect_unit_changed.
        pass

    @staticmethod
    def _fmt(value: Optional[float]) -> str:
        """Format a numeric value for the readout, or '—' if None."""
        if value is None:
            return "—"
        # Avoid trailing .0 noise: keep one decimal for mm/in,
        # integer for px.
        if abs(value) < 0.05:
            return "0"
        if abs(value - round(value)) < 0.05:
            return f"{int(round(value))}"
        return f"{value:.2f}"
