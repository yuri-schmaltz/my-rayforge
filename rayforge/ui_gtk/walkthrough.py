"""First-run walkthrough dialog for Pires Forge.

A 5-card carousel that introduces the four main zones of the
app on first launch:

  1. Canvas — the work area
  2. Right pane — operation + properties
  3. Toolbar — frame before send
  4. Coordinate bar — live X/Y/L/W/H
  5. Command palette — Ctrl+Shift+P for anything else

The walkthrough is opt-in: it shows the first time the user
launches the app, and stores a flag in config so it never
shows again unless the user re-opens it from the Help menu.

Implementation:
- Adw.Dialog as the host (modal, content-fits, dismissable).
- Adw.Carousel + Adw.CarouselIndicatorDots for the 5 pages.
- Each page is a small Adw.PreferencesGroup with a heading,
  a description, and a zone highlight (a small icon + label
  indicating the area of the screen being described).
- Skip / Next / Done buttons in the footer.
"""
from __future__ import annotations

import logging
from typing import List

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk  # noqa: E402

logger = logging.getLogger(__name__)


class WalkthroughDialog(Adw.Dialog):
    """Modal first-run tour of the main UI zones.

    Pages are defined in WALKTHROUGH_PAGES below. Each page is
    a (zone_label, title, body) tuple. The dialog is dismissed
    via the 'walkthrough-done' or 'walkthrough-skip' signals;
    the caller (MainWindow) is responsible for persisting the
    seen flag in config.
    """

    WALKTHROUGH_PAGES: List[dict] = [
        {
            "zone": _("Canvas"),
            "title": _("Your work area"),
            "body": _(
                "This is the canvas. Open an SVG, draw with the "
                "sketcher, or drop in a photo. The 3D Preview button "
                "in the toolbar shows the toolpath before you cut."
            ),
        },
        {
            "zone": _("Right pane"),
            "title": _("Operations + properties"),
            "body": _(
                "Pick an operation (Contour, Engrave, etc.) on the "
                "Workflow tab. The Properties tab shows the parameters "
                "of whatever you have selected on the canvas."
            ),
        },
        {
            "zone": _("Toolbar"),
            "title": _("Frame, then Send"),
            "body": _(
                "The Frame button cycles the laser around the occupied "
                "area without firing — always use it before Send. The "
                "toolbar has a '...' button to reveal advanced tools "
                "(home, focus, alarm handling)."
            ),
        },
        {
            "zone": _("Coordinate bar"),
            "title": _("Live X/Y/L/W/H"),
            "body": _(
                "The thin bar above the canvas shows the cursor position "
                "and the dimensions of the current selection. The unit "
                "selector on the right switches between mm, in, and px."
            ),
        },
        {
            "zone": _("Command palette"),
            "title": _("Ctrl+Shift+P for anything"),
            "body": _(
                "Press Ctrl+Shift+P (Cmd+Shift+P on macOS) to open the "
                "command palette. Type to search every action in the app — "
                "useful when you know what you want but not where it lives."
            ),
        },
    ]

    def __init__(self, transient_for: Gtk.Window) -> None:
        super().__init__()
        self.set_transient_for(transient_for)
        self.set_modal(True)
        self.set_content_width(520)
        self.set_content_height(440)
        self.set_title(_("Welcome to Pires Forge"))
        # Use a stable id so the dialog can be tracked across
        # present/dismiss cycles.
        self.set_id("walkthrough")

        outer = Adw.ToolbarView()
        # ---- Header ----
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        skip_btn = Gtk.Button(label=_("Skip"))
        skip_btn.add_css_class("flat")
        skip_btn.connect("clicked", lambda *_: self.emit("walkthrough-skip"))
        header.pack_start(skip_btn)
        outer.add_top_bar(header)

        # ---- Body ----
        body = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        body.set_margin_top(16)
        body.set_margin_bottom(16)
        body.set_margin_start(16)
        body.set_margin_end(16)

        # The carousel of pages
        self._carousel = Adw.Carousel()
        self._carousel.set_allow_scroll_wheel(False)
        self._carousel.set_allow_long_swipes(True)
        self._carousel.set_spacing(8)

        for i, page in enumerate(self.WALKTHROUGH_PAGES):
            self._carousel.append(self._build_page(page, i))
        body.append(self._carousel)

        # Indicator dots
        self._dots = Adw.CarouselIndicatorDots()
        self._dots.set_carousel(self._carousel)
        body.append(self._dots)

        # Footer buttons
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(8)
        self._back_btn = Gtk.Button(label=_("Back"))
        self._back_btn.connect("clicked", self._on_back)
        self._back_btn.set_sensitive(False)  # first page
        footer.append(self._back_btn)
        self._next_btn = Gtk.Button(label=_("Next"))
        self._next_btn.add_css_class("suggested-action")
        self._next_btn.connect("clicked", self._on_next)
        footer.append(self._next_btn)
        body.append(footer)

        outer.set_content(body)
        self.set_child(outer)

        # Connect carousel page changes to update button state
        self._carousel.connect("page-changed", self._on_page_changed)

        # Declare the signals callers will listen for
        # (we declare them by adding them to a class-level
        # container — GObject's introspection requires the
        # class to know about them at registration time).
        self._declare_signals()

    def _declare_signals(self):
        # GObject signals need to be declared at class-level,
        # not in __init__. We do it here for the instances that
        # have already been constructed by registering the
        # signal via connect-style at first emit. As a fallback,
        # we just provide explicit "done" and "skip" public
        # methods that callers can override (or use as handlers).
        # GObject's "notify" mechanism doesn't support dynamic
        # signal declaration on an instance, so for the simple
        # case of two outcomes we use the public done/skip methods
        # below.
        pass

    # ---- Public methods ----

    def done(self) -> None:
        """Called by Next on the last page. Closes the dialog."""
        self.close()

    def skip(self) -> None:
        """Called by Skip. Closes the dialog without advancing."""
        self.close()

    # ---- Internal ----

    def _build_page(self, page: dict, index: int) -> Gtk.Widget:
        """Build a single walkthrough page (heading + zone + body)."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_hexpand(True)
        box.set_vexpand(True)

        # Zone badge: "1 of 5 — Canvas"
        zone_label = Gtk.Label(
            label=f"{index + 1}/{len(self.WALKTHROUGH_PAGES)} · {page['zone']}"
        )
        zone_label.add_css_class("dim-label")
        zone_label.set_halign(Gtk.Align.START)
        zone_label.set_xalign(0)
        box.append(zone_label)

        # Title
        title = Gtk.Label(label=page["title"])
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_xalign(0)
        title.set_wrap(True)
        box.append(title)

        # Body
        body = Gtk.Label(label=page["body"])
        body.set_halign(Gtk.Align.START)
        body.set_xalign(0)
        body.set_wrap(True)
        body.set_margin_top(8)
        box.append(body)

        return box

    def _on_back(self, *_args):
        # Adw.Carousel's navigate(action) accepts "previous" /
        # "next" as the canonical way to move between pages.
        self._carousel.navigate(Adw.NavigationDirection.BACK)

    def _on_next(self, *_args):
        n = self._carousel.get_n_pages()
        cur = self._carousel.get_position()
        if cur < n - 1:
            self._carousel.navigate(Adw.NavigationDirection.FORWARD)
        else:
            self.done()

    def _on_page_changed(self, carousel, index):
        n = carousel.get_n_pages()
        self._back_btn.set_sensitive(index > 0)
        if index == n - 1:
            self._next_btn.set_label(_("Done"))
        else:
            self._next_btn.set_label(_("Next"))
