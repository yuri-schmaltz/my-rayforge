import logging
from gettext import gettext as _

from blinker import Signal
from gi.repository import Gdk, Gtk

from .action_registry import action_registry
from .icons import get_icon
from .shared.a11y import propagate_tooltip_to_accessible_label
from .shared.splitbutton import SplitMenuButton
from .shared.undo_button import RedoButton, UndoButton
from .sim3d import initialized as canvas3d_initialized

logger = logging.getLogger(__name__)


class MainToolbar(Gtk.Box):
    """
    The main application toolbar.
    Connects its buttons to Gio.Actions for centralized control.
    """

    def __init__(self, **kwargs):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6, **kwargs
        )
        self.add_css_class("main-toolbar")
        # Signals for View-State controls (not app actions)
        self.machine_warning_clicked = Signal()
        # Emitted when the user toggles the toolbar mode (essential
        # vs all). The MainWindow connects this to persist the
        # choice to config.
        self.toolbar_mode_changed = Signal()

        self.set_margin_bottom(2)
        self.set_margin_top(2)
        self.set_margin_start(12)
        self.set_margin_end(12)

        # File related buttons (open, save, import, export)
        self.open_button = Gtk.Button(child=get_icon("open-symbolic"))
        self.open_button.set_tooltip_text(_("Open Project"))
        self.open_button.set_action_name("win.open")
        self.append(self.open_button)

        self.save_button = Gtk.Button(child=get_icon("save-symbolic"))
        self.save_button.set_tooltip_text(_("Save"))
        self.save_button.set_action_name("win.save")
        self.append(self.save_button)

        self.save_as_button = Gtk.Button(child=get_icon("save-as-symbolic"))
        self.save_as_button.set_tooltip_text(_("Save As..."))
        self.save_as_button.set_action_name("win.save-as")
        self.append(self.save_as_button)

        open_button = Gtk.Button(child=get_icon("download-symbolic"))
        open_button.set_tooltip_text(_("Import image"))
        open_button.set_action_name("win.import")
        self.append(open_button)

        self.export_button = Gtk.Button(child=get_icon("export-symbolic"))
        self.export_button.set_tooltip_text(_("Generate G-code"))
        self.export_button.set_action_name("win.export")
        self.append(self.export_button)

        # Undo/Redo Buttons
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        self.undo_button = UndoButton()
        self.undo_button.set_tooltip_text(_("Undo"))
        self.undo_button.set_action_name("win.undo")
        self.append(self.undo_button)

        self.redo_button = RedoButton()
        self.redo_button.set_tooltip_text(_("Redo"))
        self.redo_button.set_action_name("win.redo")
        self.append(self.redo_button)

        # Add a button to open the 3D preview window.
        view_3d_button = Gtk.ToggleButton(child=get_icon("3d-symbolic"))
        view_3d_button.set_action_name("win.show_3d_view")
        view_3d_button.set_sensitive(canvas3d_initialized)
        if not canvas3d_initialized:
            view_3d_button.set_tooltip_text(
                _("3D view disabled (missing dependencies like PyOpenGL)")
            )
        else:
            view_3d_button.set_tooltip_text(_("Show 3D Preview"))
        self.append(view_3d_button)

        self.recalculate_button = Gtk.Button(
            child=get_icon("refresh-symbolic"),
        )
        self.recalculate_button.set_tooltip_text(
            _("Recalculate (Shift+Click to force)")
        )
        self.recalculate_button.connect(
            "clicked", self._on_recalculate_clicked
        )
        recalc_gesture = Gtk.GestureClick.new()
        recalc_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        recalc_gesture.connect("pressed", self._on_recalculate_pressed)
        self.recalculate_button.add_controller(recalc_gesture)
        self.append(self.recalculate_button)
        self._recalculate_force = False

        # Add a button to toggle the control panel.
        self.bottom_panel_button = Gtk.ToggleButton()
        self.bottom_panel_button.set_child(get_icon("jog-symbolic"))
        self.bottom_panel_button.set_active(False)
        self.bottom_panel_button.set_tooltip_text(_("Toggle bottom panel"))
        self.bottom_panel_button.set_action_name("win.toggle_bottom_panel")
        self.append(self.bottom_panel_button)

        # Arrangement buttons (Consolidated Dropdown)
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        self.arrange_actions = self._build_arrange_actions()
        self.arrange_menu_button = SplitMenuButton(
            actions=self.arrange_actions
        )
        self.arrange_menu_button.set_tooltip_text(_("Arrange selection"))
        self.append(self.arrange_menu_button)

        # Tabbing buttons (Split Dropdown)
        tab_actions = [
            (
                _("Add Equidistant Tabs…"),
                "tabs-equidistant-symbolic",
                "win.add-tabs-equidistant",
            ),
            (
                _("Add Cardinal Tabs (N,S,E,W)"),
                "compass-symbolic",
                "win.add-tabs-cardinal",
            ),
        ]
        self.tab_menu_button = SplitMenuButton(actions=tab_actions)
        self.tab_menu_button.set_tooltip_text(_("Add Tabs to selection"))
        self.append(self.tab_menu_button)

        # Control buttons: home, send, pause, stop
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        self.home_button = Gtk.Button(child=get_icon("home-symbolic"))
        self.home_button.set_tooltip_text(_("Home the machine"))
        self.home_button.set_action_name("win.machine-home")
        self.append(self.home_button)

        self.frame_button = Gtk.Button(child=get_icon("frame-symbolic"))
        self.frame_button.set_tooltip_text(
            _("Cycle laser head around the occupied area")
        )
        self.frame_button.set_action_name("win.machine-frame")
        self.append(self.frame_button)

        self.send_button = Gtk.Button(child=get_icon("send-symbolic"))
        self.send_button.set_tooltip_text(_("Send to machine"))
        self.send_button.set_action_name("win.machine-send")
        self.append(self.send_button)

        self.hold_on_icon = get_icon("play-arrow-symbolic")
        self.hold_off_icon = get_icon("pause-symbolic")
        self.hold_button = Gtk.ToggleButton()
        self.hold_button.set_child(self.hold_off_icon)
        self.hold_button.set_tooltip_text(_("Pause machine"))
        self.hold_button.set_action_name("win.machine-hold")
        self.append(self.hold_button)

        self.cancel_button = Gtk.Button(child=get_icon("stop-symbolic"))
        self.cancel_button.set_tooltip_text(_("Cancel running job"))
        self.cancel_button.set_action_name("win.machine-cancel")
        self.append(self.cancel_button)

        self.clear_alarm_button = Gtk.Button(
            child=get_icon("clear-alarm-symbolic")
        )
        self.clear_alarm_button.set_tooltip_text(
            _("Clear machine alarm (unlock)")
        )
        self.clear_alarm_button.set_action_name("win.machine-clear-alarm")
        self.append(self.clear_alarm_button)

        self.focus_on_icon = get_icon("laser-on-symbolic")
        self.focus_off_icon = get_icon("laser-off-symbolic")
        self.focus_button = Gtk.ToggleButton()
        self.focus_button.set_child(self.focus_on_icon)
        self.focus_button.set_tooltip_text(_("Toggle focus laser"))
        self.focus_button.set_action_name("win.toggle-focus")
        self.focus_button.connect("toggled", self._on_focus_toggled)
        self.append(self.focus_button)

        # Add clickable warning for misconfigured machine
        self.machine_warning_box = Gtk.Box(spacing=6)
        self.machine_warning_box.set_margin_end(12)
        warning_icon = get_icon("warning-symbolic")
        self.warning_label = Gtk.Label(label=_("Machine not fully configured"))
        self.warning_label.add_css_class("warning-label")
        self.machine_warning_box.append(warning_icon)
        self.machine_warning_box.append(self.warning_label)
        self.machine_warning_box.set_tooltip_text(
            _("Machine driver is missing required settings. Click to edit.")
        )
        self.machine_warning_box.set_visible(False)
        warning_click = Gtk.GestureClick.new()
        warning_click.connect(
            "pressed", lambda *_: self.machine_warning_clicked.send(self)
        )
        self.machine_warning_box.add_controller(warning_click)
        self.append(self.machine_warning_box)

        # Toolbar mode toggle: "Essential" hides advanced buttons to
        # reduce cognitive load on first-time users. "All" reveals
        # the full set for power users. The state is persisted to
        # config (added in wave 8, see config.toolbar_mode).
        # Default is "essential" — the user clicks the "..." button
        # to see more. This is the Blender-style progressive
        # disclosure, but kept lightweight (no workspace tabs).
        toolbar_sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(toolbar_sep)

        self._essential_buttons = []
        self._advanced_buttons = []
        self._classify_buttons()

        self.toolbar_mode_button = Gtk.ToggleButton()
        self.toolbar_mode_button.set_child(get_icon("view-more-symbolic"))
        self.toolbar_mode_button.set_tooltip_text(
            _("Show all toolbar buttons (advanced)")
        )
        self.toolbar_mode_button.connect(
            "toggled", self._on_toolbar_mode_toggled
        )
        self.append(self.toolbar_mode_button)

        # Connect to action registry changes for dynamic toolbar updates
        action_registry.changed.connect(self._on_action_registry_changed)

        # Accessibility: icon-only buttons (which make up most of the
        # toolbar) have a tooltip but no visible text. GTK doesn't
        # automatically copy the tooltip to the AT-SPI accessible
        # label, so screen readers announce them as 'button' with no
        # name. Walk every descendant and propagate the tooltip into
        # the accessible label. No-op for widgets that have no
        # tooltip set.
        self._apply_accessible_labels_recursive(self)

    def _classify_buttons(self):
        """Tag each visible toolbar widget as essential or advanced.

        The essential set covers the everyday "open file, change
        something, send to machine" flow. The advanced set is the
        everything-else (3D preview, arrange sub-tools, home
        individually, focus laser, machine alarm handling).

        The classification is keyed on the `widget_name` attribute
        we set in __init__ — keeping the names as a constant list
        here makes the policy readable in one place.
        """
        # Essential: file ops + undo/redo + recalculate + frame + send.
        # Reasoning: a user who just wants "open, edit, cut" needs
        # exactly these. Anything else is power-user territory.
        essential = (
            "open_button",
            "save_button",
            "save_as_button",
            "undo_button",
            "redo_button",
            "recalculate_button",
            "frame_button",
            "send_button",
        )
        for name in essential:
            widget = getattr(self, name, None)
            if widget is not None:
                self._essential_buttons.append(widget)

        # Advanced: the rest of the visible buttons + dropdowns.
        # 3D preview, import (file dialog), export, bottom panel toggle,
        # arrange/tabs split menus, home, hold, cancel, clear-alarm,
        # focus, machine-warning.
        # We don't have stable names for all the local-var widgets
        # (e.g. `view_3d_button`, `bottom_panel_button`,
        # `arrange_menu_button`, `tab_menu_button`, `hold_button`,
        # `cancel_button`, `clear_alarm_button`, `focus_button`),
        # so we just collect *all* Gtk.Button/ToggleButton/SplitMenuButton
        # children that aren't in the essential list.
        for child in self._iter_buttons():
            if child not in self._essential_buttons and isinstance(
                child,
                (
                    Gtk.Button,
                    Gtk.ToggleButton,
                ),
            ):
                # Skip the toolbar_mode_button itself and the
                # machine_warning_box (special-purpose, not a tool).
                if child is getattr(self, "toolbar_mode_button", None):
                    continue
                if child.get_parent() is getattr(
                    self, "machine_warning_box", None
                ):
                    continue
                self._advanced_buttons.append(child)

    def _iter_buttons(self):
        """Yield every direct child widget of the toolbar Box."""
        child = self.get_first_child()
        while child is not None:
            yield child
            child = child.get_next_sibling()

    def _on_toolbar_mode_toggled(self, toggle_button):
        """Show or hide the advanced buttons based on the toggle state.

        When the user activates the toggle, every widget in
        _advanced_buttons becomes visible. When they deactivate it,
        those widgets hide and the toolbar is reduced to the
        essential set + the toggle itself.
        """
        show_all = toggle_button.get_active()
        for widget in self._advanced_buttons:
            widget.set_visible(show_all)
        toggle_button.set_tooltip_text(
            _("Hide advanced toolbar buttons")
            if show_all
            else _("Show all toolbar buttons (advanced)")
        )
        # Persist the choice. The MainWindow owns config and is
        # the one that knows when to write it; we just emit a
        # signal that the caller can connect to.
        self.toolbar_mode_changed.send(self, show_all=show_all)

    def apply_toolbar_mode(self, show_all: bool):
        """Public API: set the toolbar to 'essential' or 'all' mode.

        Called by the MainWindow when config.toolbar_mode changes
        (initial load or after a settings change). Keeps the
        toggle's state in sync so the UI is consistent.
        """
        if getattr(self, "toolbar_mode_button", None) is None:
            return
        # set_active will trigger _on_toolbar_mode_toggled, so we
        # need to suppress recursion on the initial call.
        if self.toolbar_mode_button.get_active() == show_all:
            return
        self.toolbar_mode_button.set_active(show_all)

    def _apply_accessible_labels_recursive(self, widget):
        """Set accessible label from tooltip for every descendant."""
        propagate_tooltip_to_accessible_label(widget)
        child = widget.get_first_child()
        while child is not None:
            self._apply_accessible_labels_recursive(child)
            child = child.get_next_sibling()

    def _on_recalculate_pressed(self, gesture, n_press, x, y):
        self._recalculate_force = bool(
            gesture.get_current_event_state() & Gdk.ModifierType.SHIFT_MASK
        )

    def _on_recalculate_clicked(self, button):
        force = self._recalculate_force
        self._recalculate_force = False
        action_name = "win.force-recalculate" if force else "win.recalculate"
        self.activate_action(action_name, None)

    def _build_arrange_actions(self):
        """Build the list of arrange actions including registered layouts."""
        arrange_actions = [
            (
                _("Center Horizontally"),
                "align-horizontal-center-symbolic",
                "win.align-h-center",
            ),
            (
                _("Center Vertically"),
                "align-vertical-center-symbolic",
                "win.align-v-center",
            ),
            (_("Align Left"), "align-left-symbolic", "win.align-left"),
            (_("Align Right"), "align-right-symbolic", "win.align-right"),
            (_("Align Top"), "align-top-symbolic", "win.align-top"),
            (_("Align Bottom"), "align-bottom-symbolic", "win.align-bottom"),
            (
                _("Spread Horizontally"),
                "distribute-horizontal-symbolic",
                "win.spread-h",
            ),
            (
                _("Spread Vertically"),
                "distribute-vertical-symbolic",
                "win.spread-v",
            ),
            (
                _("Flip Horizontal"),
                "flip-horizontal-symbolic",
                "win.flip-horizontal",
            ),
            (
                _("Flip Vertical"),
                "flip-vertical-symbolic",
                "win.flip-vertical",
            ),
        ]
        for info in action_registry.get_toolbar_items("arrange"):
            if info.label:
                icon = info.icon_name or "auto-layout-symbolic"
                arrange_actions.append(
                    (
                        info.label,
                        icon,
                        f"win.{info.action_name}",
                    )
                )
        return arrange_actions

    def _on_action_registry_changed(self, sender):
        """Handle action registry changes by refreshing arrange menu."""
        self.arrange_actions = self._build_arrange_actions()
        self.arrange_menu_button.update_actions(self.arrange_actions)

    def _on_focus_toggled(self, button: Gtk.ToggleButton):
        """Callback to update the focus icon when the button's
        state changes for any reason (user click or action state change)."""
        if button.get_active():
            button.set_child(self.focus_off_icon)
        else:
            button.set_child(self.focus_on_icon)

    def set_machine_warning(
        self, error_title: str, error_code: int, error_description: str
    ):
        """
        Update the machine warning label with title, code and description.
        """
        self.warning_label.set_label(f"{error_title} ({error_code})")
        self.machine_warning_box.set_tooltip_text(error_description)
