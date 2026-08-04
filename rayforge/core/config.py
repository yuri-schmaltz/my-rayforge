import logging
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from blinker import Signal

from ..machine.models.machine import Machine

logger = logging.getLogger(__name__)


class OpsColorMode(Enum):
    """Enum for ops color source options."""

    LASER = "laser"
    LAYER = "layer"


class StartupBehavior(Enum):
    """Enum for application startup behavior options."""

    NONE = "none"
    LAST_PROJECT = "last_project"
    SPECIFIC_PROJECT = "specific_project"


@dataclass
class CanvasViewState:
    """Persistent view toggle states for the 2D/3D canvases."""

    show_workpieces: bool = True
    show_camera: bool = True
    show_travel_lines: bool = False
    show_nogo_zones: bool = True
    show_grid: bool = True
    show_models: bool = True
    show_tabs: bool = True
    perspective_mode: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasViewState":
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class Config:
    def __init__(self):
        self.machine: Optional[Machine] = None
        self.theme: str = "system"
        # UI density: "comfortable" (default, current spacing),
        # "compact" (tighter rows, smaller paddings for users
        # who want more content on screen). The runtime applies
        # this via a CSS class on the main window.
        self.ui_density: str = "comfortable"
        # Toolbar mode: "essential" (default — only the most-used
        # buttons are visible) or "all" (every button). The user
        # toggles a "..." button in the toolbar; the choice is
        # persisted here.
        self.toolbar_mode: str = "essential"
        # Walkthrough seen flag. False on first launch so the
        # 5-card intro dialog appears; True after the user
        # dismisses it (Skip / Done / close button).
        self.walkthrough_seen: bool = False
        # Panel layout preset. One of "default", "compact",
        # "expanded". The PanelManager applies the preset to
        # the right + bottom panel visibility on every change.
        self.panel_layout: str = "default"
        # Per-panel overrides layered on top of the preset.
        # e.g. {"right": False} means "use the preset's bottom
        # panel state, but force the right panel off". The
        # override is updated whenever the user explicitly
        # toggles a panel via the header buttons.
        self.panel_overrides: dict = {}
        # Per-zone coach-mark seen flags. Each entry is a zone
        # name (see coach_marks.COACH_MARKS for the canonical
        # list). The first time the user interacts with a zone,
        # a popover shows; the flag is added to this set so
        # the popover never re-shows (the user can re-enable
        # all coach marks by clearing the list from the Help
        # menu).
        self.coach_marks_seen: list = []
        # Lazy-load addon frontend modules on first attribute
        # access instead of at startup. Default False to keep
        # the existing behavior; enable via
        # RAYFORGE_LAZY_ADDONS=1 to opt in. The trade-off
        # is documented in rayforge/addon_mgr/lazy.py.
        self.addon_lazy_load: bool = False
        # Default user preferences for units. Key is quantity, value is
        # unit name.
        self.unit_preferences: Dict[str, str] = {
            "length": "mm",
            "speed": "mm/min",
            "acceleration": "mm/s²",
        }
        # Startup behavior: "none", "last_project", or "specific_project"
        self.startup_behavior: str = StartupBehavior.NONE.value
        # Path to the specific project to open on startup (when
        # startup_behavior is SPECIFIC_PROJECT)
        self.startup_project_path: Optional[Path] = None
        # Track the last opened project path
        self.last_opened_project: Optional[Path] = None
        # UI visibility states
        self.bottom_panel: Optional[Dict[str, Any]] = None
        self.right_panel_visible: bool = True
        self.canvas_view: CanvasViewState = CanvasViewState()
        self.auto_pipeline: bool = True
        self.ops_color_mode: OpsColorMode = OpsColorMode.LASER
        # Pires Forge does not check for updates by default. The fork
        # has its own release cadence and we don't want to silently
        # notify users about unrelated upstream versions. Users can
        # opt-in via Settings → Preferences.
        self.check_for_app_updates: bool = False
        # Usage tracking consent date: None = not asked, "" = declined,
        # ISO date string = consent given on that date
        self.usage_consent_date: Optional[str] = None
        # Default DPI for unitless SVG imports
        self.import_dpi: float = 96.0
        # Language preference: None = system default, or a code like "de"
        self.language: Optional[str] = None
        self.changed = Signal()

    def set_machine(self, machine: Optional[Machine]):
        if self.machine == machine:
            return
        if self.machine:
            self.machine.changed.disconnect(self.changed.send)
        self.machine = machine
        self.changed.send(self)
        if self.machine:
            self.machine.changed.connect(self.changed.send)

    def set_theme(self, theme: str):
        """Sets the application theme preference."""
        if self.theme == theme:
            return
        self.theme = theme
        self.changed.send(self)

    def set_ui_density(self, density: str):
        """Sets the UI density.

        Recognized values: "comfortable" (default), "compact".
        Any other value is stored verbatim; the runtime apply
        step in MainWindow treats unknown values as "comfortable".
        """
        if self.ui_density == density:
            return
        self.ui_density = density
        self.changed.send(self)

    def set_toolbar_mode(self, mode: str):
        """Sets the toolbar mode.

        Recognized values: "essential" (default — only the most-
        used buttons are visible) or "all" (every button). The
        toolbar Mode button toggles between these.
        """
        if self.toolbar_mode == mode:
            return
        self.toolbar_mode = mode
        self.changed.send(self)

    def set_walkthrough_seen(self, seen: bool = True):
        """Mark the first-run walkthrough as seen.

        Called when the user dismisses the walkthrough dialog
        (Skip, Done, or close button). The flag is persisted to
        config so the dialog never shows again unless the user
        re-opens it from the Help menu.
        """
        if self.walkthrough_seen == seen:
            return
        self.walkthrough_seen = seen
        self.changed.send(self)

    def set_panel_layout(self, layout: str) -> None:
        """Sets the panel layout preset.

        Recognized values: 'default', 'compact', 'expanded'.
        Anything else is treated as 'default' by the
        PanelManager. Triggers a config.changed signal so the
        MainWindow can re-apply visibility.
        """
        if self.panel_layout == layout:
            return
        self.panel_layout = layout
        self.changed.send(self)

    def set_panel_override(self, panel: str, visible: Optional[bool]) -> None:
        """Set or clear a per-panel visibility override.

        Args:
            panel: 'right' or 'bottom'.
            visible: True/False to set the override, or None to
                clear it (so the preset's default applies again).
        """
        if visible is None:
            self.panel_overrides.pop(panel, None)
        else:
            self.panel_overrides[panel] = bool(visible)
        self.changed.send(self)

    def mark_coach_mark_seen(self, zone: str) -> None:
        """Add a zone to the seen set.

        Idempotent: re-marking an already-seen zone is a no-op
        (no signal, no list change). This is important because
        the same zone can fire its trigger multiple times in
        a single session (e.g. the user clicks the toolbar
        many times after the first popover was shown).
        """
        if zone in self.coach_marks_seen:
            return
        self.coach_marks_seen.append(zone)
        self.changed.send(self)

    def reset_coach_marks(self) -> None:
        """Clear all coach-mark seen flags.

        Called from the Help > 'Replay Coach Marks' menu item
        (or equivalent). The next time the user interacts with
        any zone, the corresponding popover re-shows.
        """
        if not self.coach_marks_seen:
            return
        self.coach_marks_seen = []
        self.changed.send(self)

    def set_unit_preference(self, quantity: str, unit_name: str):
        """Sets the user's preferred display unit for a quantity."""
        if self.unit_preferences.get(quantity) == unit_name:
            return
        self.unit_preferences[quantity] = unit_name
        self.changed.send(self)

    def set_startup_behavior(self, behavior: StartupBehavior):
        """Sets the startup behavior preference."""
        behavior_value = behavior.value
        if self.startup_behavior == behavior_value:
            return
        self.startup_behavior = behavior_value
        self.changed.send(self)

    def set_startup_project_path(self, path: Optional[Path]):
        """Sets the specific project path to open on startup."""
        if self.startup_project_path == path:
            return
        self.startup_project_path = path
        self.changed.send(self)

    def set_last_opened_project(self, path: Optional[Path]):
        """Sets the last opened project path."""
        if self.last_opened_project == path:
            return
        self.last_opened_project = path
        self.changed.send(self)

    def set_bottom_panel(self, data: Optional[Dict[str, Any]]):
        if self.bottom_panel == data:
            return
        self.bottom_panel = data
        self.changed.send(self)

    def set_right_panel_visible(self, visible: bool):
        """Sets the right panel visibility state."""
        if self.right_panel_visible == visible:
            return
        self.right_panel_visible = visible
        self.changed.send(self)

    def set_import_dpi(self, dpi: float):
        """Sets the default DPI for unitless SVG imports."""
        if self.import_dpi == dpi:
            return
        self.import_dpi = dpi
        self.changed.send(self)

    def set_auto_pipeline(self, enabled: bool):
        """Sets whether the pipeline recalculates automatically."""
        if self.auto_pipeline == enabled:
            return
        self.auto_pipeline = enabled
        self.changed.send(self)

    def set_check_for_app_updates(self, enabled: bool):
        """Sets whether to check for application updates on startup."""
        if self.check_for_app_updates == enabled:
            return
        self.check_for_app_updates = enabled
        self.changed.send(self)

    def set_ops_color_mode(self, mode: OpsColorMode):
        """Sets the ops color mode."""
        if self.ops_color_mode == mode:
            return
        self.ops_color_mode = mode
        self.changed.send(self)

    def set_language(self, language: Optional[str]):
        """Sets the UI language preference.

        Args:
            language: Language code (e.g. "de") or None for system default.
        """
        if self.language == language:
            return
        self.language = language
        self.changed.send(self)

    def set_usage_consent(self, consent: bool):
        """Sets the usage tracking consent preference."""
        new_value = ""
        if consent:
            new_value = datetime.now().isoformat()
        if self.usage_consent_date == new_value:
            return
        self.usage_consent_date = new_value
        self.changed.send(self)

    @property
    def has_consented_tracking(self) -> bool:
        """Returns True if user has consented to usage tracking after
        the current policy date."""
        if not self.usage_consent_date or self.usage_consent_date == "":
            return False
        try:
            consent_date = datetime.fromisoformat(self.usage_consent_date)
            policy_date = datetime(2026, 2, 24)
            return consent_date >= policy_date
        except (ValueError, TypeError):
            return False

    @property
    def has_declined_tracking(self) -> bool:
        """Returns True if user has explicitly declined usage tracking."""
        return self.usage_consent_date == ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine": self.machine.id if self.machine else None,
            "theme": self.theme,
            "ui_density": self.ui_density,
            "toolbar_mode": self.toolbar_mode,
            "walkthrough_seen": self.walkthrough_seen,
            "panel_layout": self.panel_layout,
            "panel_overrides": self.panel_overrides,
            "coach_marks_seen": self.coach_marks_seen,
            "addon_lazy_load": self.addon_lazy_load,
            "unit_preferences": self.unit_preferences,
            "startup_behavior": self.startup_behavior,
            "startup_project_path": (
                str(self.startup_project_path)
                if self.startup_project_path
                else None
            ),
            "last_opened_project": (
                str(self.last_opened_project)
                if self.last_opened_project
                else None
            ),
            "bottom_panel": self.bottom_panel,
            "right_panel_visible": self.right_panel_visible,
            "canvas_view": self.canvas_view.to_dict(),
            "auto_pipeline": self.auto_pipeline,
            "check_for_app_updates": self.check_for_app_updates,
            "ops_color_mode": self.ops_color_mode.value,
            "usage_consent_date": self.usage_consent_date,
            "import_dpi": self.import_dpi,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], get_machine_by_id) -> "Config":
        config = cls()
        config.theme = data.get("theme", "system")
        config.ui_density = data.get("ui_density", "comfortable")
        config.toolbar_mode = data.get("toolbar_mode", "essential")
        config.walkthrough_seen = data.get("walkthrough_seen", False)
        config.panel_layout = data.get("panel_layout", "default")
        config.panel_overrides = data.get("panel_overrides", {})
        config.coach_marks_seen = data.get("coach_marks_seen", [])
        config.addon_lazy_load = data.get("addon_lazy_load", False)

        # Load unit preferences, falling back to defaults for safety
        default_prefs = {
            "length": "mm",
            "speed": "mm/min",
            "acceleration": "mm/s²",
        }
        loaded_prefs = data.get("unit_preferences", default_prefs)
        # Ensure all default keys are present
        default_prefs.update(loaded_prefs)
        config.unit_preferences = default_prefs

        # Load startup behavior
        default_behavior = StartupBehavior.NONE.value
        startup_behavior = data.get("startup_behavior", default_behavior)
        try:
            StartupBehavior(startup_behavior)
            config.startup_behavior = startup_behavior
        except ValueError:
            logger.warning(
                f"Invalid startup behavior in config: {startup_behavior}. "
                f"Using default: {default_behavior}"
            )
            config.startup_behavior = default_behavior

        # Load startup project path
        startup_project_path_str = data.get("startup_project_path")
        if startup_project_path_str:
            config.startup_project_path = Path(startup_project_path_str)

        # Load last opened project path
        last_opened_project_str = data.get("last_opened_project")
        if last_opened_project_str:
            config.last_opened_project = Path(last_opened_project_str)

        # Load UI visibility states
        config.bottom_panel = data.get("bottom_panel", None)
        config.right_panel_visible = data.get("right_panel_visible", True)
        config.canvas_view = CanvasViewState.from_dict(
            data.get("canvas_view", {})
        )
        config.auto_pipeline = data.get("auto_pipeline", True)
        config.check_for_app_updates = data.get("check_for_app_updates", False)

        ops_color_mode_str = data.get(
            "ops_color_mode", OpsColorMode.LASER.value
        )
        try:
            config.ops_color_mode = OpsColorMode(ops_color_mode_str)
        except ValueError:
            config.ops_color_mode = OpsColorMode.LASER

        # Load usage tracking consent date
        config.usage_consent_date = data.get("usage_consent_date", None)

        # Load import DPI
        config.import_dpi = data.get("import_dpi", 96.0)

        # Load language preference (None = system default)
        config.language = data.get("language", None)

        # Get the machine by ID. add fallbacks in case the machines
        # no longer exist.
        machine_id = data.get("machine")
        machine = None
        if machine_id is not None:
            machine = get_machine_by_id(machine_id)
            if machine is None:
                msg = f"config references unknown machine {machine_id}"
                logger.error(msg)
        if machine:
            config.set_machine(machine)

        return config


