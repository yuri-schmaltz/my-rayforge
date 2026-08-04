"""First-interaction coach marks.

The first-run walkthrough (walkthrough.py) shows 5 cards on
the very first launch. After it's dismissed, the user is
on their own. But the walkthrough is high-level ("here's
the right pane"), not tied to actual usage. Coach marks
are the per-zone follow-up: the first time the user clicks
on each major surface, a small popover appears next to it
with one sentence of "what this is" + "what to do here".

This addresses the gap between "I know the zones exist" and
"I know what to do IN this zone". For example, the
walkthrough shows the right pane exists; the coach mark for
the right pane shows "Click an object on the canvas to see
its properties here".

Coach marks are seen flags, persisted to
config.coach_marks_seen (a list of zone names that have
been shown). Zones:

  - "toolbar"   : first time the user clicks ANY toolbar button
  - "canvas"    : first time the user clicks on the canvas
  - "right_pane": first time a selection is auto-shown in
                  the right pane (not a click — a state)
  - "bottom"    : first time the user switches to a bottom tab
  - "coord"     : first time the user changes the unit selector
  - "status"    : first time the mode badge changes

To avoid popover spam, only one coach mark shows at a time
(the most recently triggered one wins, shown via
GLib.idle_add so the main-window click event has finished
processing). Once shown, the zone's flag is added to the
seen list and the popover is dismissed permanently.
"""
from __future__ import annotations

import logging
from typing import Optional

from gi.repository import Gtk, GLib, GObject

logger = logging.getLogger(__name__)


# Coach mark content per zone. Kept short (one title + one
# sentence) so the popover is a glance, not a paragraph.
COACH_MARKS = {
    "toolbar": (
        "Toolbar",
        "Frame, then send — that's the core loop. Press "
        "<b>F5</b> to send the current operation.",
    ),
    "canvas": (
        "Canvas",
        "Click and drag to pan, scroll to zoom. <b>Hold "
        "Space</b> to move, <b>R</b> to rotate the view.",
    ),
    "right_pane": (
        "Properties",
        "Click an object on the canvas to see and edit its "
        "settings here.",
    ),
    "bottom": (
        "Console / G-code",
        "Watch jobs run here. The gcode viewer shows the "
        "actual instructions sent to the machine.",
    ),
    "coord": (
        "Coordinate bar",
        "Live cursor X / Y plus selection size. Switch units "
        "any time — the choice is remembered.",
    ),
    "status": (
        "Status bar",
        "The colored badge shows the current mode "
        "(green = designing, blue = framing, etc).",
    ),
}


# Register the 'dismissed' signal on Gtk.Popover subclasses.
# Gtk.Popover already has 'closed'; we add 'dismissed' to
# fire specifically when the popover fully exits, and to
# carry the zone name (since 'closed' doesn't).
GObject.signal_new(
    "dismissed",
    Gtk.Popover,
    GObject.SignalFlags.RUN_LAST,
    GObject.TYPE_NONE,
    (GObject.TYPE_STRING,),
)


class CoachMark(Gtk.Popover):
    """A small popover with a one-sentence hint.

    Built once per zone, reused. The popover auto-dismisses
    after DISMISS_AFTER_MS; the close button forces an early
    dismiss. The 'dismissed' signal is what callers listen
    to in order to mark the zone as seen in config.
    """

    DISMISS_AFTER_MS = 8000

    def __init__(self, zone: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._zone = zone
        self._timeout_id: Optional[int] = None

        title, body = COACH_MARKS.get(zone, (zone, ""))

        # Content
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{title}</b>")
        title_label.set_xalign(0.0)
        title_label.add_css_class("coach-title")

        body_label = Gtk.Label()
        body_label.set_markup(body)
        body_label.set_xalign(0.0)
        body_label.set_wrap(True)
        body_label.set_max_width_chars(40)
        body_label.add_css_class("coach-body")

        dismiss_btn = Gtk.Button(label="Got it")
        dismiss_btn.add_css_class("flat")
        dismiss_btn.set_halign(Gtk.Align.END)
        dismiss_btn.connect("clicked", lambda _b: self.popdown())

        box.append(title_label)
        box.append(body_label)
        box.append(dismiss_btn)
        self.set_child(box)
        self.set_autohide(True)
        self.set_has_arrow(True)
        self.set_position(Gtk.PositionType.BOTTOM)

        # Auto-dismiss after the timeout.
        self._timeout_id = GLib.timeout_add(
            self.DISMISS_AFTER_MS, self._on_timeout
        )

    def _on_timeout(self) -> bool:
        self.popdown()
        return False

    def do_closed(self) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        # Notify external listeners (the MainWindow registers
        # a callback to update config.coach_marks_seen).
        self.emit("dismissed", self._zone)
        super().do_closed()
