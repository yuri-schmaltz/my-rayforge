"""Status bar widget for the main window.

Sits at the bottom of the window, above the bottom panel. Provides
always-on feedback for:

- Current mode (Designing, Framing, Sending, Paused, Alarm) as a
  colored badge to the left.
- Cursor position (X, Y) in the configured unit. Updated on
  mouse-move events from the canvas.
- Layer info (current layer / total layers).
- Operation info (current operation type, e.g. Engrave / Contour).
- Job progress bar (visible only when a job is running).

This widget exists to give the user a single, glanceable source of
truth for "what is the app doing right now". Previously the
status_message_label was an overlay on the canvas corner — easy to
miss, easy to ignore, and not informative about mode/layer/op.

The status bar is a pure presentation layer. Mode detection and
state update is the caller's job (the MainWindow updates the
public methods when state changes).
"""
from __future__ import annotations

import logging
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..shared.util.localized import _  # noqa: E402

logger = logging.getLogger(__name__)


# Mode → (label, css-class-for-color). The CSS classes are defined
# in rayforge/resources/styles/forge.css under
# `.forge-statusbar-mode-{key}`.
_VALID_MODES = ("designing", "framing", "sending", "paused", "alarm", "idle")


class StatusBar(Gtk.Box):
    """The persistent status bar at the bottom of the main window.

    Layout (left to right):
        [MODE BADGE]  [X: 12.3]  [Y: 45.6]  |  [Layer 2/3]  [Op: Engrave]  |  [PROGRESS BAR]
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8, **kwargs
        )
        self.add_css_class("forge-statusbar")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(2)
        self.set_margin_bottom(2)

        # ---- Mode badge (left) ----
        self._mode_badge = Gtk.Label(label=_("Idle"))
        self._mode_badge.add_css_class("forge-statusbar-mode-badge")
        self._mode_badge.add_css_class("forge-statusbar-mode-idle")
        self.append(self._mode_badge)

        # ---- Cursor coordinates (X, Y) ----
        self._separator1 = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL
        )
        self._separator1.set_margin_start(4)
        self._separator1.set_margin_end(4)
        self.append(self._separator1)

        self._x_label = Gtk.Label(label="X: —")
        self._x_label.add_css_class("forge-statusbar-mono")
        self.append(self._x_label)

        self._y_label = Gtk.Label(label="Y: —")
        self._y_label.add_css_class("forge-statusbar-mono")
        self.append(self._y_label)

        # ---- Accessibility ----
        # The status bar is a live region (the screen reader
        # re-announces its contents when they change). Each
        # sub-widget gets a role + label so orca can announce
        # 'X: 12.5, Y: 8.0' instead of just 'label'.
        from ..shared.util.a11y import (
            set_a11y_label,
            mark_live_region,
        )

        set_a11y_label(
            self._mode_badge,
            _("Mode indicator"),
            description=_(
                "Current app state: designing, framing, "
                "sending, paused, alarm, or idle"
            ),
            role=Gtk.AccessibleRole.STATUS,
        )
        set_a11y_label(
            self._x_label,
            _("Cursor X coordinate"),
            role=Gtk.AccessibleRole.LABEL,
        )
        set_a11y_label(
            self._y_label,
            _("Cursor Y coordinate"),
            role=Gtk.AccessibleRole.LABEL,
        )
        # The bar itself is the live region root.
        mark_live_region(self)

        # ---- Layer + operation info ----
        self._separator2 = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL
        )
        self._separator2.set_margin_start(4)
        self._separator2.set_margin_end(4)
        self.append(self._separator2)

        self._layer_label = Gtk.Label(label=_("No layer"))
        self.append(self._layer_label)

        self._op_label = Gtk.Label(label="")
        self._op_label.set_hexpand(True)  # Push progress to the right
        self._op_label.set_halign(Gtk.Align.START)
        self.append(self._op_label)

        # ---- Progress bar (right) ----
        self._progress = Gtk.ProgressBar()
        self._progress.set_size_request(160, -1)
        self._progress.set_valign(Gtk.Align.CENTER)
        self._progress.set_visible(False)
        self.append(self._progress)

    # ---- Public API ----

    def set_mode(self, mode: str, label: Optional[str] = None) -> None:
        """Set the mode badge.

        Args:
            mode: One of "designing", "framing", "sending", "paused",
                "alarm", or "idle". Unknown values fall back to "idle".
            label: Optional override for the badge text. Defaults to
                a capitalized version of `mode`.
        """
        if mode not in _VALID_MODES:
            mode = "idle"
        # Strip previous mode-* classes
        for m in _VALID_MODES:
            cls = f"forge-statusbar-mode-{m}"
            if self._mode_badge.has_css_class(cls):
                self._mode_badge.remove_css_class(cls)
        self._mode_badge.add_css_class(f"forge-statusbar-mode-{mode}")
        if label is None:
            label = mode.capitalize()
        self._mode_badge.set_text(label)
        # Mirror the change to the local tracker so the
        # Insights dialog can show "current mode" and
        # "mode transitions since launch". Best-effort —
        # we never want a tracker failure to break the
        # status bar.
        try:
            from ..util.local_tracker import get_local_tracker

            get_local_tracker().record_mode(mode)
        except Exception:  # pragma: no cover
            pass

    def set_cursor_position(self, x: Optional[float], y: Optional[float]) -> None:
        """Set the cursor coordinates shown in the status bar.

        Pass None for either axis to show '—' (no data).
        """
        from ..shared.util.localized import _
        if x is None:
            self._x_label.set_text(_("X: —"))
        else:
            self._x_label.set_text(_("X: %.2f") % x)
        if y is None:
            self._y_label.set_text(_("Y: —"))
        else:
            self._y_label.set_text(_("Y: %.2f") % y)

    def set_layer_info(self, current: Optional[int], total: Optional[int]) -> None:
        """Show the current layer index and total count.

        Pass None for either to omit (shows 'No layer').
        """
        if current is None or total is None or total == 0:
            self._layer_label.set_text(_("No layer"))
        else:
            self._layer_label.set_text(_("Layer {cur}/{tot}").format(
                cur=current, tot=total
            ))

    def set_operation(self, op_label: str) -> None:
        """Show the current operation type (e.g. 'Engrave', 'Contour')."""
        if op_label:
            self._op_label.set_text(_("Op: {label}").format(label=op_label))
        else:
            self._op_label.set_text("")

    def set_progress(self, fraction: Optional[float]) -> None:
        """Show or hide the progress bar.

        Pass None to hide. Pass 0.0..1.0 to show and set.
        """
        if fraction is None:
            self._progress.set_visible(False)
        else:
            self._progress.set_visible(True)
            self._progress.set_fraction(max(0.0, min(1.0, fraction)))