class ConfigManager:
    def __init__(self, filepath: Path, machine_mgr):
        self.filepath = filepath
        self.machine_mgr = machine_mgr
        self.config: Config = Config()

        # Load first, which may trigger 'changed' signals if defaults are set
        self.load()
        # Connect the auto-save handler *after* loading is complete.
        self.config.changed.connect(self._on_config_changed)
        # Listen to machine removal to update config if needed
        self.machine_mgr.machine_removed.connect(self._on_machine_removed)

    def _on_config_changed(self, sender, **kwargs):
        self.save()

    def _on_machine_removed(self, sender, machine_id):
        """Handle machine removal by clearing config reference if needed."""
        if self.config.machine and self.config.machine.id == machine_id:
            msg = f"Current machine {machine_id} removed, clearing config"
            logger.info(msg)
            # Clear the machine reference
            self.config.set_machine(None)
            # If there are other machines available, select the first one
            if self.machine_mgr.machines:
                # Sort by ID for deterministic selection
                first_machine = list(
                    sorted(
                        self.machine_mgr.machines.values(), key=lambda m: m.id
                    )
                )[0]
                self.config.set_machine(first_machine)
                logger.info(f"Selected new machine {first_machine.id}")

    def save(self):
        if not self.config:
            return
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w") as f:
            yaml.safe_dump(self.config.to_dict(), f)

    def load(self) -> "Config":
        if not self.filepath.exists():
            logger.info("Config file does not exist, creating default config.")
            self.config = Config()
            return self.config

        try:
            with open(self.filepath, "r") as f:
                data = yaml.safe_load(f)
                if not data:
                    logger.info(
                        "Config file is empty, creating default config."
                    )
                    self.config = Config()
                else:
                    machine_id = data.get("machine")
                    logger.info(
                        f"Loading config with machine_id: {machine_id}"
                    )
                    self.config = Config.from_dict(
                        data, self.machine_mgr.get_machine_by_id
                    )
                    if self.config.machine:
                        logger.info(
                            f"Config loaded with machine: "
                            f"{self.config.machine.id} "
                            f"({self.config.machine.name})"
                        )
                    else:
                        logger.info("Config loaded but no machine set.")
        except (IOError, yaml.YAMLError) as e:
            logger.error(
                f"Failed to load config file: {e}. Creating a default config."
            )
            self.config = Config()

        return self.config
