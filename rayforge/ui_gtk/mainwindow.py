import asyncio
import logging
from concurrent.futures import Future
from gettext import gettext as _
from pathlib import Path
from typing import Callable, Coroutine, List, Optional, Tuple

from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from raygeo.ops.axis import Axis

from .. import __version__, const
from ..addon_mgr.update_cmd import UpdateCommand
from ..context import get_context
from ..core.asset_registry import asset_type_registry
from ..core.group import Group
from ..core.item import DocItem
from ..core.registration import call_registration_hooks
from ..core.step_registry import step_registry
from ..core.undo import Command, HistoryManager
from ..core.workpiece import WorkPiece
from ..doceditor.editor import DocEditor
from ..machine.cmd import MachineCmd
from ..machine.driver.driver import DeviceState, DeviceStatus
from ..machine.driver.dummy import NoDeviceDriver
from ..machine.models.machine import Machine
from ..machine.sanity import CheckMode, SanityChecker
from ..machine.transport import TransportStatus
from ..pipeline.artifact import JobArtifact
from ..pipeline.artifact.handle import BaseArtifactHandle
from ..pipeline.encoder.gcode import MachineCodeOpMap
from ..shared.tasker import task_mgr
from ..shared.util.time_format import format_hours_to_hm
from ..updater import AppUpdateChecker
from ..usage import get_usage_tracker
from .about import AboutDialog
from .action_registry import action_registry
from .actions import (
    SHORTCUTS,
    ActionManager,
    action_extension_registry,
)
from .canvas import CanvasElement
from .canvas2d.drag_drop_cmd import DragDropCmd
from .canvas2d.elements.stock import StockElement
from .canvas2d.surface import WorkSurface
from .debug_log_dialog import DebugLogDialog
from .doceditor import file_dialogs
from .doceditor.bottom_panel import BottomPanel
from .doceditor.import_handler import start_interactive_import
from .doceditor.item_properties import DocItemPropertiesWidget
from .doceditor.missing_features_dialog import MissingFeaturesDialog
from .doceditor.property_providers import register_builtin_providers
from .doceditor.workflow_view import WorkflowView
from .machine.machine_dropdown import MachineDropdown
from .machine.settings_dialog import MachineSettingsDialog
from .main_menu import MainMenu
from .project_cmd import ProjectCmd
from .settings.settings_dialog import SettingsWindow
from .shared.gtk import get_monitor_geometry
from .shared.playback_overlay import PlaybackOverlay
from .shared.progress_bar import ProgressBar
from .shared.sanity_check_dialog import SanityCheckDialog
from .shared.time_estimate_overlay import TimeEstimateOverlay
from .shared.usage_consent_dialog import UsageConsentDialog
from .shared.visibility_overlay import VisibilityOverlay
from .sim3d import Canvas3D
from .sim3d import initialized as canvas3d_initialized
from .sim3d.camera import ViewDirection
from .sim3d.viewport import ViewportConfig
from .toolbar import MainToolbar
from .view_mode_cmd import ViewModeCmd

logger = logging.getLogger(__name__)


def _resolve_forge_css_path():
    """Locate rayforge/resources/styles/forge.css, bundle-aware.

    Dev:    <repo>/rayforge/resources/styles/forge.css
    Bundle: <sys._MEIPASS>/rayforge/resources/styles/forge.css
    Returns the Path or None if not found.

    Thin wrapper over rayforge.shared.util.resources.resource_path
    so the bundle-aware resolution pattern lives in exactly one
    place (see also splash._resolve_splash_svg).
    """
    from ..shared.util.resources import resource_path

    return resource_path(
        "rayforge/resources/styles/forge.css", anchor_file=__file__
    )


# Module-level state: track whether the CssProvider for forge.css
# has been installed for the current display. CssProvider installs
# are display-global (they affect every widget on the GdkDisplay),
# so a second call from MainWindow.__init__ is a no-op.
_FORGE_CSS_INSTALLED = False


