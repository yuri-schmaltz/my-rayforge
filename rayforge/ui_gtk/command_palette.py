"""Command palette (Ctrl+Shift+P) for the main window.

A modal overlay that lets the user fuzzy-search every action
available in the app — the VS Code / Sublime / Blender pattern.
Pressing Enter activates the highlighted action.

The palette is the single discovery surface for features the
user might not know exist. It complements the menu, the
toolbar, and the right-pane: anything in any of those is also
searchable here.

Implementation:
- The list of actions is built once at startup by walking the
  Gtk.Application's Gio.ActionMap and collecting the user-
  visible ones. We filter by name prefix ('win.' is the
  window-scope) and skip actions with no enabled property.
- The search is a simple substring match (case-insensitive)
  ranked by: prefix match > word match > substring match.
  Fuzzy matching is intentionally not used to keep the
  results predictable — a user typing 'theme' should see
  Theme entries, not random matches.
- Activation: when the user selects an entry and presses
  Enter (or double-clicks), we activate the action via
  Gtk.Widget.activate_action().
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from ..shared.util.localized import _  # noqa: E402

logger = logging.getLogger(__name__)


class _PaletteEntry(GObject.Object):
    """One row in the command palette list.

    Wraps a Gio.Action (so we can activate it) plus a
    human-readable label and a search-key (lowercase label +
    action name, used for substring matching).
    """

    def __init__(self, action: Gio.Action, label: str, detail: str = ""):
        super().__init__()
        self._action = action
        self._label = label
        self._detail = detail
        self._search_key = (label + " " + action.get_name() + " " + detail).lower()

    def matches(self, query: str) -> bool:
        if not query:
            return True
        q = query.lower()
        return q in self._search_key

    def score(self, query: str) -> int:
        """Return a ranking score; higher is better. 0 means no match."""
        if not query:
            return 1  # everything matches an empty query
        q = query.lower()
        if self._label.lower().startswith(q):
            return 100
        # Word-boundary match (e.g. 'theme' matches 'Switch theme')
        if any(word.startswith(q) for word in self._label.lower().split()):
            return 50
        if q in self._search_key:
            return 10
        return 0

    def activate(self) -> None:
        try:
            self._action.activate(None)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to activate %s: %s", self._action.get_name(), exc)

    # GObject properties for ListView binding
    @GObject.Property(type=str)
    def label(self) -> str:
        return self._label

    @GObject.Property(type=str)
    def detail(self) -> str:
        return self._detail


class CommandPalette(Gtk.Box):
    """Modal command palette, opened via Ctrl+Shift+P.

    Self-contained: hosts a search entry, a list of matching
    entries, and a key handler that activates the highlighted
    entry on Enter.
    """

    def __init__(self, on_close: Callable[[], None]) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL, spacing=6
        )
        self.add_css_class("forge-command-palette")
        self.set_size_request(560, -1)
        self._on_close = on_close
        self._all_entries: List[_PaletteEntry] = []

        # Search entry
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(_("Type a command or search…"))
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._on_search_changed)
        self._search.connect("stop-search", lambda *_: self._on_close())
        # Accessibility: the search entry is the primary
        # input. Give it a clear a11y label so the screen
        # reader announces it before the user types.
        from ..shared.util.a11y import set_a11y_label

        set_a11y_label(
            self._search,
            _("Command search"),
            description=_(
                "Type a command name, action, or setting to "
                "find it. Arrow keys navigate, Enter activates."
            ),
            role=Gtk.AccessibleRole.SEARCH_BOX,
        )
        self.append(self._search)

        # ListView of matching entries
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(280)
        scrolled.set_max_content_height(420)
        set_a11y_label(
            scrolled,
            _("Search results"),
            description=_(
                "List of commands matching the search. The "
                "first result is auto-selected."
            ),
            role=Gtk.AccessibleRole.LIST,
        )
        scrolled.set_propagate_natural_height(True)

        self._model = Gio.ListStore.new(_PaletteEntry)
        self._selection = Gtk.SingleSelection.new(self._model)
        factory = Gtk.SignalListItemFactory()
        factory.connect("bind", self._on_factory_bind)
        self._listview = Gtk.ListView.new(self._selection, factory)
        self._listview.set_show_separators(True)
        self._listview.set_single_click_activate(False)
        self._listview.connect("list-activated", self._on_list_activated)
        scrolled.set_child(self._listview)
        self.append(scrolled)

        # Footer hint
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer.set_margin_start(4)
        footer.set_margin_end(4)
        footer.set_margin_bottom(2)
        hint = Gtk.Label(
            label=_("↑↓ to navigate · Enter to run · Esc to close")
        )
        hint.add_css_class("forge-command-palette-hint")
        hint.set_hexpand(True)
        hint.set_halign(Gtk.Align.END)
        footer.append(hint)
        self.append(footer)

        # Key controller for arrow navigation + Enter to activate
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    # ---- Public API ----

    def populate_from_action_map(self, action_map: Gio.ActionMap) -> None:
        """Walk the action map and build the searchable list.

        Skips stateful actions whose .get_state() returns None
        (those are toggles whose state we'd have to read) — for
        now we only show stateless (simple) actions plus
        stateful ones whose enabled state we can read safely.
        """
        self._all_entries.clear()
        for action_name in sorted(action_map.list_actions()):
            if action_name.startswith("app."):
                # Skip app-level actions (quit, about, preferences)
                # to keep the palette focused on the workspace.
                continue
            action = action_map.lookup_action(action_name)
            if action is None:
                continue
            # Skip the palette action itself to avoid recursion
            if action_name in ("palette", "open-palette"):
                continue
            label = action_name.replace("-", " ").replace(".", " · ").title()
            self._all_entries.append(_PaletteEntry(action, label))
        # Update the visible list with the current query (likely empty)
        self._on_search_changed(self._search)

    def focus_search(self) -> None:
        """Grab focus on the search entry so the user can start typing."""
        self._search.grab_focus()

    # ---- Internal ----

    def _on_search_changed(self, entry):
        query = entry.get_text()
        # Compute scores and keep only matches, sorted desc.
        scored = [(e.score(query), e) for e in self._all_entries]
        scored = [(s, e) for s, e in scored if s > 0]
        scored.sort(key=lambda x: -x[0])
        self._model.remove_all()
        for _, e in scored[:50]:  # cap visible list to 50
            self._model.append(e)
        # Auto-select the first row so Enter activates it.
        if self._model.get_n_items() > 0:
            self._selection.set_selected(0)

    def _on_factory_bind(self, factory, item):
        """Render one _PaletteEntry as a label row."""
        label = item.get_child()
        if label is None:
            label = Gtk.Label()
            label.set_xalign(0)
            item.set_child(label)
        entry = item.get_item()
        label.set_text(entry.props.label)
        label.add_css_class("forge-command-palette-row")

    def _on_list_activated(self, list_view, position):
        if 0 <= position < self._model.get_n_items():
            entry = self._model.get_item(position)
            if entry is not None:
                entry.activate()
                self._on_close()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        # Sentinel for "no selection" — Gtk.INVALID_LIST_POSITION
        # exists on 4.10+, use a numeric fallback for older builds.
        invalid = getattr(Gtk, "INVALID_LIST_POSITION", 4294967295)
        if keyval == Gdk.KEY_Escape:
            self._on_close()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            pos = self._selection.get_selected()
            if pos != invalid and pos >= 0:
                entry = self._model.get_item(pos)
                if entry is not None:
                    entry.activate()
                    self._on_close()
                    return True
        if keyval == Gdk.KEY_Down:
            n = self._model.get_n_items()
            if n > 0:
                cur = self._selection.get_selected()
                if cur == invalid or cur < 0:
                    new = 0
                else:
                    new = (cur + 1) % n
                self._selection.set_selected(new)
                return True
        if keyval == Gdk.KEY_Up:
            n = self._model.get_n_items()
            if n > 0:
                cur = self._selection.get_selected()
                if cur == invalid or cur < 0:
                    new = n - 1
                elif cur == 0:
                    new = n - 1
                else:
                    new = cur - 1
                self._selection.set_selected(new)
                return True
        return False
