"""Local usage insights (opt-in, no telemetry).

The InsightsPanel shows simple, local, in-memory usage stats:

  - Session time (since last launch)
  - Total launches (since config was created)
  - Actions fired (top 10 by count, descending)
  - Mode transitions (e.g. designing -> framing count)
  - Walkthrough completion (one-shot: True if seen)
  - Coach-mark completion (how many of 6 zones shown)
  - Last action: name + timestamp

This is a local panel — no data leaves the machine. The user
opens it via the Help > Insights menu item (or
Ctrl+Shift+I), and the data is reset on demand via a
'Reset' button at the bottom of the dialog.

Why local-only? Two reasons:

  1. Privacy: shipping telemetry requires a privacy
     policy, opt-in flow, and infrastructure. Local
     insights are zero-infrastructure.
  2. Honesty: the stats reflect what the app can observe
     from its own action map, which is the only objective
     ground truth we have. Browser-based or event-based
     metrics can overcount or undercount depending on how
     the user actually interacts.

The 'usage tracker' (rayforge/util/usage.py) already records
the action fires and mode transitions. This panel just
queries that tracker at dialog-open time. No persistent
state beyond the tracker's own (in-memory) counters.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from gi.repository import Gtk, Adw, GLib

if TYPE_CHECKING:
    from ..util.local_tracker import LocalTracker

logger = logging.getLogger(__name__)


class InsightsDialog(Adw.Dialog):
    """A modal dialog showing local usage stats.

    Built once and reused across opens. Data is queried
    fresh each time (via _refresh) so the user sees up-to-
    the-second values if they keep the dialog open while
    working.
    """

    def __init__(self, tracker: "LocalTracker", **kwargs) -> None:
        super().__init__(**kwargs)
        from ..shared.util.localized import _
        self._tracker = tracker
        self.set_title(_("Insights"))
        self.set_content_width(560)
        self.set_content_height(640)

        # Outer layout: Adw.ToolbarView for the header + a
        # scrolled box for the body. The body is rebuilt
        # each time the dialog opens, so a change in the
        # tracker's state shows up immediately.
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Body — a list box with rows for each metric.
        body_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        body_box.set_margin_top(18)
        body_box.set_margin_bottom(18)
        body_box.set_margin_start(18)
        body_box.set_margin_end(18)

        # Section: session.
        self._session_section = self._build_section(
            "This session", body_box
        )
        self._session_labels = {}
        for label in (
            "Session time",
            "Total actions fired",
            "Current mode",
        ):
            row, lbl = self._build_stat_row(label)
            self._session_section.add_row(row)
            self._session_labels[label] = lbl

        # Section: top actions.
        self._actions_section = self._build_section(
            "Top 10 actions (since launch)", body_box
        )
        self._actions_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4
        )
        self._actions_section.add_row(
            Gtk.ListBoxRow(child=self._actions_list)
        )

        # Section: configuration.
        self._config_section = self._build_section(
            "Configuration", body_box
        )
        self._config_labels = {}
        for label in (
            "Walkthrough seen",
            "Coach marks shown",
            "Layout preset",
            "Toolbar mode",
        ):
            row, lbl = self._build_stat_row(label)
            self._config_section.add_row(row)
            self._config_labels[label] = lbl

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(body_box)
        scrolled.set_vexpand(True)
        toolbar_view.set_content(scrolled)

        # Footer: a small note + reset button.
        footer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
        )
        footer.set_margin_top(6)
        footer.set_margin_bottom(12)
        footer.set_margin_start(18)
        footer.set_margin_end(18)
        note = Gtk.Label()
        note.set_markup(
            "<small>All data is local. Nothing is sent to "
            "any server. Counts reset when the app restarts.</small>"
        )
        note.set_xalign(0.0)
        note.set_hexpand(True)
        reset_btn = Gtk.Button(label="Reset session")
        reset_btn.add_css_class("destructive-action")
        reset_btn.connect("clicked", self._on_reset_clicked)
        footer.append(note)
        footer.append(reset_btn)
        toolbar_view.add_bottom_bar(footer)

        self.set_child(toolbar_view)

    @staticmethod
    def _build_section(title: str, parent: Gtk.Box) -> Gtk.ListBox:
        """Build a labelled, separated section row.

        Returns the inner ListBox; rows can be appended
        with add_row. The title is rendered as an Adw
        preferences group (since the rest of the app uses
        those)."""
        from ..core.config import get_context

        config = get_context().config()
        group = Adw.PreferencesGroup()
        group.set_title(title)
        listbox = Gtk.ListBox()
        listbox.add_css_class("boxed-list")
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        group.add(listbox)
        parent.append(group)
        return listbox

    @staticmethod
    def _build_stat_row(label: str) -> tuple[Gtk.ListBoxRow, Gtk.Label]:
        """Build a row with a left label and a right value.

        The value is the empty string by default; callers
        fill it in via _refresh."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        lbl_left = Gtk.Label(label=label)
        lbl_left.set_xalign(0.0)
        lbl_left.set_hexpand(True)
        lbl_right = Gtk.Label(label="")
        lbl_right.set_xalign(1.0)
        lbl_right.add_css_class("dim-label")
        lbl_right.add_css_class("numeric")
        box.append(lbl_left)
        box.append(lbl_right)
        row.set_child(box)
        return row, lbl_right

    def _refresh(self) -> None:
        """Read fresh data from the tracker + config.

        Called once on open and any time the dialog is
        re-shown. Cheap (a few dict lookups)."""
        from ..core.config import get_context

        config = get_context().config()

        # Session stats
        self._session_labels["Session time"].set_text(
            self._tracker.format_session_time()
        )
        self._session_labels["Total actions fired"].set_text(
            str(self._tracker.total_actions)
        )
        self._session_labels["Current mode"].set_text(
            self._tracker.current_mode or "—"
        )

        # Top 10 actions
        top = self._tracker.top_actions(10)
        # Clear old list
        while self._actions_list.get_first_child() is not None:
            self._actions_list.remove(
                self._actions_list.get_first_child()
            )
        for name, count in top:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            row.set_margin_top(2)
            row.set_margin_bottom(2)
            lbl = Gtk.Label(label=name)
            lbl.set_xalign(0.0)
            lbl.set_hexpand(True)
            lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            count_lbl = Gtk.Label(label=str(count))
            count_lbl.set_xalign(1.0)
            count_lbl.add_css_class("dim-label")
            count_lbl.add_css_class("numeric")
            row.append(lbl)
            row.append(count_lbl)
            self._actions_list.append(row)
        if not top:
            empty = Gtk.Label(label="(no actions fired yet)")
            empty.add_css_class("dim-label")
            empty.set_xalign(0.0)
            self._actions_list.append(empty)

        # Config stats
        self._config_labels["Walkthrough seen"].set_text(
            "Yes" if config.walkthrough_seen else "No"
        )
        seen = len(config.coach_marks_seen or [])
        self._config_labels["Coach marks shown"].set_text(
            f"{seen} / 6"
        )
        self._config_labels["Layout preset"].set_text(
            config.panel_layout or "default"
        )
        self._config_labels["Toolbar mode"].set_text(
            config.toolbar_mode or "essential"
        )

    def _on_reset_clicked(self, _btn) -> None:
        self._tracker.reset_session()
        self._refresh()

    def do_opened(self) -> None:
        # Re-read on each open so the dialog always shows
        # the freshest stats.
        self._refresh()
        super().do_opened()