def install_forge_css_once():
    """Install the forge.css stylesheet for the current display.

    Idempotent: subsequent calls are a no-op. Safe to call from
    anywhere — App.do_activate calls it BEFORE showing the splash
    so the splash window inherits the .splash-window rule
    declared in forge.css, and MainWindow.__init__ calls it again
    as a defensive measure (which becomes a no-op on the second
    call).

    Without this, the splash shows for ~100-500ms with the
    compositor's default background, which on a light WM theme
    leaks white through the SVG's transparent corners.
    """
    global _FORGE_CSS_INSTALLED
    if _FORGE_CSS_INSTALLED:
        return
    display = Gdk.Display.get_default()
    if display is None:
        # No display (e.g. running headless under a test harness).
        # Nothing to install; the widgets will use Gtk defaults.
        return
    css_path = _resolve_forge_css_path()
    provider = Gtk.CssProvider()
    if css_path is not None:
        try:
            provider.load_from_path(str(css_path))
        except GLib.Error as exc:
            logger.warning(
                "Failed to load forge.css from %s: %s; "
                "falling back to no stylesheet",
                css_path,
                exc,
            )
    else:
        logger.warning(
            "forge.css not found at expected path; "
            "the main window will render with GTK defaults."
        )
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _FORGE_CSS_INSTALLED = True


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_css_class("forge-theme")
        self.set_title(const.APP_NAME)
        self._current_machine: Optional[Machine] = None  # For signal handling
        self._last_bottom_panel_height = 200
        self._saved_bottom_panel_visible = False
        self._old_doc = None  # Track previous document for signal reconnection
        self.canvas3d: Optional[Canvas3D] = None
        self._canvas3d_time_overlay: Optional[TimeEstimateOverlay] = None
        self._is_syncing_3d = False

        # The ToastOverlay will wrap the main content box
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        # Track active toasts so they can be cleared programmatically
        self._active_toasts: List[Adw.Toast] = []

        # The main content box is now the child of the ToastOverlay
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(vbox)
        # Expose as a public attribute so the
        # dockable_integration module can reparent
        # the coordinate_bar / bottom_panel widgets
        # when the user drops them in a new zone.
        self._dockable_top_vbox = vbox

        # Create the central document editor. This now owns the Doc and
        # Pipeline.
        context = get_context()
        self.doc_editor = DocEditor(task_mgr, context)
        context.addon_mgr.addon_state_changed.connect(
            self._on_addon_state_changed
        )
        self.machine_cmd = MachineCmd(self.doc_editor)
        self.machine_cmd.job_started.connect(self._on_job_started)

        # Instantiate and connect the UpdateCommand's notification signal
        self.update_cmd = UpdateCommand(task_mgr, context)
        self.update_cmd.notification_requested.connect(
            self._on_editor_notification
        )

        # Instantiate the app version update checker
        self.app_update_checker = AppUpdateChecker(task_mgr, context)
        self.app_update_checker.notification_requested.connect(
            self._on_editor_notification
        )

        # Instantiate UI-specific command handlers
        self.view_cmd = ViewModeCmd(self.doc_editor, self)
        self.project_cmd = ProjectCmd(self, self.doc_editor)

        geometry = get_monitor_geometry()
        if geometry:
            self.set_default_size(
                int(geometry.width * 0.8), int(geometry.height * 0.8)
            )
        else:
            self.set_default_size(1100, 800)

        # HeaderBar with left-aligned menu and centered title
        self.header_bar = Adw.HeaderBar()
        vbox.append(self.header_bar)

        # Create the menu model and the popover menubar
        self.menu_model = MainMenu()
        self.menubar = Gtk.PopoverMenuBar.new_from_model(self.menu_model)
        self.menubar.add_css_class("in-header-menubar")
        self.header_bar.pack_start(self.menubar)

        # Set up Recent Files manager
        self.recent_manager = Gtk.RecentManager.get_default()
        self.recent_manager.connect(
            "changed", self.project_cmd.update_recent_files_menu
        )
        self.project_cmd.update_recent_files_menu()

        # Create and set the centered title widget
        window_title = Adw.WindowTitle(
            title=self.get_title() or "", subtitle=__version__ or ""
        )
        self.header_bar.set_title_widget(window_title)

        # Add machine selector to the header bar (right side)
        self.machine_selector = MachineDropdown()
        self.header_bar.pack_end(self.machine_selector)

        # Right-panel toggle (workflow + item properties). The button
        # is an explicit affordance in addition to the Adw.Breakpoint
        # auto-hide: on wide windows the panel floats over the canvas
        # (default), on narrow windows the breakpoint hides it and
        # the user re-enables it from this button. The active state
        # stays in sync with the panel's visibility.
        from .icons import get_icon

        self._right_panel_toggle = Gtk.ToggleButton(
            child=get_icon("info-symbolic"),
            tooltip_text=_("Toggle right panel"),
            action_name="win.toggle-right-panel",
        )
        # Initialize active state from the saved config so the toggle
        # reflects reality after a restart.
        self._right_panel_toggle.set_active(
            get_context().config.right_panel_visible
        )
        self.header_bar.pack_end(self._right_panel_toggle)

        # Create a vertical paned for main content and bottom control panel
        self.vertical_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.vertical_paned.set_resize_start_child(True)
        self.vertical_paned.set_resize_end_child(False)
        self.vertical_paned.set_shrink_start_child(False)
        self.vertical_paned.set_shrink_end_child(False)
        # Alias for the dockable_integration module
        # (the reparenting functions look up
        # _dockable_vertical_paned by name)
        self._dockable_vertical_paned = self.vertical_paned

        self._status_overlay = Gtk.Overlay()
        self._status_overlay.set_child(self.vertical_paned)

        self._status_message_label = Gtk.Label(
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            margin_end=12,
            margin_bottom=6,
        )
        self._status_message_label.add_css_class("status-message-overlay")
        self._status_message_label.set_visible(False)
        self._status_overlay.add_overlay(self._status_message_label)

        vbox.append(self._status_overlay)

        # Coordinate bar: live X/Y/L/W/H readout with unit
        # selector. Sits between the header and the canvas so
        # the user always has the cursor position and selection
        # dimensions visible without needing to open any panel.
        from .coordinate_bar import CoordinateBar

        self.coordinate_bar = CoordinateBar()
        vbox.append(self.coordinate_bar)
        # Connect unit changes so the canvas can re-render
        # coordinates in the new unit.
        self.coordinate_bar.connect_unit_changed(self._on_unit_changed)
        # Initial unit comes from config.
        self._on_unit_changed_apply_initial()

        # Persistent status bar at the bottom of the window. Sits
        # below the bottom panel (which lives inside _status_overlay
        # / vertical_paned). The status bar gives the user a single
        # glanceable source of truth for mode, cursor, layer,
        # operation, and job progress.
        from .status_bar import StatusBar

        self.status_bar = StatusBar()
        vbox.append(self.status_bar)
        # First-interaction coach mark for the status bar.
        # A click anywhere on the bar (including the mode
        # badge) shows the popover pointing at the bar.
        status_click = Gtk.GestureClick()
        status_click.connect(
            "pressed",
            lambda *_: self.trigger_coach_mark(
                "status", self.status_bar
            ),
        )
        self.status_bar.add_controller(status_click)

        # Create a stack for switching between main view and addon pages
        self.main_stack = Gtk.Stack()
        self.main_stack.set_vexpand(True)
        self.main_stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_UP_DOWN
        )
        self.vertical_paned.set_start_child(self.main_stack)

        # Create a container for the main UI
        main_ui_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_stack.add_named(main_ui_box, "main")

        # Create and add the main toolbar.
        self.toolbar = MainToolbar()
        self._connect_toolbar_signals()
        main_ui_box.append(self.toolbar)

        # Create an overlay so the right panel can float above the canvas.
        self._canvas_overlay = Gtk.Overlay()
        self._canvas_overlay.set_vexpand(True)
        main_ui_box.append(self._canvas_overlay)

        # Apply styles — load the forge.css stylesheet from disk so
        # the source of truth lives next to other resources instead
        # of being stringified in a Python file. install_forge_css_once
        # is idempotent: App.do_activate already called it before
        # showing the splash, so this is a no-op the second time
        # around. Kept here as a defensive fallback for any code
        # path that constructs a MainWindow without going through
        # App.do_activate (tests, addons).
        install_forge_css_once()

        # Determine initial machine dimensions for canvases.
        context = get_context()
        config = context.config
        if config.machine:
            viewport = ViewportConfig.from_machine(config.machine)
        else:
            viewport = ViewportConfig.default()

        self.surface = WorkSurface(
            editor=self.doc_editor,
            parent_window=self,
            machine=config.machine,
            cam_visible=True,  # Will be set by action state
        )
        self.surface.set_hexpand(True)

        # Initialize drag-and-drop command for the surface
        self.drag_drop_cmd = DragDropCmd(self, self.surface)
        self.surface.drag_drop_cmd = self.drag_drop_cmd
        self.drag_drop_cmd.setup_drop_targets()

        # Set up action registry before registering actions
        action_registry.set_window(self)
        self.action_registry = action_registry

        # Let addons register action extension handlers before
        # ActionManager.register_actions() invokes setup handlers.
        call_registration_hooks(context.plugin_mgr, window_required=True)

        # Setup keyboard actions using the new ActionManager.
        self.action_manager = ActionManager(self)
        self.action_manager.register_actions()

        shortcut_controller = Gtk.ShortcutController()
        self.action_manager.register_shortcuts(shortcut_controller)
        self.add_controller(shortcut_controller)

        # Connect document signals
        doc = self.doc_editor.doc
        self._old_doc = doc  # Track initial document for signal reconnection
        self._initialize_document()
        doc.updated.connect(self.on_doc_changed)
        doc.descendant_added.connect(self.on_doc_changed)
        doc.descendant_removed.connect(self.on_doc_changed)
        doc.descendant_updated.connect(self.on_doc_changed)
        doc.active_layer_changed.connect(self._on_active_layer_changed)
        doc.history_manager.changed.connect(self.on_history_changed)

        # Connect editor signals
        self.doc_editor.notification_requested.connect(
            self._on_editor_notification
        )
        self.doc_editor.document_settled.connect(self._on_document_settled)
        self.doc_editor.saved_state_changed.connect(
            self.project_cmd.on_saved_state_changed
        )
        self.doc_editor.document_changed.connect(self._on_document_changed)

        # Create the view stack for 2D and 3D views
        self.view_stack = Gtk.Stack()
        self.view_stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        )
        self.view_stack.set_margin_start(12)
        self.view_stack.set_hexpand(True)

        # The view stack is the base child of the canvas overlay
        self._canvas_overlay.set_child(self.view_stack)

        # First-interaction coach mark for the canvas. A
        # gesture-click on the overlay fires on any click
        # inside the canvas; the first one shows the canvas
        # coach mark. We use the overlay (not the surface)
        # so the popover arrow points at the canvas as a
        # whole rather than a specific element.
        canvas_click = Gtk.GestureClick()
        canvas_click.connect(
            "pressed",
            lambda *_: self.trigger_coach_mark(
                "canvas", self._canvas_overlay
            ),
        )
        self._canvas_overlay.add_controller(canvas_click)

        # Wrap surface in an overlay to allow preview controls
        self.surface_overlay = Gtk.Overlay()
        self.surface_overlay.set_child(self.surface)
        self._surface_vis_overlay = VisibilityOverlay(
            show_workpiece=True,
            show_camera=bool(
                config.machine
                and any(c.enabled for c in config.machine.cameras)
            ),
            show_tabs=True,
            shortcuts=SHORTCUTS,
        )
        self._surface_vis_overlay.set_margin_end(424)
        self.surface_overlay.add_overlay(self._surface_vis_overlay)
        self._time_estimate_overlay = TimeEstimateOverlay()
        self.surface_overlay.add_overlay(self._time_estimate_overlay)
        self.view_stack.add_named(self.surface_overlay, "2d")

        # Add a click handler to unfocus when clicking the "dead space" of the
        # canvas area. This is the correct place for this handler, as it won't
        # interfere with clicks on the sidebar.
        canvas_click_gesture = Gtk.GestureClick.new()
        canvas_click_gesture.connect(
            "pressed", self._on_canvas_area_click_pressed
        )
        # self.surface_overlay.add_controller(canvas_click_gesture)

        if canvas3d_initialized:
            self._create_canvas3d(context, viewport)

        self._sync_view_toggle_actions()

        # Undo/Redo buttons are now connected to the doc via actions.
        self.toolbar.undo_button.set_history_manager(
            self.doc_editor.history_manager
        )
        self.toolbar.redo_button.set_history_manager(
            self.doc_editor.history_manager
        )

        # Create a right pane with tabs (Workflow | Properties)
        # instead of a single ScrolledWindow that stacked both
        # sections. The user previously had to scroll up and down
        # to switch between viewing the workflow steps and the
        # properties of the selected item; with tabs the same height
        # hosts two distinct contexts that the user clicks between.
        # (Wave 9 in the UI/UX wave — Inkscape/Krita pattern.)
        right_pane_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_pane_outer.set_size_request(400, -1)
        right_pane_outer.add_css_class("right-panel-overlay")
        right_pane_outer.set_halign(Gtk.Align.END)
        right_pane_outer.set_valign(Gtk.Align.START)

        # ViewSwitcher bar at the top, with the two tabs.
        right_pane_switcher = Adw.ViewSwitcher()
        right_pane_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        right_pane_switcher.set_margin_top(4)
        right_pane_switcher.set_margin_start(8)
        right_pane_switcher.set_margin_end(8)

        right_pane_stack = Adw.ViewStack()
        right_pane_stack.set_vexpand(True)
        right_pane_stack.set_hexpand(False)
        right_pane_switcher.set_stack(right_pane_stack)
        # Save on self so _on_selection_changed can auto-switch
        # to the Properties tab when the user selects an item.
        self._right_pane_stack = right_pane_stack

        # The ViewStack goes inside a ScrolledWindow so each page
        # can have its own scrollable content. We bind the switcher
        # to the stack via set_stack above.
        scrolled_workflow = Gtk.ScrolledWindow()
        scrolled_workflow.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        scrolled_workflow.set_vexpand(True)

        scrolled_props = Gtk.ScrolledWindow()
        scrolled_props.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        scrolled_props.set_vexpand(True)

        right_pane_stack.add_titled(
            scrolled_workflow, "workflow", _("Workflow")
        )
        right_pane_stack.add_titled(
            scrolled_props, "properties", _("Properties")
        )

        right_pane_outer.append(right_pane_switcher)
        right_pane_outer.append(right_pane_stack)

        # The outer widget still goes into the canvas overlay (so
        # it floats on the canvas), but the layout inside is now
        # a tabbed stack. The legacy _right_pane attribute points
        # to the outer box for any code that toggles its visibility.
        # (Note: set_propagate_natural_height is a ScrolledWindow
        # method, not a Box method — we removed the call because
        # the right_pane is a plain Gtk.Box, not a ScrolledWindow.
        # The natural-height behavior is handled by the inner
        # ScrolledWindows for each tab.)
        self._right_pane = right_pane_outer
        self._canvas_overlay.add_overlay(self._right_pane)

        # The WorkflowView will be updated when a layer is activated.
        initial_workflow = self.doc_editor.doc.active_layer.workflow
        assert initial_workflow, "Initial active layer must have a workflow"
        self.workflowview = WorkflowView(
            self.doc_editor,
            initial_workflow,
            step_factories=step_registry.get_factories(),
        )
        self.workflowview.set_margin_top(6)
        self.workflowview.set_margin_start(12)
        self.workflowview.set_margin_end(12)
        scrolled_workflow.set_child(self.workflowview)

        # Register built-in property providers before creating the widget
        register_builtin_providers()

        # Add the WorkpiecePropertiesWidget to the Properties tab
        self.item_props_widget = DocItemPropertiesWidget(
            editor=self.doc_editor
        )
        item_props_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.item_props_widget.set_margin_top(6)
        self.item_props_widget.set_margin_start(12)
        self.item_props_widget.set_margin_end(12)
        item_props_container.append(self.item_props_widget)

        self.item_revealer = Gtk.Revealer()
        self.item_revealer.set_child(item_props_container)
        self.item_revealer.set_reveal_child(False)
        self.item_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_UP
        )
        scrolled_props.set_child(self.item_revealer)

        # Connect signals for item selection and actions
        self.surface.selection_changed.connect(self._on_selection_changed)
        self.surface.elements_deleted.connect(self.on_elements_deleted)
        self.surface.cut_requested.connect(self.on_cut_requested)
        self.surface.copy_requested.connect(self.on_copy_requested)
        self.surface.paste_requested.connect(self.on_paste_requested)
        self.surface.duplicate_requested.connect(self.on_duplicate_requested)
        self.surface.transform_initiated.connect(
            self._on_surface_transform_initiated
        )
        self.surface.transform_end.connect(self._on_surface_transform_end)
        self.surface.work_zero_requested.connect(self._on_work_zero_requested)
        self.surface.click_to_zero_cancelled.connect(
            self._on_click_to_zero_cancelled
        )

        # Connect new signal from WorkSurface for edit item requests
        self.surface.edit_item_requested.connect(self._on_edit_item_requested)

        # Create the control panel
        config = get_context().config
        self.bottom_panel = BottomPanel(
            config.machine, self.doc_editor, self.machine_cmd
        )
        self.bottom_panel.set_size_request(-1, self._last_bottom_panel_height)
        self.bottom_panel.set_visible(True)
        self.vertical_paned.set_end_child(self.bottom_panel)

        self.bottom_panel.gcode_viewer.line_activated.connect(
            self._on_gcode_line_activated
        )

        # Connect edit item requests from the layers tab
        self.bottom_panel.edit_item_requested.connect(
            self._on_edit_item_requested
        )
        self.bottom_panel.select_items_requested.connect(
            self._on_select_items_requested
        )

        config = get_context().config
        if config.bottom_panel:
            self.bottom_panel.from_dict(config.bottom_panel)

        self.bottom_panel.tab_changed.connect(self._on_bottom_tab_changed)
        self.bottom_panel.layout_changed.connect(
            self._on_bottom_layout_changed
        )
        # First-interaction coach mark for the bottom panel.
        # Gesture-click on the widget itself; the popover
        # points at the panel and explains "console / gcode".
        bottom_click = Gtk.GestureClick()
        bottom_click.connect(
            "pressed",
            lambda *_: self.trigger_coach_mark(
                "bottom", self.bottom_panel
            ),
        )
        self.bottom_panel.add_controller(bottom_click)

        self.bottom_panel.click_to_zero_mode_changed.connect(
            self._on_click_to_zero_mode_changed
        )

        self.bottom_panel.asset_browser.add_asset_requested.connect(
            self.on_add_asset_requested
        )
        self.bottom_panel.asset_browser.asset_activated.connect(
            self.on_asset_activated
        )

        self.bottom_panel.set_get_bounds_callback(self._get_selection_bounds)

        self.view_stack.connect(
            "notify::visible-child-name", self._on_view_stack_changed
        )

        # Connect to position signal to remember user's chosen height
        self.vertical_paned.connect(
            "notify::position", self._on_vertical_pane_position_changed
        )

        # Create and add the progress bar at the bottom of vbox
        self.progress_bar = ProgressBar(task_mgr)
        gesture = Gtk.GestureClick()
        gesture.connect(
            "pressed", lambda *args: self.on_status_bar_clicked(None)
        )
        self.progress_bar.add_controller(gesture)
        vbox.append(self.progress_bar)

        self.doc_editor.pipeline.job_time_updated.connect(
            self._on_job_time_updated
        )

        # Set up config signals.
        config.changed.connect(self.on_config_changed)
        task_mgr.tasks_updated.connect(self.on_running_tasks_changed)
        self.needs_homing = (
            config.machine.home_on_start if config.machine else False
        )

        # Set initial state
        self.on_config_changed(None)

        # Wire the dockable panels UI. This is a
        # best-effort setup: if any of the optional
        # dependencies (workspace actions, submenu
        # insertion) fail, the drag-and-drop itself
        # still works for the surfaces that exist.
        try:
            from .dockable_integration import setup_dockable

            setup_dockable(self)
        except Exception as e:  # pragma: no cover
            logger.debug("Dockable UI setup failed: %s", e)

        # Try to load the saved workspace. If the
        # 'default' workspace doesn't exist, create it.
        # This is a PoC: only the default workspace is
        # actually applied to the UI. Future commits
        # will add a 'View > Workspace' submenu that
        # switches between named workspaces.
        try:
            from .workspace import (
                list_workspaces,
                _make_default_workspace,
            )
            from pathlib import Path
            from ..config import config_dir

            ws_list = list_workspaces(Path(config_dir))
            # Future: let the user pick via menu; for now
            # we just ensure the default exists.
            if "default" not in ws_list:
                from .workspace import save_workspace

                save_workspace(
                    Path(config_dir), _make_default_workspace()
                )
        except Exception as e:  # pragma: no cover
            logger.debug("Workspace load skipped: %s", e)

        # Local-only usage tracker. Records action fires +
        # mode changes for the Insights dialog. Independent
        # of the Umami tracker (which is opt-in cloud
        # telemetry); this is always-on but never leaves
        # the process.
        from ..util.local_tracker import get_local_tracker

        self._local_tracker = get_local_tracker()

        # Coach-mark controller. Lazily constructs one
        # CoachMark popover per zone and shows them in
        # response to first-interaction triggers. Popovers
        # are not created until the first interaction so the
        # initial paint isn't delayed.
        from .coach_marks import CoachMark, COACH_MARKS

        self._coach_marks: dict = {}
        self._coach_mark_pending: Optional[str] = None
        # Suppresses the very first user click on a zone if
        # the walkthrough is still on screen (avoids the
        # popover fighting the walkthrough for attention).
        self._walkthrough_active: bool = False

        # Panel manager — coordinates right + bottom panel
        # visibility across the three layout presets
        # (default / compact / expanded) and per-panel overrides.
        # The actual widgets are bound after they're constructed
        # below; this just creates the manager.
        from .panel_manager import PanelManager

        self.panel_manager = PanelManager(
            right_panel=self._right_pane,
            bottom_panel=self.bottom_panel,
        )

        # First-run walkthrough. Shown only if config.walkthrough_seen
        # is False. The dialog persists a "seen" flag to config on
        # any of: skip, done, or close, so it only runs once.
        self._walkthrough: Optional[Adw.Dialog] = None
        if not get_context().config.walkthrough_seen:
            GLib.idle_add(self._show_walkthrough)

        # Command palette (Ctrl+Shift+P). Built lazily on first
        # open so the action map is fully populated by then.
        self._command_palette_window: Optional[Gtk.Window] = None
        self._install_palette_shortcut()
        self._install_insights_shortcut()

        # Apply saved visibility state
        self._apply_saved_visibility_state()

        # Notify addons that main window is ready
        context.plugin_mgr.hook.main_window_ready(main_window=self)

        # Trigger startup tasks when window is shown
        self.connect("map", self._trigger_startup_tasks)

        # Accessibility: respect the system 'reduce motion' preference.
        # Installs a one-time listener that re-applies the motion
        # preference across the widget tree whenever the system
        # setting flips. Initial pass runs at install time so
        # existing stacks/revealers are correct before the first
        # transition fires.
        from .shared.a11y import install_motion_preference_listener

        install_motion_preference_listener(self)

        # Responsive layout: when the window drops below 900px wide,
        # the floating right panel (workflow + item properties) starts
        # occluding the canvas. Auto-hide it in that case and show a
        # one-time toast so the user knows where the toggle is. On
        # wide windows we leave the panel state alone — the user's
        # saved preference is respected.
        self._narrow_mode = False
        try:
            narrow_bp = Adw.Breakpoint.new(
                Adw.BreakpointCondition.parse("max-width: 900px")
            )
            narrow_bp.connect("apply", self._on_narrow_breakpoint_apply)
            narrow_bp.connect("unapply", self._on_narrow_breakpoint_unapply)
            self.add_breakpoint(narrow_bp)
        except Exception as exc:
            logger.warning(
                "Could not install narrow-mode breakpoint: %s", exc
            )

    def _on_narrow_breakpoint_apply(self, _bp):
        """Window dropped below 900px: hide the floating right panel.

        We remember the prior visible state so unapply can restore it
        if the user didn't explicitly toggle the panel in the
        meantime. This is best-effort: if the user clicks the toggle
        in narrow mode and then resizes back to wide, the new state
        wins.
        """
        self._narrow_mode = True
        if not self._right_pane.get_visible():
            return  # Already hidden; nothing to do.
        self._right_pane_was_visible_before_narrow = True
        self._right_pane.set_visible(False)
        self._right_panel_toggle.set_active(False)
        get_context().config.set_right_panel_visible(False)
        self._add_toast(
            Adw.Toast.new(
                _("Right panel hidden on small window — "
                  "use the info button in the header to show it.")
            )
        )

    def _on_narrow_breakpoint_unapply(self, _bp):
        """Window grew past 900px: restore prior right-panel state."""
        self._narrow_mode = False
        if getattr(self, "_right_pane_was_visible_before_narrow", False):
            self._right_pane_was_visible_before_narrow = False
            self._right_pane.set_visible(True)
            self._right_panel_toggle.set_active(True)
            get_context().config.set_right_panel_visible(True)

    def _trigger_startup_tasks(self, widget):
        """
        Runs once when the window is first shown.
        """
        # Disconnect self to ensure it only runs once
        self.disconnect_by_func(self._trigger_startup_tasks)

        # Initialize usage tracking based on saved consent
        config = get_context().config
        if config.has_consented_tracking:
            get_usage_tracker().set_enabled(True)
            get_usage_tracker().track_page_view("/view/2d", "2D View")
        elif config.has_declined_tracking:
            pass  # Explicitly do nothing, respecting the user's choice
        else:
            dialog = UsageConsentDialog(self)
            dialog.present()

        # Trigger the non-blocking check for addon updates
        self.update_cmd.check_for_updates_on_startup()

        # Trigger the non-blocking check for app version updates
        self.app_update_checker.check_on_startup()

    def _on_click_to_zero_mode_changed(self, sender, *, active: bool):
        """Handle click-to-zero mode toggle from control panel."""
        self.surface.set_click_to_zero_mode(active)

    def _on_work_zero_requested(self, sender, *, x: float, y: float):
        """Handle work zero request from canvas click."""
        config = get_context().config
        if not config.machine:
            return

        async def set_zero_func(ctx):
            if config.machine:
                await config.machine.set_work_origin(x, y, 0.0)

        task_mgr.add_coroutine(set_zero_func)
        self.bottom_panel.set_click_to_zero_mode(False)

    def _on_click_to_zero_cancelled(self, sender):
        """Handle click-to-zero mode cancellation."""
        self.bottom_panel.set_click_to_zero_mode(False)

    def _get_selection_bounds(
        self,
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Get the bounding box of selected items or workarea bounds.

        Returns:
            A tuple (min_x, min_y, max_x, max_y) in world coordinates,
            or None if there is no machine configured.
        """
        selected_elements = self.surface.get_selected_elements()

        if selected_elements:
            workpieces = []
            for elem in selected_elements:
                if isinstance(elem.data, WorkPiece):
                    workpieces.append(elem.data)
                elif isinstance(elem.data, Group):
                    workpieces.extend(elem.data.get_descendants(WorkPiece))

            bboxes = []
            for wp in workpieces:
                bbox = wp.get_geometry_world_bbox()
                if bbox is not None:
                    bboxes.append(bbox)

            if bboxes:
                min_x = min(b[0] for b in bboxes)
                min_y = min(b[1] for b in bboxes)
                max_x = max(b[2] for b in bboxes)
                max_y = max(b[3] for b in bboxes)
                return (min_x, min_y, max_x, max_y)

        config = get_context().config
        machine = config.machine
        if not machine:
            return None

        space = machine.get_coordinate_space()
        workarea_origin_machine = space.get_workarea_origin_in_machine()
        min_x, min_y = space.machine_point_to_world(*workarea_origin_machine)
        workarea_w, workarea_h = space.workarea_size
        max_x = min_x + workarea_w
        max_y = min_y + workarea_h

        return (min_x, min_y, max_x, max_y)

    def _apply_saved_visibility_state(self):
        """
        Applies the saved visibility state for control panel.
        This should be called after actions are registered.
        """
        config = get_context().config

        bottom_panel_action = self.action_manager.get_action(
            "toggle_bottom_panel"
        )
        if (
            bottom_panel_action
            and config.bottom_panel
            and config.bottom_panel.get("visible")
        ):
            bottom_panel_action.change_state(GLib.Variant.new_boolean(True))

    def add_stack_page(self, name: str, widget: Gtk.Widget):
        """Add a page to the main stack.

        This is a public API for addons to add their own pages to the
        main stack (e.g., editor views).

        Args:
            name: The name/identifier for the page
            widget: The widget to add as a page
        """
        self.main_stack.add_named(widget, name)

    def show_stack_page(self, name: str):
        """Switch to a named page in the main stack.

        Args:
            name: The name of the page to show
        """
        self.main_stack.set_visible_child_name(name)

    def remove_stack_page(self, name: str):
        """Remove a page from the main stack.

        Args:
            name: The name of the page to remove
        """
        child = self.main_stack.get_child_by_name(name)
        if child:
            self.main_stack.remove(child)

    def get_stack_page(self, name: str) -> Optional[Gtk.Widget]:
        """Get a page widget from the main stack by name.

        Args:
            name: The name of the page to get

        Returns:
            The widget if found, None otherwise
        """
        return self.main_stack.get_child_by_name(name)

    def open_modal_page(self, name: str):
        """Open a modal page, hiding auxiliary panels.

        This is used for full-screen editor modes (like the sketcher) that
        should hide panels like the control panel.

        Args:
            name: The name of the modal page to show
        """
        self._saved_bottom_panel_visible = self.bottom_panel.get_visible()
        if self._saved_bottom_panel_visible:
            self.bottom_panel.set_visible(False)
        self.main_stack.set_visible_child_name(name)

    def close_modal_page(self):
        """Close the current modal page and return to main view.

        Restores the visibility of auxiliary panels that were hidden.
        """
        if self._saved_bottom_panel_visible:
            self.bottom_panel.set_visible(True)
        self.main_stack.set_visible_child_name("main")

    def on_add_child(self, sender):
        """Handler for adding a new stock item."""
        self.doc_editor.stock.add_stock()

    def on_add_asset_requested(self, sender, *, type_name: str):
        """Handler for add asset requests, dispatches via action lookup."""
        asset_cls = asset_type_registry.get(type_name)
        if asset_cls and asset_cls.add_action:
            action = self.action_manager.get_action(asset_cls.add_action)
            if action:
                action.activate(None)

    def on_asset_activated(self, sender, *, asset):
        """Handler for asset activation, dispatches via action lookup."""
        asset_cls = type(asset)
        if asset_cls.activate_action:
            action = self.action_manager.get_action(asset_cls.activate_action)
            if action:
                action.activate(GLib.Variant.new_string(asset.uid))

    def _on_edit_item_requested(self, sender, *, item, action_name: str):
        """Signal handler for edit item requests from the surface."""
        action = self.action_manager.get_action(action_name)
        if action:
            action.activate(GLib.Variant.new_string(item.uid))

    def _on_select_items_requested(self, sender, *, items, **kwargs):
        self.surface.select_items(items)

    def load_project(self, file_path: Path):
        """Public method to load a project from a given path."""
        self.project_cmd.load_project(file_path)

    def _update_macros_menu(self, *args):
        """Rebuilds the dynamic 'Macros' menu."""
        config = get_context().config
        if not config.machine:
            self.menu_model.update_macros_menu([])
            return

        macros = sorted(
            config.machine.macros.values(), key=lambda m: m.name.lower()
        )
        enabled_macros = [m for m in macros if m.enabled]
        self.menu_model.update_macros_menu(enabled_macros)

    def on_execute_macro(self, action: Gio.SimpleAction, param: GLib.Variant):
        """Handler for the 'execute-macro' action."""
        config = get_context().config
        if not config.machine:
            return
        macro_uid = param.get_string()
        logger.info(f"Executing macro: {macro_uid}")
        self.machine_cmd.execute_macro_by_uid(config.machine, macro_uid)

    def _on_job_started(self, sender):
        logger.debug("Job started")
        self.machine_selector.update_eta(None)
        self._update_actions_and_ui()

    def _on_addon_state_changed(self, sender, addon_name):
        """Handle addon enable/disable to refresh action handlers."""
        action_extension_registry.invoke_setup_handlers(self.action_manager)
        self.action_manager.update_action_states()

    def _on_job_progress_updated(self, metrics: dict):
        """Callback for when job progress is updated."""
        eta_seconds = metrics.get("eta_seconds")
        self.machine_selector.update_eta(eta_seconds)

    def _on_job_finished(self, sender):
        """Handles the completion of a machine job."""
        logger.debug("Job finished")
        self.machine_selector.update_eta(None)

    def _on_job_future_done(self, future: Future):
        """Callback for when the job submission task completes or fails."""
        try:
            # Check for exceptions during job assembly or submission.
            future.result()
        except Exception as e:
            logger.error(f"Job submission failed: {e}", exc_info=True)
            # If the submission failed, the driver's 'job_finished' signal
            # will never fire, so we must stop the live view here to prevent
            # the UI from getting stuck.
            self.machine_selector.update_eta(None)

        # Ensure UI is updated (e.g. Cancel button disabled, others enabled)
        self._update_actions_and_ui()

    def _on_bottom_tab_changed(self, sender, *, name: str):
        if name == "gcode":
            self.refresh_previews()
        self._save_bottom_panel()

    def _on_bottom_layout_changed(self, sender):
        self._save_bottom_panel()

    def _save_bottom_panel(self):
        get_context().config.set_bottom_panel(self.bottom_panel.to_dict())

    def _on_gcode_line_activated(self, sender, *, line_number: int):
        """
        Handles the user activating a line in the G-code previewer.
        Syncs the highlight and the 3D playback slider.
        """
        # 1. Update the visual highlight to match the cursor, no scroll.
        self.bottom_panel.gcode_viewer.highlight_line(
            line_number, use_align=False
        )

        # 2. If 3D playback is active, sync the slider.
        op_map = self.bottom_panel.gcode_viewer.op_map
        if op_map and line_number in op_map.machine_code_to_op:
            op_index = op_map.machine_code_to_op[line_number]
            self._is_syncing_3d = True
            self._canvas3d_playback.set_playback_position(op_index)
            if self.canvas3d:
                self.canvas3d.queue_render()
            self._is_syncing_3d = False

    def _on_3d_playback_step_changed(self, sender, *, ops_index: int):
        """
        Handles the 3D playback slider changing. Syncs the G-code viewer
        highlight to the corresponding line.
        """
        if self._is_syncing_3d:
            return
        self.bottom_panel.gcode_viewer.highlight_op(ops_index)

    def _on_vertical_pane_position_changed(self, paned, param):
        position = paned.get_position()
        full_height = paned.get_height()
        panel_height = full_height - position
        if panel_height > 1:
            self._last_bottom_panel_height = panel_height

    def _on_surface_transform_initiated(self, sender):
        pass

    def _on_view_stack_changed(self, stack: Gtk.Stack, param):
        """Handles logic when switching between 2D and 3D views."""
        child_name = stack.get_visible_child_name()
        if child_name == "3d":
            self._update_3d_view_content()
        self._update_actions_and_ui()

    def _update_3d_view_content(self):
        """
        Updates the 3D canvas by delegating to its internal update method.
        This is now a fast, non-blocking operation.
        """
        if not self.canvas3d:
            return
        if self.canvas3d.has_stale_job():
            self.refresh_previews()
        self.canvas3d.update_scene_from_doc()

    def _update_gcode_preview(
        self, gcode_string: Optional[str], op_map: Optional[MachineCodeOpMap]
    ):
        """Updates the G-code preview panel from a pre-generated string."""
        if gcode_string is None:
            self.bottom_panel.gcode_viewer.clear()
            return

        self.bottom_panel.gcode_viewer.set_gcode(gcode_string)
        if op_map:
            self.bottom_panel.gcode_viewer.set_op_map(op_map)

    def on_show_3d_view(
        self, action: Gio.SimpleAction, value: Optional[GLib.Variant]
    ):
        """Delegates the view switching logic to the command module."""
        self.view_cmd.toggle_3d_view(action, value)

    def on_show_workpieces_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        self.surface.set_workpieces_visible(is_visible)
        action.set_state(value)
        config = get_context().config
        config.canvas_view.show_workpieces = is_visible
        config.changed.send(config)

    def on_toggle_camera_view_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        self.surface.set_camera_image_visibility(is_visible)
        action.set_state(value)
        config = get_context().config
        config.canvas_view.show_camera = is_visible
        config.changed.send(config)

    def on_toggle_travel_view_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        self.surface.set_show_travel_moves(is_visible)
        if self.canvas3d is not None:
            self.canvas3d.set_show_travel_moves(is_visible)
        action.set_state(value)
        config = get_context().config
        config.canvas_view.show_travel_lines = is_visible
        config.changed.send(config)

    def on_show_nogo_zones_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        self.surface.set_show_nogo_zones(is_visible)
        if self.canvas3d is not None:
            self.canvas3d.set_show_nogo_zones(is_visible)
        action.set_state(value)
        config = get_context().config
        config.canvas_view.show_nogo_zones = is_visible
        config.changed.send(config)

    def on_show_models_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        if self.canvas3d is not None:
            self.canvas3d.set_show_models(is_visible)
        action.set_state(value)
        config = get_context().config
        config.canvas_view.show_models = is_visible
        config.changed.send(config)

    def on_show_grid_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        if self.canvas3d is not None:
            self.canvas3d.set_show_grid(is_visible)
        action.set_state(value)
        config = get_context().config
        config.canvas_view.show_grid = is_visible
        config.changed.send(config)

    def on_view_top(self, action, param):
        """Action handler to set the 3D view to top-down."""
        self.view_cmd.set_view(ViewDirection.TOP, self.canvas3d)

    def on_view_front(self, action, param):
        """Action handler to set the 3D view to front."""
        self.view_cmd.set_view(ViewDirection.FRONT, self.canvas3d)

    def on_view_right(self, action, param):
        """Action handler to set the 3D view to right."""
        self.view_cmd.set_view(ViewDirection.RIGHT, self.canvas3d)

    def on_view_left(self, action, param):
        """Action handler to set the 3D view to left."""
        self.view_cmd.set_view(ViewDirection.LEFT, self.canvas3d)

    def on_view_back(self, action, param):
        """Action handler to set the 3D view to back."""
        self.view_cmd.set_view(ViewDirection.BACK, self.canvas3d)

    def on_view_iso(self, action, param):
        """Action handler to set the 3D view to isometric."""
        self.view_cmd.set_view(ViewDirection.ISO, self.canvas3d)

    def on_view_perspective_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        """Handles state changes for the perspective view action."""
        self.view_cmd.toggle_perspective(self.canvas3d, action, value)

    def _initialize_document(self):
        """
        Adds required initial state to a new document, such as default
        steps to workpiece layers.
        """
        self.doc_editor.step.initialize_default_steps()

    def _sync_view_toggle_actions(self):
        """
        Re-triggers each persisted view toggle action so that both the
        canvas surfaces and the overlay buttons reflect the persisted
        config values at startup.
        """
        am = self.action_manager
        cv = get_context().config.canvas_view

        am.get_action("show_workpieces").set_state(
            GLib.Variant.new_boolean(not cv.show_workpieces)
        )
        self.on_show_workpieces_state_change(
            am.get_action("show_workpieces"),
            GLib.Variant.new_boolean(cv.show_workpieces),
        )

        am.get_action("toggle_camera_view").set_state(
            GLib.Variant.new_boolean(not cv.show_camera)
        )
        self.on_toggle_camera_view_state_change(
            am.get_action("toggle_camera_view"),
            GLib.Variant.new_boolean(cv.show_camera),
        )

        am.get_action("toggle_travel_view").set_state(
            GLib.Variant.new_boolean(not cv.show_travel_lines)
        )
        self.on_toggle_travel_view_state_change(
            am.get_action("toggle_travel_view"),
            GLib.Variant.new_boolean(cv.show_travel_lines),
        )

        am.get_action("show_nogo_zones").set_state(
            GLib.Variant.new_boolean(not cv.show_nogo_zones)
        )
        self.on_show_nogo_zones_state_change(
            am.get_action("show_nogo_zones"),
            GLib.Variant.new_boolean(cv.show_nogo_zones),
        )

        am.get_action("show_models").set_state(
            GLib.Variant.new_boolean(not cv.show_models)
        )
        self.on_show_models_state_change(
            am.get_action("show_models"),
            GLib.Variant.new_boolean(cv.show_models),
        )

        am.get_action("show_grid").set_state(
            GLib.Variant.new_boolean(not cv.show_grid)
        )
        self.on_show_grid_state_change(
            am.get_action("show_grid"),
            GLib.Variant.new_boolean(cv.show_grid),
        )

        am.get_action("show_tabs").set_state(
            GLib.Variant.new_boolean(not cv.show_tabs)
        )
        am.on_show_tabs_state_change(
            am.get_action("show_tabs"),
            GLib.Variant.new_boolean(cv.show_tabs),
        )

        am.get_action("view_toggle_perspective").set_state(
            GLib.Variant.new_boolean(not cv.perspective_mode)
        )
        self.on_view_perspective_state_change(
            am.get_action("view_toggle_perspective"),
            GLib.Variant.new_boolean(cv.perspective_mode),
        )

    def _connect_toolbar_signals(self):
        """Connects signals from the MainToolbar to their handlers.
        Most buttons are connected via Gio.Actions. Only view-state toggles
        and special widgets are connected here.
        """
        self.toolbar.machine_warning_clicked.connect(
            self.on_machine_warning_clicked
        )
        self.toolbar.toolbar_mode_changed.connect(
            self.on_toolbar_mode_changed
        )
        # First-interaction coach mark for the toolbar. A
        # gesture-click on the toolbar widget fires on any
        # toolbar button press; the coach mark shows the
        # first time only. We use the toolbar widget itself
        # as the popover parent so the arrow points at the
        # toolbar regardless of which button was clicked.
        toolbar_click = Gtk.GestureClick()
        toolbar_click.connect(
            "pressed", lambda *_: self.trigger_coach_mark(
                "toolbar", self.toolbar
            )
        )
        self.toolbar.add_controller(toolbar_click)
        self.machine_selector.machine_selected.connect(
            self.on_machine_selected_by_selector
        )

    def on_toolbar_mode_changed(self, sender, **kwargs):
        """Persist the toolbar mode when the user toggles the '...'
        button. Mode is 'all' (every button visible) or 'essential'
        (curated subset). Stored in config.toolbar_mode."""
        show_all = kwargs.get("show_all", False)
        get_context().config.set_toolbar_mode("all" if show_all else "essential")

    def on_panel_layout_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        """Apply a layout preset chosen from the View > Layout submenu.

        The action is stateful (string variant), so the menu
        shows a radio checkmark next to the current preset. When
        the user picks a new preset, we:
          1. Update config.panel_layout
          2. Clear any per-panel overrides (since the preset is
             now the source of truth)
          3. Re-apply the layout (so the panels move immediately,
             even if the user has only ever seen the menu via the
             keyboard shortcut)
        """
        layout = value.get_string()
        config = get_context().config
        # Clear overrides; the preset is now authoritative.
        if config.panel_overrides:
            config.panel_overrides = {}
        config.set_panel_layout(layout)
        action.set_state(value)
        self.apply_panel_layout()

    def _show_insights(self) -> None:
        """Open the InsightsDialog (Help > Insights, Ctrl+Shift+I).

        Lazy-built on first open. Re-uses the same instance
        on subsequent opens; the dialog refreshes its stats
        from the local tracker on every open.
        """
        from .insights_panel import InsightsDialog

        if (
            not hasattr(self, "_insights_dialog")
            or self._insights_dialog is None
        ):
            self._insights_dialog = InsightsDialog(
                transient_for=self, tracker=self._local_tracker
            )
        self._insights_dialog.present()

    def _replay_coach_marks(self, *args) -> None:
        """Reset the coach-mark seen flags so all 6 popovers
        can re-show on the next interaction. Wired from the
        Help > Replay Coach Marks menu item."""
        get_context().config.reset_coach_marks()

    def _show_tour(self, *args) -> None:
        """Re-show the first-run walkthrough. Wired from the
        Help > Show Tour menu item."""
        # Reset the seen flag so the walkthrough logic
        # decides to show. The dialog itself is built and
        # presented via the same _show_walkthrough code
        # path used on first launch.
        get_context().config.set_walkthrough_seen(False)
        # Drop any existing dialog so a fresh one builds.
        self._walkthrough = None
        GLib.idle_add(self._show_walkthrough)

    def on_zero_here_clicked(self, action, param):
        """Handler for 'zero-here' action."""
        config = get_context().config
        if not config.machine:
            return

        # 'param' is likely "all" string from the action setup
        axes_to_zero = Axis.X | Axis.Y | Axis.Z

        async def zero_func(ctx):
            # Explicitly check again to satisfy type checker
            if config.machine:
                await config.machine.set_work_origin_here(axes_to_zero)

        # Launch async zeroing
        task_mgr.add_coroutine(zero_func)

    def _on_canvas_area_click_pressed(self, gesture, n_press, x, y):
        """
        Handler for clicks on the canvas overlay area (the 'dead space').
        It unfocuses any other widget and gives focus to the surface for
        keyboard shortcuts.
        """
        logger.debug("Clicked on canvas area dead space, focusing surface.")
        self.surface.grab_focus()

    def on_machine_selected_by_selector(self, sender, *, machine: Machine):
        """
        Handles the 'machine_selected' signal from the MachineSelector widget,
        delegating the logic to the MachineManager.
        """
        context = get_context()
        context.machine_mgr.set_active_machine(machine)

    def _on_machine_status_changed(self, machine: Machine, state: DeviceState):
        """Called when the active machine's state changes."""
        config = get_context().config
        if self.needs_homing and config.machine and config.machine.driver:
            if state.status == DeviceStatus.IDLE:
                self.needs_homing = False
                driver = config.machine.driver
                task_mgr.add_coroutine(lambda ctx: driver.home())
        self._update_actions_and_ui()

    def _on_connection_status_changed(
        self,
        machine: Machine,
        status: TransportStatus,
        message: Optional[str] = None,
    ):
        """Called when the active machine's connection status changes."""
        if (
            status == TransportStatus.CONNECTED
            and machine.clear_alarm_on_connect
            and machine.device_state.status == DeviceStatus.ALARM
        ):
            logger.info(
                "Machine connected in ALARM state. Auto-clearing alarm."
            )
            self.machine_cmd.clear_alarm(machine)
        self._update_actions_and_ui()

    def _on_machine_hours_changed(self, sender, **kwargs):
        """
        Called when machine hours change. Checks for maintenance notifications.
        """
        due_counters = sender.consume_due_notifications()
        for counter in due_counters:
            msg = _(
                "Maintenance Alert: {name} has reached its limit "
                "({curr} / {limit})"
            ).format(
                name=counter.name,
                curr=format_hours_to_hm(counter.value),
                limit=format_hours_to_hm(counter.notify_at),
            )
            self._on_editor_notification(
                self,
                msg,
                persistent=True,
                action_label=_("View Counters"),
                action_callback=lambda: self._open_machine_hours_dialog(),
            )

    def _open_machine_hours_dialog(self):
        """Opens the machine settings dialog on the Hours page."""
        config = get_context().config
        if not config.machine:
            return
        dialog = MachineSettingsDialog(
            machine=config.machine,
            transient_for=self,
            initial_page="hours",
        )
        dialog.present()

    def on_history_changed(
        self, history_manager: HistoryManager, command: Command
    ):
        self._update_actions_and_ui()
        # After undo/redo, the document state may have changed in ways
        # that require a full UI sync (e.g., layer visibility).
        self.on_doc_changed(self.doc_editor.doc)
        self._update_macros_menu()

    def on_doc_changed(self, sender, **kwargs):
        # Synchronize UI elements that depend on the document model
        from ..util.tracing import get_tracer

        tracer = get_tracer()
        with tracer.span("mainwindow.surface_update_from_doc"):
            self.surface.update_from_doc()
        doc = self.doc_editor.doc
        if doc.active_layer and doc.active_layer.workflow:
            with tracer.span("mainwindow.workflowview_set_workflow"):
                self.workflowview.set_workflow(doc.active_layer.workflow)

        # Sync the selectability of stock items based on active layer
        self._sync_element_selectability()

        # Update button sensitivity and other state
        self._update_actions_and_ui()

    def _sync_element_selectability(self):
        """
        Updates the 'selectable' property of StockElements on the canvas
        based on which layer is currently active and their visibility.
        """
        # Find all StockElement instances currently on the canvas
        for element in self.surface.find_by_type(StockElement):
            # Stock items are only selectable when they are visible
            element.selectable = element.visible

    def _on_active_layer_changed(self, sender):
        """
        Handles activation of a new layer. Updates the workflow view and
        resets the paste counter.
        """
        logger.debug("Active layer changed, updating UI.")
        # Reset the paste counter to ensure the next paste is in-place.
        self.doc_editor.edit.reset_paste_counter()

        # Get the newly activated layer from the document
        activated_layer = self.doc_editor.doc.active_layer
        has_workflow = activated_layer.workflow is not None

        # Show/hide the workflow view based on the layer type
        self.workflowview.set_visible(has_workflow)

        if has_workflow:
            # For regular layers, update the workflow view with the
            # new workflow
            self.workflowview.set_workflow(activated_layer.workflow)

    def _on_document_changed(self, sender):
        """
        Handles when a new document is set on the DocEditor.
        Reconnects signal handlers to the new document and updates the UI.
        """
        new_doc = self.doc_editor.doc

        # Disconnect from old document signals if they were connected
        # We need to track the old doc to disconnect properly
        if self._old_doc is not None:
            self._old_doc.updated.disconnect(self.on_doc_changed)
            self._old_doc.descendant_added.disconnect(self.on_doc_changed)
            self._old_doc.descendant_removed.disconnect(self.on_doc_changed)
            self._old_doc.descendant_updated.disconnect(self.on_doc_changed)
            self._old_doc.active_layer_changed.disconnect(
                self._on_active_layer_changed
            )
            self._old_doc.history_manager.changed.disconnect(
                self.on_history_changed
            )

        # Connect to new document's signals
        new_doc.updated.connect(self.on_doc_changed)
        new_doc.descendant_added.connect(self.on_doc_changed)
        new_doc.descendant_removed.connect(self.on_doc_changed)
        new_doc.descendant_updated.connect(self.on_doc_changed)
        new_doc.active_layer_changed.connect(self._on_active_layer_changed)
        new_doc.history_manager.changed.connect(self.on_history_changed)

        # Store reference to current doc for future disconnection
        self._old_doc = new_doc

        # Update Undo/Redo buttons to listen to the new history manager
        self.toolbar.undo_button.set_history_manager(new_doc.history_manager)
        self.toolbar.redo_button.set_history_manager(new_doc.history_manager)

        # Update child views to point to the new document
        self.bottom_panel.set_doc(new_doc)

        # Initialize new document
        self._initialize_document()

        # Check for missing step types and show dialog if needed
        missing_types = new_doc.missing_step_types
        if missing_types:
            dialog = MissingFeaturesDialog(self, missing_types)
            dialog.present()

        # Trigger update to sync UI with new document
        self.on_doc_changed(new_doc)

        # Update the UI with the new document's content
        self.on_doc_changed(new_doc)

    def _on_editor_notification(
        self,
        sender,
        message: str,
        persistent: bool = False,
        action_label: Optional[str] = None,
        action_callback: Optional[Callable] = None,
    ):
        """
        Shows a toast when requested by the DocEditor.
        If 'persistent' is True, the toast will have a dismiss button and
        remain visible until closed.
        If 'action_label' and 'action_callback' are provided, a button
        will be added to the toast that triggers the callback.
        """
        toast = Adw.Toast.new(message)
        if persistent:
            toast.set_timeout(0)  # 0 = persistent
            toast.set_priority(Adw.ToastPriority.HIGH)

        if action_label and action_callback:
            toast.set_button_label(action_label)
            # Connecting directly to 'button-clicked' is the simplest way
            # to handle a callback without defining a GAction.
            toast.connect("button-clicked", lambda t: action_callback())

        self._add_toast(toast)

    def _add_toast(self, toast: Adw.Toast):
        """Helper to add a toast to the overlay and track it."""
        self._active_toasts.append(toast)
        # Connect to dismissed signal to clean up our reference
        toast.connect("dismissed", self._on_toast_dismissed)
        self.toast_overlay.add_toast(toast)

    def _on_toast_dismissed(self, toast):
        """Removes the toast from the tracking list when dismissed."""
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)

    def _on_surface_transform_end(self, sender, *args, **kwargs):
        """Clears all active toasts from the toast overlay."""
        logger.debug("Clearing all toasts from overlay.")

        # Iterate over a copy of the list because dismiss() triggers removal
        for toast in list(self._active_toasts):
            toast.dismiss()

    def _on_assembly_for_preview_finished(
        self,
        handle: Optional[BaseArtifactHandle],
        error: Optional[Exception],
    ):
        """Callback for when the job assembly for previews is complete."""
        if error:
            logger.error(
                "Failed to aggregate ops for preview",
                exc_info=error,
            )
            # Release handle on error if it exists
            if handle:
                self.doc_editor.pipeline.artifact_store.release(handle)
            handle = None

        # Schedule the UI update on the main thread, passing the handle.
        # The handle will be released in the main thread callback.
        GLib.idle_add(self._on_previews_ready, handle)

    def _on_previews_ready(self, handle: Optional[BaseArtifactHandle]):
        """
        Main-thread callback to distribute assembled Ops to all consumers.
        This method is responsible for releasing the artifact handle.
        """
        artifact_store = self.doc_editor.pipeline.artifact_store

        with artifact_store.checkout_handle(handle) as final_artifact:
            if final_artifact is None:
                if handle is None:
                    self._update_gcode_preview(None, None)
                    return

                logger.warning("Final artifact is None, not a JobArtifact")
                return

            assert isinstance(final_artifact, JobArtifact)

            # 2. Update G-code Preview
            is_gcode_visible = self.bottom_panel.is_item_visible("gcode")
            is_3d_visible = self.view_stack.get_visible_child_name() == "3d"

            if final_artifact and (is_gcode_visible or is_3d_visible):
                self._update_gcode_preview(
                    final_artifact.machine_code, final_artifact.op_map
                )
            else:
                self._update_gcode_preview(None, None)

        return GLib.SOURCE_REMOVE

    def refresh_previews(self):
        """
        Public method to trigger a refresh of all data previews, like the
        simulator and G-code view.
        """
        if get_context().exit_after_settle:
            return

        # The document_settled signal can fire BEFORE
        # self.bottom_panel is constructed (e.g. when the
        # doc editor adds its default 'Contorno' step
        # during __init__). Guard against AttributeError
        # so the signal doesn't crash startup. The
        # next signal fire (after construction
        # completes) will pick up the missing preview.
        if not hasattr(self, "bottom_panel"):
            return

        is_gcode_visible = self.bottom_panel.is_item_visible("gcode")
        is_3d_visible = self.view_stack.get_visible_child_name() == "3d"

        if not is_gcode_visible and not is_3d_visible:
            return

        config = get_context().config
        if not config.machine:
            # Pass None to clear previews if no machine is configured
            self._on_previews_ready(None)
            return

        # Try to use existing job artifact first
        existing_handle = self.doc_editor.pipeline.get_existing_job_handle()
        if existing_handle is not None:
            # Use existing artifact without regenerating
            self._on_previews_ready(existing_handle)
        else:
            # No existing artifact, trigger generation
            self.doc_editor.file.assemble_job_in_background(
                when_done=self._on_assembly_for_preview_finished
            )

    def _refresh_gcode_preview(self, sender=None, **kwargs):
        """Refresh G-code preview when machine settings change."""
        if self.bottom_panel.is_item_visible("gcode"):
            self.refresh_previews()

    def _create_canvas3d(self, context, viewport: ViewportConfig):
        """
        Creates a Canvas3D instance and adds it to the view stack.
        """
        self.canvas3d = Canvas3D(
            context,
            self.doc_editor,
            viewport=viewport,
        )
        self._canvas3d_overlay = Gtk.Overlay()
        self._canvas3d_overlay.set_child(self.canvas3d)
        self._canvas3d_vis_overlay = VisibilityOverlay(
            show_workpiece=False,
            show_models=True,
            show_grid=True,
            shortcuts=SHORTCUTS,
        )
        self._canvas3d_vis_overlay.set_margin_end(424)
        self._canvas3d_overlay.add_overlay(self._canvas3d_vis_overlay)
        self._canvas3d_playback = PlaybackOverlay()
        self.canvas3d.set_playback_overlay(self._canvas3d_playback)
        self._canvas3d_overlay.add_overlay(self._canvas3d_playback)
        self._canvas3d_playback.step_changed.connect(
            self._on_3d_playback_step_changed
        )
        self._canvas3d_time_overlay = TimeEstimateOverlay()
        self._canvas3d_overlay.add_overlay(self._canvas3d_time_overlay)
        self.view_stack.add_named(self._canvas3d_overlay, "3d")

    def _on_document_settled(self, sender):
        """
        Called when all background processing is complete. This is the main
        hook for refreshing previews that depend on the final assembled job.
        """
        self.refresh_previews()
        self._update_actions_and_ui()

    def _on_selection_changed(
        self,
        sender,
        elements: List[CanvasElement],
        active_element: Optional[CanvasElement],
    ):
        """Handles the 'selection-changed' signal from the WorkSurface."""
        # Get all selected DocItems (WorkPieces, Groups, etc.)
        selected_items = [
            elem.data for elem in elements if isinstance(elem.data, DocItem)
        ]

        # Get the primary active item from the signal payload
        active_item = (
            active_element.data
            if active_element and isinstance(active_element.data, DocItem)
            else None
        )

        # Reorder the list to put the active one first, if it exists
        if active_item and active_item in selected_items:
            selected_items.remove(active_item)
            selected_items.insert(0, active_item)

        self.item_props_widget.set_items(selected_items)
        self.item_revealer.set_reveal_child(bool(selected_items))
        # If the user selected something, auto-switch the right
        # pane to the Properties tab so they immediately see what
        # changed. If they de-selected, switch back to the Workflow
        # tab so the workflow is the default focus.
        if hasattr(self, "_right_pane_stack") and selected_items:
            try:
                self._right_pane_stack.set_visible_child_name("properties")
            except Exception:
                pass
            # First time the right pane shows properties
            # because the user clicked an object, show the
            # coach mark for the right pane. Lazy import
            # to avoid a circular dep at module load.
            if hasattr(self, "trigger_coach_mark"):
                self.trigger_coach_mark(
                    "right_pane", self._right_pane
                )
        elif hasattr(self, "_right_pane_stack"):
            try:
                self._right_pane_stack.set_visible_child_name("workflow")
            except Exception:
                pass
        self.bottom_panel.update_position_menu_sensitivity()
        self._update_actions_and_ui()
        selected_uids = {item.uid for item in selected_items}
        self.bottom_panel.update_layer_selection(selected_uids)

    def on_config_changed(self, sender, **kwargs):
        config = get_context().config
        machine_changed = config.machine is not self._current_machine

        if machine_changed:
            self._on_machine_signals_changed(config)
            self._update_canvas3d(config.machine)

        # Update the control panel to use the new machine
        self.bottom_panel.set_machine(config.machine, self.machine_cmd)

        # Update the main WorkSurface to use the new size
        self.surface.set_machine(config.machine)

        # Show/hide camera toggle based on whether machine has cameras
        has_cameras = bool(
            config.machine and any(c.enabled for c in config.machine.cameras)
        )
        self._surface_vis_overlay.set_camera_visible(has_cameras)

        self.surface.update_from_doc()
        self._update_macros_menu()

        # Check for any pending notifications from the new machine immediately
        if self._current_machine:
            self._on_machine_hours_changed(self._current_machine.machine_hours)

        self._update_actions_and_ui()
        self.apply_theme()
        self.apply_ui_density()
        self.apply_toolbar_mode()
        self.apply_panel_layout()
        self.apply_panel_layout()

    def _on_machine_signals_changed(self, config):
        # Disconnect from the previously active machine, if any
        if self._current_machine:
            self._current_machine.state_changed.disconnect(
                self._on_machine_status_changed
            )
            self._current_machine.connection_status_changed.disconnect(
                self._on_connection_status_changed
            )
            self._current_machine.job_finished.disconnect(
                self._on_job_finished
            )
            self._current_machine.changed.disconnect(self._update_macros_menu)
            self._current_machine.changed.disconnect(
                self._refresh_gcode_preview
            )
            self._current_machine.machine_hours.changed.disconnect(
                self._on_machine_hours_changed
            )
            # The controller signal is sourced directly from the controller
            # object rather than proxied through the machine. When the active
            # machine is removed, its controller is torn down before this
            # handler runs, so accessing ``controller`` would lazily fail
            # with a ValueError. Skip the disconnect in that case: the
            # controller (and its signal) is already gone, so there is
            # nothing left to detach.
            if self._current_machine.has_controller:
                self._current_machine.controller.laser_power_changed.disconnect(  # noqa: E501
                    self._on_laser_power_changed
                )

        self._current_machine = config.machine

        # Connect to the new active machine's signals
        if self._current_machine:
            self._current_machine.state_changed.connect(
                self._on_machine_status_changed
            )
            self._current_machine.connection_status_changed.connect(
                self._on_connection_status_changed
            )
            self._current_machine.job_finished.connect(self._on_job_finished)
            self._current_machine.changed.connect(self._update_macros_menu)
            self._current_machine.changed.connect(self._refresh_gcode_preview)
            self._current_machine.machine_hours.changed.connect(
                self._on_machine_hours_changed
            )
            self._current_machine.controller.laser_power_changed.connect(
                self._on_laser_power_changed
            )

    def _update_canvas3d(self, new_machine):
        if self.canvas3d is None:
            return
        if new_machine:
            viewport = ViewportConfig.from_machine(new_machine)
        else:
            viewport = ViewportConfig.default()
        self.canvas3d.set_machine(viewport=viewport)

    def apply_theme(self):
        """Reads the theme from config and applies it to the UI.

        Resolves config.theme ("system" | "light" | "dark") to the
        matching Adw.ColorScheme. The CSS in this module defines a
        @media (prefers-color-scheme: light) block that overrides
        the dark default tokens when the effective scheme is light,
        so component rules below stay valid for both themes.

        Unknown config values fall back to "system" (DEFAULT) rather
        than FORCE_DARK, which is safer for users with stale configs
        from a prior fork version that only had dark.
        """
        config = get_context().config
        theme = (config.theme or "system").lower()
        style_manager = Adw.StyleManager.get_default()
        scheme_map = {
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }
        # Anything that isn't explicitly "light" or "dark" — including
        # "system" and unknown values — uses DEFAULT (follows OS).
        style_manager.set_color_scheme(scheme_map.get(theme, Adw.ColorScheme.DEFAULT))

    def apply_ui_density(self):
        """Toggle the .forge-density-compact style class based on
        config.ui_density.

        The class is consumed by forge.css:
            .forge-theme.forge-density-compact .row { ... }
        so the right CSS rules activate without any per-widget
        Python changes. Unknown density values fall back to the
        'comfortable' class (which is a no-op since the default
        rule already assumes comfortable).
        """
        config = get_context().config
        density = (config.ui_density or "comfortable").lower()
        if density == "compact":
            self.add_css_class("forge-density-compact")
        else:
            self.remove_css_class("forge-density-compact")

    def apply_toolbar_mode(self):
        """Apply config.toolbar_mode to the MainToolbar.

        The toolbar exposes a Mode toggle (the "..." button) that
        switches between "essential" (a curated subset of buttons,
        default — designed for first-time users and quick
        navigation) and "all" (every button visible, for power
        users). The choice is persisted to config and applied
        here whenever config changes.
        """
        config = get_context().config
        mode = (config.toolbar_mode or "essential").lower()
        show_all = mode == "all"
        if hasattr(self, "toolbar"):
            self.toolbar.apply_toolbar_mode(show_all)

    def apply_panel_layout(self):
        """Apply config.panel_layout to the right and bottom panels.

        Three presets:
          - default  : right + bottom both visible
          - compact  : right visible, bottom hidden (canvas focus)
          - expanded : right hidden, bottom visible (logs focus)

        Per-panel overrides from config.panel_overrides are
        layered on top of the preset, so a user who likes the
        'default' preset but wants the right pane off doesn't
        have to switch to 'compact' and lose the bottom panel.
        """
        if not hasattr(self, "panel_manager"):
            return
        config = get_context().config
        layout = (config.panel_layout or "default").lower()
        # Apply the preset via the manager (sets both panels
        # to the preset's visibility).
        self.panel_manager.apply_layout(layout)
        # Then apply any overrides on top.
        for panel_name, visible in (config.panel_overrides or {}).items():
            if panel_name == "right":
                self.panel_manager.set_right_visible(visible)
            elif panel_name == "bottom":
                self.panel_manager.set_bottom_visible(visible)

    def _install_palette_shortcut(self):
        """Register Ctrl+Shift+P as the open-command-palette shortcut."""
        from .shared.keyboard import PRIMARY_ACCEL

        # Use the GTK shortcut controller. The primary accel is
        # Ctrl on Linux/Windows, Cmd on macOS. The key combo
        # matches VS Code / Sublime / Blender convention.
        shortcut_ctrl = Gtk.ShortcutController()
        shortcut_ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        trigger = Gtk.ShortcutTrigger.parse_string(
            f"{PRIMARY_ACCEL}shift+p"
        )
        if trigger is None:
            logger.warning("Could not parse Ctrl+Shift+P shortcut")
            return
        action = Gtk.ShortcutAction.parse_string("signal::open-palette")
        if action is None:
            logger.warning("Could not parse open-palette action")
            return
        shortcut = Gtk.Shortcut(trigger=trigger, action=action)
        shortcut_ctrl.add_shortcut(shortcut)
        self.add_controller(shortcut_ctrl)
        # Connect the signal: when the shortcut fires, open the palette.
        self.connect("open-palette", lambda *_: self._open_command_palette())

    def _install_insights_shortcut(self):
        """Register Ctrl+Shift+I as the open-insights shortcut.

        Mirrors the pattern in _install_palette_shortcut.
        The action is a signal 'open-insights' that this
        method also connects to."""
        from .shared.keyboard import PRIMARY_ACCEL

        shortcut_ctrl = Gtk.ShortcutController()
        shortcut_ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        trigger = Gtk.ShortcutTrigger.parse_string(
            f"{PRIMARY_ACCEL}shift+i"
        )
        if trigger is None:
            return
        action = Gtk.ShortcutAction.parse_string(
            "signal::open-insights"
        )
        if action is None:
            return
        shortcut = Gtk.Shortcut(trigger=trigger, action=action)
        shortcut_ctrl.add_shortcut(shortcut)
        self.add_controller(shortcut_ctrl)
        self.connect(
            "open-insights", lambda *_: self._show_insights()
        )

    def _open_command_palette(self):
        """Build (once) and present the command palette overlay."""
        from .command_palette import CommandPalette

        if self._command_palette_window is None:
            window = Gtk.Window()
            window.set_transient_for(self)
            window.set_modal(True)
            window.set_decorated(False)
            window.set_resizable(False)
            window.set_halign(Gtk.Align.CENTER)
            window.set_valign(Gtk.Align.START)
            window.set_margin_top(120)
            window.add_css_class("forge-command-palette-window")
            palette = CommandPalette(on_close=window.close)
            # Populate from the MainWindow's own action map.
            palette.populate_from_action_map(self)
            window.set_child(palette)
            self._command_palette_window = window
            # Keep a reference to the palette so it isn't GC'd.
            window._palette = palette
        self._command_palette_window.present()

    def _show_walkthrough(self) -> bool:
        """Build and present the first-run walkthrough dialog.

        Persists a 'seen' flag in config as soon as the dialog
        is constructed, so even an early crash (e.g. user force-
        quits during the dialog) doesn't make the dialog
        re-appear next launch. The flag is also re-set on
        Skip / Done, which is the canonical 'I read this' signal.
        """
        from .walkthrough import WalkthroughDialog

        if self._walkthrough is not None:
            self._walkthrough.present()
            return False
        dialog = WalkthroughDialog(transient_for=self)
        dialog.set_can_close(False)  # user must click Skip or Done
        # Persist 'seen' on any dismissal: Skip, Done, or
        # close-attempt. We attach a single handler that always
        # marks the flag, so even an unexpected close path
        # (Esc on the header, etc.) does the right thing.
        def _on_close(_dlg):
            get_context().config.set_walkthrough_seen(True)
            self._walkthrough = None
        dialog.connect("closed", _on_close)
        self._walkthrough = dialog
        dialog.present()
        return False  # remove the idle source

    def trigger_coach_mark(self, zone: str, parent: Gtk.Widget) -> None:
        """Show a coach mark for the given zone, attached to parent.

        The first time the user interacts with a given zone, this
        method is called with the zone name and the widget to
        attach the popover to. The popover is built lazily, shown
        via idle_add (so any click handler completes first), and
        dismissed either by the user clicking 'Got it' or by
        the 8s auto-timeout. The 'dismissed' signal updates
        config.coach_marks_seen so the popover never re-shows.

        If a coach mark is already pending or visible for a
        different zone, this call supersedes it (the most
        recent user interaction wins). This avoids the case
        where the user clicks the canvas, then the toolbar
        button, and both popovers fight for the same screen
        space.
        """
        from .coach_marks import CoachMark, COACH_MARKS

        config = get_context().config
        if zone in config.coach_marks_seen:
            return  # already shown for this zone
        if zone not in COACH_MARKS:
            logger.debug("Unknown coach mark zone '%s'", zone)
            return
        if self._walkthrough_active:
            return  # wait until the walkthrough is dismissed
        # Mark as pending; if a popover is already in the
        # pipeline for a different zone, the new one replaces
        # it. We don't want a long chain of idle callbacks.
        self._coach_mark_pending = zone
        GLib.idle_add(self._present_coach_mark, parent)

    def _present_coach_mark(self, parent: Gtk.Widget) -> bool:
        """Build (or reuse) and show the pending coach mark.

        Runs from GLib.idle_add so the user click that triggered
        it has finished. The popover is bound to 'parent' and
        positioned automatically. The 'dismissed' signal
        updates config and clears the cache.
        """
        zone = self._coach_mark_pending
        self._coach_mark_pending = None
        if zone is None or self._walkthrough_active:
            return False
        config = get_context().config
        if zone in config.coach_marks_seen:
            return False
        mark = self._coach_marks.get(zone)
        if mark is None:
            from .coach_marks import CoachMark

            mark = CoachMark(zone)
            # 'dismissed' fires once the popover has fully
            # closed (auto-timeout, button click, or autohide).
            # We use it to persist the seen flag and clear
            # the cache so a re-shown zone gets a fresh popover.
            def _on_dismiss(_popover, dismissed_zone: str):
                get_context().config.mark_coach_mark_seen(
                    dismissed_zone
                )
                self._coach_marks.pop(dismissed_zone, None)
            mark.connect("dismissed", _on_dismiss)
            self._coach_marks[zone] = mark
        # Setting the parent and re-positioning is required
        # every time because the popover may have been
        # attached to a different widget in a previous show.
        mark.set_parent(parent)
        # Popover position is auto (the arrow points to
        # parent). For the canvas, a top position is more
        # natural; for the toolbar, a bottom. The default
        # (BOTTOM) is fine for the rest.
        if zone == "canvas":
            mark.set_position(Gtk.PositionType.TOP)
        else:
            mark.set_position(Gtk.PositionType.BOTTOM)
        mark.popup()
        return False  # remove the idle source

    def _on_unit_changed(self, unit: str) -> None:
        """Persist the display unit when the user changes it
        in the coordinate bar."""
        if unit in ("mm", "in"):
            get_context().config.set_unit_preference("length", unit)

    def _on_unit_changed_apply_initial(self) -> None:
        """Apply the unit saved in config on app startup so the
        coordinate bar shows the user's preferred unit from
        the first frame."""
        unit = get_context().config.unit_preferences.get("length", "mm")
        if unit not in ("mm", "in"):
            unit = "mm"
        self.coordinate_bar.set_unit(unit)

    def on_running_tasks_changed(self, sender, tasks, progress):
        self._update_actions_and_ui()
        self._update_status_message(tasks, progress)

    def _update_status_message(self, tasks, progress):
        if not tasks:
            self._status_message_label.set_visible(False)
            self.status_bar.set_mode("designing")
            self.status_bar.set_progress(None)
            return

        oldest_task = tasks[0]
        message = oldest_task.get_message()
        status_text = message if message is not None else ""

        if status_text and len(tasks) > 1:
            status_text += _(" (+{tasks} more)").format(tasks=len(tasks) - 1)
        elif len(tasks) > 1:
            status_text = _("{tasks} tasks").format(tasks=len(tasks))

        self._status_message_label.set_text(status_text)
        self._status_message_label.set_visible(bool(status_text))

        # Update the persistent status bar with mode + progress.
        # We pick 'sending' as the dominant mode when there's an
        # active task; the caller can override with 'paused' or
        # 'alarm' via the explicit setters when those apply.
        self.status_bar.set_mode("sending", label=status_text or "Sending")
        self.status_bar.set_progress(progress)

    def _update_actions_and_ui(self):
        config = get_context().config
        active_machine = config.machine
        am = self.action_manager
        doc = self.doc_editor.doc

        # The document_settled signal can fire BEFORE
        # self.bottom_panel and self.toolbar are
        # constructed (e.g. when the doc editor adds
        # its default 'Contorno' step during __init__).
        # Guard so the signal doesn't crash startup. The
        # next signal fire (after construction completes)
        # will pick up the missing UI update.
        if not hasattr(self, "bottom_panel") or not hasattr(self, "toolbar"):
            return

        if not active_machine:
            am.get_action("export").set_enabled(False)
            am.get_action("machine-settings").set_enabled(False)
            am.get_action("machine-home").set_enabled(False)
            am.get_action("machine-frame").set_enabled(False)
            am.get_action("machine-send").set_enabled(False)
            am.get_action("machine-hold").set_enabled(False)
            am.get_action("machine-cancel").set_enabled(False)
            am.get_action("machine-clear-alarm").set_enabled(False)
            am.get_action("execute-macro").set_enabled(False)
            am.get_action("zero-here").set_enabled(False)

            self.toolbar.export_button.set_tooltip_text(
                _("Select a machine to enable G-code export")
            )
            self.toolbar.machine_warning_box.set_visible(False)
            self.surface.set_laser_dot_visible(False)
        else:
            device_status = active_machine.device_state.status
            conn_status = active_machine.connection_status
            state = active_machine.device_state
            active_driver = active_machine.driver
            is_dummy = isinstance(active_driver, NoDeviceDriver)

            can_export = (
                doc.has_result()
                and not task_mgr.has_tasks()
                and not self.doc_editor.pipeline.is_data_stale
            )
            am.get_action("export").set_enabled(can_export)
            export_tooltip = _("Generate G-code")
            if task_mgr.has_tasks():
                export_tooltip = _(
                    "Cannot export while other tasks are running"
                )
            elif self.doc_editor.pipeline.is_data_stale:
                export_tooltip = _(
                    "Pipeline needs recalculation before export. "
                    "Press F5 to recalculate."
                )
            elif not doc.has_workpiece():
                export_tooltip = _("Add a workpiece to enable export")
            elif not doc.has_result():
                export_tooltip = _(
                    "Add or enable a processing step to enable export"
                )
            self.toolbar.export_button.set_tooltip_text(export_tooltip)

            if active_driver and active_driver.state.error:
                self.toolbar.set_machine_warning(
                    active_driver.state.error.title,
                    active_driver.state.error.code,
                    active_driver.state.error.description,
                )
                self.toolbar.machine_warning_box.set_visible(True)
            else:
                self.toolbar.machine_warning_box.set_visible(False)
            am.get_action("machine-settings").set_enabled(True)

            # A job/task is running if the machine is not idle or a UI task is
            # active.
            machine_processing = (
                conn_status == TransportStatus.CONNECTED
                and device_status != DeviceStatus.IDLE
            )

            is_job_or_task_active = (
                machine_processing
                or task_mgr.has_tasks()
                or self.machine_cmd.is_job_running
            )

            am.get_action("machine-home").set_enabled(
                not is_job_or_task_active
            )

            can_frame = (
                active_machine.can_frame()
                and doc.has_result()
                and not is_job_or_task_active
            )
            am.get_action("machine-frame").set_enabled(can_frame)
            if not active_machine.can_frame():
                self.toolbar.frame_button.set_tooltip_text(
                    _("Configure frame power to enable")
                )
            else:
                self.toolbar.frame_button.set_tooltip_text(
                    _("Cycle laser head around the occupied area")
                )

            send_sensitive = (
                not isinstance(active_driver, NoDeviceDriver)
                and (active_driver and not active_driver.state.error)
                and conn_status == TransportStatus.CONNECTED
                and doc.has_result()
                and not is_job_or_task_active
                and not self.doc_editor.pipeline.is_data_stale
            )
            am.get_action("machine-send").set_enabled(send_sensitive)
            if self.doc_editor.pipeline.is_data_stale:
                self.toolbar.send_button.set_tooltip_text(
                    _(
                        "Pipeline needs recalculation before sending. "
                        "Press F5 to recalculate."
                    )
                )
            else:
                self.toolbar.send_button.set_tooltip_text(_("Send to machine"))

            hold_sensitive = device_status in (
                DeviceStatus.RUN,
                DeviceStatus.HOLD,
                DeviceStatus.CYCLE,
            )
            is_holding = device_status == DeviceStatus.HOLD
            am.get_action("machine-hold").set_enabled(hold_sensitive)
            am.get_action("machine-hold").set_state(
                GLib.Variant.new_boolean(is_holding)
            )
            if is_holding:
                self.toolbar.hold_button.set_child(self.toolbar.hold_on_icon)
                self.toolbar.hold_button.set_tooltip_text(_("Resume machine"))
            else:
                self.toolbar.hold_button.set_child(self.toolbar.hold_off_icon)
                self.toolbar.hold_button.set_tooltip_text(_("Pause machine"))

            cancel_sensitive = conn_status == TransportStatus.CONNECTED
            am.get_action("machine-cancel").set_enabled(cancel_sensitive)

            clear_alarm_sensitive = bool(
                device_status == DeviceStatus.ALARM
                or (active_driver and active_driver.state.error)
            )
            am.get_action("machine-clear-alarm").set_enabled(
                clear_alarm_sensitive
            )
            if clear_alarm_sensitive:
                self.toolbar.clear_alarm_button.add_css_class(
                    "suggested-action"
                )
            else:
                self.toolbar.clear_alarm_button.remove_css_class(
                    "suggested-action"
                )

            # Update focus button sensitivity
            head = active_machine.get_default_head()
            can_focus = (
                head
                and head.focus_power_percent > 0
                and not is_job_or_task_active
            )
            am.get_action("toggle-focus").set_enabled(can_focus)

            connected = conn_status == TransportStatus.CONNECTED
            self.surface.set_laser_dot_visible(connected)
            if state and connected:
                x, y = state.machine_pos[:2]
                if x is not None and y is not None:
                    self.surface.set_laser_dot_position(x, y)

            # Set macro action sensitivity
            can_run_macros = connected and not is_job_or_task_active
            am.get_action("execute-macro").set_enabled(can_run_macros)

            # WCS UI
            is_g53 = (
                active_machine.active_wcs == active_machine.machine_space_wcs
            )

            # Allow zeroing if connected OR if it's the dummy driver
            can_zero = (
                (connected or is_dummy)
                and not is_g53
                and not is_job_or_task_active
            )
            am.get_action("zero-here").set_enabled(can_zero)

        # Update actions that don't depend on the machine state
        selected_elements = self.surface.get_selected_elements()
        has_selection = len(selected_elements) > 0

        am.get_action("undo").set_enabled(
            self.doc_editor.history_manager.can_undo()
        )
        am.get_action("redo").set_enabled(
            self.doc_editor.history_manager.can_redo()
        )
        am.get_action("cut").set_enabled(has_selection)
        am.get_action("copy").set_enabled(has_selection)
        am.get_action("paste").set_enabled(self.doc_editor.edit.can_paste())
        am.get_action("asset-paste").set_enabled(
            self.bottom_panel.asset_browser.can_paste_assets()
        )
        am.get_action("select_all").set_enabled(doc.has_workpiece())
        am.get_action("duplicate").set_enabled(has_selection)
        am.get_action("remove").set_enabled(has_selection)
        am.get_action("clear").set_enabled(doc.has_workpiece())

        # Update sensitivity for Grouping actions
        can_group = len(selected_elements) >= 2
        am.get_action("group").set_enabled(can_group)

        can_ungroup = any(
            isinstance(elem.data, Group) for elem in selected_elements
        )
        am.get_action("ungroup").set_enabled(can_ungroup)

        # Update sensitivity for Layer actions
        can_move_layers = has_selection and len(doc.layers) > 1
        am.get_action("layer-move-up").set_enabled(can_move_layers)
        am.get_action("layer-move-down").set_enabled(can_move_layers)

        # Update sensitivity for 3D view actions
        is_3d_view_active = self.view_stack.get_visible_child_name() == "3d"
        can_show_3d = is_3d_view_active or canvas3d_initialized
        am.get_action("show_3d_view").set_enabled(can_show_3d)
        am.get_action("view_top").set_enabled(is_3d_view_active)
        am.get_action("view_front").set_enabled(is_3d_view_active)
        am.get_action("view_iso").set_enabled(is_3d_view_active)
        am.get_action("view_toggle_perspective").set_enabled(is_3d_view_active)

        # Update sensitivity for Arrangement actions
        can_distribute = len(self.surface.get_selected_workpieces()) >= 2
        am.get_action("align-h-center").set_enabled(has_selection)
        am.get_action("align-v-center").set_enabled(has_selection)
        am.get_action("align-left").set_enabled(has_selection)
        am.get_action("align-right").set_enabled(has_selection)
        am.get_action("align-top").set_enabled(has_selection)
        am.get_action("align-bottom").set_enabled(has_selection)
        am.get_action("spread-h").set_enabled(can_distribute)
        am.get_action("spread-v").set_enabled(can_distribute)
        self.toolbar.arrange_menu_button.set_sensitive(has_selection)

        # Update sensitivity for Tab buttons
        show_tabs_action = am.get_action("show_tabs")
        has_any_tabs = any(wp.tabs for wp in doc.all_workpieces)
        show_tabs_action.set_enabled(has_any_tabs)

    def on_machine_warning_clicked(self, sender):
        """Opens the machine settings dialog for the current machine."""
        config = get_context().config
        if not config.machine:
            return
        dialog = MachineSettingsDialog(
            machine=config.machine,
            transient_for=self,
        )
        dialog.present()

    def on_status_bar_clicked(self, sender):
        action = self.action_manager.get_action("toggle_bottom_panel")
        state = action.get_state()
        if state:
            new_state = not state.get_boolean()
            action.change_state(GLib.Variant.new_boolean(new_state))
        else:
            action.change_state(GLib.Variant.new_boolean(True))

    def on_toggle_bottom_panel_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        action.set_state(value)

        if is_visible:
            self.bottom_panel.set_visible(True)
            full_height = self.vertical_paned.get_height()
            self.vertical_paned.set_position(
                full_height - self._last_bottom_panel_height
            )
            get_usage_tracker().track_page_view(
                "/bottom-panel/open", "Bottom Panel Opened"
            )
        else:
            self.bottom_panel.set_visible(False)

        # Record the user's per-panel override. If the toggle
        # ends up matching the current preset, the override is
        # cleared so the preset becomes canonical again.
        if hasattr(self, "panel_manager"):
            preset = self.panel_manager.resolve(
                get_context().config.panel_layout
            )
            if is_visible == preset["bottom"]:
                get_context().config.set_panel_override(
                    "bottom", None
                )
            else:
                get_context().config.set_panel_override(
                    "bottom", is_visible
                )

        self._save_bottom_panel()

    def on_toggle_right_panel_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        is_visible = value.get_boolean()
        action.set_state(value)
        self._right_pane.set_visible(is_visible)
        # Sync the header-bar toggle so it reflects reality when the
        # action is fired from the menu, a keyboard shortcut, or the
        # breakpoint. Guarded with hasattr because this method can
        # be called during early construction (before the toggle is
        # added to the header bar).
        toggle = getattr(self, "_right_panel_toggle", None)
        if toggle is not None:
            toggle.set_active(is_visible)

        # Record the user's per-panel override. If the toggle
        # ends up matching the current preset, the override is
        # cleared so the preset becomes canonical again.
        if hasattr(self, "panel_manager"):
            preset = self.panel_manager.resolve(
                get_context().config.panel_layout
            )
            if is_visible == preset["right"]:
                get_context().config.set_panel_override("right", None)
            else:
                get_context().config.set_panel_override(
                    "right", is_visible
                )
        toggle = getattr(self, "_right_panel_toggle", None)
        if toggle is not None:
            toggle.set_active(is_visible)
        # If the user explicitly toggles in narrow mode, drop the
        # auto-restore hint so the breakpoint unapply doesn't undo
        # their choice.
        if is_visible and getattr(self, "_narrow_mode", False):
            self._right_pane_was_visible_before_narrow = True
        get_context().config.set_right_panel_visible(is_visible)

    def _on_dialog_notification(self, sender, message: str = ""):
        """Shows a toast when requested by a child dialog."""
        toast = Adw.Toast.new(message)
        self._add_toast(toast)

    def on_quit_action(self, action, parameter):
        self.close()

    def do_close_request(self):
        """
        Handles the 'close-request' signal to check for unsaved changes.
        For GTK signals, returning True PREVENTS the default handler from
        running (i.e., stops the close). Returning False allows it.
        """
        if self.doc_editor.is_saved:
            return False  # Allow the window to close

        self.project_cmd.show_unsaved_changes_dialog(
            self._on_close_request_dialog_response
        )
        return True  # Prevent the window from closing until user responds

    def _on_close_request_dialog_response(self, response):
        """Callback for unsaved changes dialog in do_close_request."""
        if response == "cancel":
            return  # Do nothing, window remains open.

        if response == "discard":
            self.destroy()
            return

        if response == "save":
            self.project_cmd.on_save_project(None, None)
            if self.doc_editor.is_saved:
                self.destroy()

    def on_menu_import(self, action, param=None):
        start_interactive_import(self, self.doc_editor)

    def on_open_clicked(self, sender):
        self.on_menu_import(sender)

    def on_clear_clicked(self, action, param):
        self.doc_editor.edit.clear_all_items()

    def on_recalculate_clicked(self, action, param):
        self.doc_editor.pipeline.recalculate()

    def on_force_recalculate_clicked(self, action, param):
        self.doc_editor.pipeline.recalculate(force=True)

    def _run_sanity_check_and_proceed(self, proceed_callback):
        config = get_context().config
        machine = config.machine
        if not machine:
            proceed_callback()
            return

        checker = SanityChecker(machine)

        def _handle_ops(ops):
            report = checker.check(ops, mode=CheckMode.FAST)
            if report.is_clean:
                proceed_callback()
            else:
                dialog = SanityCheckDialog(
                    parent=self,
                    report=report,
                    on_proceed=proceed_callback,
                )
                dialog.present()

        existing = self.doc_editor.pipeline.get_existing_job_handle()
        if existing is not None:
            artifact_store = self.doc_editor.pipeline.artifact_store
            try:
                with artifact_store.checkout_handle(existing) as artifact:
                    if isinstance(artifact, JobArtifact):
                        _handle_ops(artifact.ops)
                        return
            except (OSError, KeyError, ValueError, AttributeError):
                logger.warning("Failed to run sanity check", exc_info=True)
            proceed_callback()
            return

        def _on_artifact_ready(handle, error):
            if error or not handle:
                proceed_callback()
                return
            try:
                artifact_store = self.doc_editor.pipeline.artifact_store
                with artifact_store.checkout_handle(handle) as artifact:
                    if isinstance(artifact, JobArtifact):
                        _handle_ops(artifact.ops)
                        return
            except (OSError, KeyError, ValueError, AttributeError):
                logger.warning("Failed to run sanity check", exc_info=True)
            proceed_callback()

        self.doc_editor.file.assemble_job_in_background(
            when_done=_on_artifact_ready
        )

    def on_export_clicked(self, action, param=None):
        def _proceed():
            initial_name = None
            if self.doc_editor.file_path:
                initial_name = f"{self.doc_editor.file_path.stem}.gcode"
            file_dialogs.show_export_gcode_dialog(
                self, self._on_save_dialog_response, initial_name
            )

        self._run_sanity_check_and_proceed(_proceed)

    def on_export_document_clicked(self, action, param=None):
        initial_name = "document.svg"
        if self.doc_editor.file_path:
            initial_name = f"{self.doc_editor.file_path.stem}.svg"
        file_dialogs.show_export_document_dialog(
            self, self._on_export_document_response, initial_name
        )

    def on_export_object_clicked(self, action, param=None):
        selected = self.surface.get_selected_workpieces()
        if len(selected) == 1:
            file_dialogs.show_export_object_dialog(
                self, self._on_export_object_response, selected[0]
            )
        else:
            self._on_editor_notification(
                self, _("Please select a single object to export.")
            )

    def _on_export_object_response(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            file_path = Path(file.get_path())

            selected = self.surface.get_selected_workpieces()
            if len(selected) != 1:
                return

            self.doc_editor.file.export_object_to_path(file_path, selected[0])

        except GLib.Error as e:
            logger.error(f"Error exporting object: {e.message}")

    def _on_export_document_response(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            file_path = Path(file.get_path())
        except GLib.Error as e:
            logger.error(f"Error exporting document: {e.message}")
            return

        self.doc_editor.file.export_document_to_path(file_path)

    def _on_save_dialog_response(self, dialog, result, user_data):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            file_path = Path(file.get_path())
        except GLib.Error as e:
            logger.error(f"Error saving file: {e.message}")
            return

        # This is now a non-blocking call.
        self.doc_editor.file.export_gcode_to_path(file_path)

    def on_home_clicked(self, action, param):
        config = get_context().config
        if not config.machine:
            return

        # Disable focus mode when homing
        focus_action = self.action_manager.get_action("toggle-focus")
        focus_state = focus_action.get_state()
        if focus_state and focus_state.get_boolean():
            focus_action.change_state(GLib.Variant.new_boolean(False))

        self.machine_cmd.home(config.machine)

    def _run_machine_job(self, job_coroutine: Coroutine):
        """
        Wraps a machine job coroutine in an asyncio.Task and handles
        its completion or failure.
        """
        fut = asyncio.run_coroutine_threadsafe(job_coroutine, task_mgr.loop)
        # Add a callback to handle the result (or exception) of the task
        fut.add_done_callback(self._on_job_future_done)

    def on_frame_clicked(self, action, param):
        config = get_context().config
        if not config.machine:
            return

        # Disable focus mode when framing
        focus_action = self.action_manager.get_action("toggle-focus")
        focus_state = focus_action.get_state()
        if focus_state and focus_state.get_boolean():
            focus_action.change_state(GLib.Variant.new_boolean(False))

        # Get the coroutine object for the framing job
        job_coro = self.machine_cmd.frame_job(
            config.machine, on_progress=self._on_job_progress_updated
        )
        # Run the job using the helper
        self._run_machine_job(job_coro)

    def on_send_clicked(self, action, param):
        config = get_context().config
        machine = config.machine
        if not machine:
            return

        def _proceed():
            focus_action = self.action_manager.get_action("toggle-focus")
            focus_state = focus_action.get_state()
            if focus_state and focus_state.get_boolean():
                focus_action.change_state(GLib.Variant.new_boolean(False))

            job_coro = self.machine_cmd.send_job(
                machine,
                on_progress=self._on_job_progress_updated,
            )
            self._run_machine_job(job_coro)

        self._run_sanity_check_and_proceed(_proceed)

    def on_hold_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        """
        Handles the 'change-state' signal for the 'hold' action.
        This is the correct handler for a stateful action.
        """
        config = get_context().config
        if not config.machine:
            return
        is_requesting_hold = value.get_boolean()
        self.machine_cmd.set_hold(config.machine, is_requesting_hold)
        action.set_state(value)

    def on_cancel_clicked(self, action, param):
        config = get_context().config
        if not config.machine:
            return
        self.machine_cmd.cancel_job(config.machine)

    def on_clear_alarm_clicked(self, action, param):
        config = get_context().config
        if not config.machine:
            return
        self.machine_cmd.clear_alarm(config.machine)

    def on_toggle_focus_state_change(
        self, action: Gio.SimpleAction, value: GLib.Variant
    ):
        """
        Handles the 'change-state' signal for the 'toggle-focus' action.
        This toggles the laser focus mode on/off.
        """
        config = get_context().config
        if not config.machine:
            return

        is_focus_on = value.get_boolean()
        head = config.machine.get_default_head()

        if is_focus_on:
            self.machine_cmd.set_focus_power(head, head.focus_power_percent)
        else:
            self.machine_cmd.set_focus_power(head, 0)
        action.set_state(value)

        # Update the toolbar button icon
        if is_focus_on:
            self.toolbar.focus_button.set_child(self.toolbar.focus_off_icon)
        else:
            self.toolbar.focus_button.set_child(self.toolbar.focus_on_icon)

    def _on_laser_power_changed(self, sender, *, head, percent):
        focus_action = self.action_manager.get_action("toggle-focus")
        if focus_action is None:
            return
        is_on = percent > 0
        focus_action.set_state(GLib.Variant.new_boolean(is_on))

    def on_elements_deleted(self, sender, elements: List[CanvasElement]):
        """Handles the deletion signal from the WorkSurface."""
        items_to_delete = [
            elem.data for elem in elements if isinstance(elem.data, DocItem)
        ]
        if items_to_delete:
            self.doc_editor.edit.remove_items(
                items_to_delete, "Delete item(s)"
            )

    def on_cut_requested(self, sender, items: List[DocItem]):
        """Handles the 'cut-requested' signal from the WorkSurface."""
        self.doc_editor.edit.cut_items(items)
        self._update_actions_and_ui()

    def on_copy_requested(self, sender, items: List[DocItem]):
        """
        Handles the 'copy-requested' signal from the WorkSurface.
        """
        self.doc_editor.edit.copy_items(items)
        self._update_actions_and_ui()

    def on_paste_requested(self, sender, *args):
        """
        Handles the 'paste-requested' signal from the WorkSurface.
        Checks for image data on system clipboard first, then falls back
        to workpiece paste.
        """
        # Priority 1: Check if system clipboard contains image data
        if self.drag_drop_cmd.handle_clipboard_paste():
            return

        # Priority 2: Standard workpiece paste
        newly_pasted = self.doc_editor.edit.paste_items()
        if newly_pasted:
            self.surface.select_items(newly_pasted)
        self._update_actions_and_ui()

    def on_select_all(self, action, param):
        """
        Selects all top-level items (workpieces and groups) in the document.
        """
        self.surface.select_all()

    def on_duplicate_requested(self, sender, items: List[DocItem]):
        """
        Handles the 'duplicate-requested' signal from the WorkSurface.
        """
        newly_duplicated = self.doc_editor.edit.duplicate_items(items)
        if newly_duplicated:
            self.surface.select_items(newly_duplicated)

    def on_menu_cut(self, action, param):
        selection = self.surface.get_selected_items()
        if selection:
            self.doc_editor.edit.cut_items(list(selection))
            self._update_actions_and_ui()

    def on_menu_copy(self, action, param):
        selection = self.surface.get_selected_items()
        if selection:
            self.doc_editor.edit.copy_items(list(selection))
            self._update_actions_and_ui()

    def on_menu_duplicate(self, action, param):
        selection = self.surface.get_selected_items()
        if selection:
            newly_duplicated = self.doc_editor.edit.duplicate_items(
                list(selection)
            )
            self.surface.select_items(newly_duplicated)

    def on_menu_remove(self, action, param):
        items = self.surface.get_selected_items()
        if items:
            self.doc_editor.edit.remove_items(list(items))

    def show_about_dialog(self, action, param):
        dialog = AboutDialog(transient_for=self)
        dialog.present()

    def on_save_debug_log(self, action, param):
        DebugLogDialog(
            parent=self,
            editor=self.doc_editor,
            on_saved=lambda name: self._on_editor_notification(
                self,
                _("Debug log saved to {path}").format(path=name),
            ),
            on_error=lambda msg: self._on_editor_notification(self, msg),
        ).present()

    def show_settings(self, action, param):
        dialog = SettingsWindow(transient_for=self)
        dialog.present()
        dialog.connect("close-request", self._on_settings_dialog_closed)

    def show_machine_settings(self, action, param):
        """Opens the machine settings dialog for the current machine."""
        config = get_context().config
        if not config.machine:
            return
        dialog = MachineSettingsDialog(
            machine=config.machine,
            transient_for=self,
        )
        dialog.present()

    def _on_settings_dialog_closed(self, dialog):
        logger.debug("Settings dialog closed")
        self.surface.grab_focus()  # re-enables keyboard shortcuts

    def _on_job_time_updated(self, sender, *, total_seconds):
        self._time_estimate_overlay.set_estimated_time(total_seconds)
        if self._canvas3d_time_overlay is not None:
            self._canvas3d_time_overlay.set_estimated_time(total_seconds)
