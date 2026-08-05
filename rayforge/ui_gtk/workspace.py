"""Workspace save/load — persist the dock layout + UI state.

A workspace is a named bundle of UI preferences:
  - DockLayout (which surface is in which zone)
  - PanelLayout preset (default/compact/expanded)
  - Theme (system/light/dark)
  - Toolbar mode (essential/all)
  - Walkthrough_seen (one-time flag)

Workspaces are saved to ~/.config/pires-forge/
workspaces/<name>.json. The 'default' workspace is
created automatically on first launch; users can
duplicate it to create variations.

Switching workspaces (Ctrl+Tab, or 'View > Workspace'
submenu) restores the saved state. The state is
applied immediately to the live UI.

Why JSON? The state is small (~200 bytes), JSON is
debuggable in any text editor, and a future Web UI
can edit the same format.

Why not the existing config.yaml? That file is
'user preferences' (a single canonical set of values).
Workspaces are 'named snapshots of preferences' —
multiple can exist; the user picks one. They live in
a different directory and a different lifecycle.
Mixing them would require schema versioning on the
canonical config which we don't have.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """A named bundle of UI preferences.

    The fields mirror config.Config (subset) so
    loading a workspace is essentially a config
    override. Future fields (font size, density,
    per-workspace action history) are added here
    without changing the storage format.
    """
    name: str
    dock_layout: dict
    panel_layout: str = "default"
    theme: str = "system"
    toolbar_mode: str = "essential"
    walkthrough_seen: bool = True

    def to_json(self) -> str:
        return json.dumps(
            {
                "name": self.name,
                "dock_layout": self.dock_layout,
                "panel_layout": self.panel_layout,
                "theme": self.theme,
                "toolbar_mode": self.toolbar_mode,
                "walkthrough_seen": self.walkthrough_seen,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, s: str) -> "Workspace":
        d = json.loads(s)
        return cls(
            name=d.get("name", "unnamed"),
            dock_layout=d.get("dock_layout", {}),
            panel_layout=d.get("panel_layout", "default"),
            theme=d.get("theme", "system"),
            toolbar_mode=d.get("toolbar_mode", "essential"),
            walkthrough_seen=d.get("walkthrough_seen", True),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "dock_layout": self.dock_layout,
            "panel_layout": self.panel_layout,
            "theme": self.theme,
            "toolbar_mode": self.toolbar_mode,
            "walkthrough_seen": self.walkthrough_seen,
        }


def workspace_dir(config_dir: Path) -> Path:
    """Return the directory where workspaces are stored.

    The directory is created on first access. Layout:
    ~/.config/pires-forge/workspaces/<name>.json
    """
    d = config_dir / "workspaces"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_workspaces(config_dir: Path) -> Dict[str, Workspace]:
    """Return all workspaces keyed by name.

    Returns an empty dict if no workspaces exist. The
    'default' workspace is created on first call if
    the directory is empty.
    """
    wd = workspace_dir(config_dir)
    result: Dict[str, Workspace] = {}
    for path in sorted(wd.glob("*.json")):
        try:
            with open(path) as f:
                ws = Workspace.from_json(f.read())
            result[ws.name] = ws
        except Exception as e:
            logger.warning(
                "Failed to load workspace %s: %s", path, e
            )
    if not result:
        # Seed with the default workspace
        default = _make_default_workspace()
        save_workspace(config_dir, default)
        result[default.name] = default
    return result


def save_workspace(config_dir: Path, workspace: Workspace) -> Path:
    """Save `workspace` to disk. Overwrites if it exists.

    Returns the path of the saved file.
    """
    path = workspace_dir(config_dir) / f"{workspace.name}.json"
    with open(path, "w") as f:
        f.write(workspace.to_json())
    return path


def load_workspace(config_dir: Path, name: str) -> Optional[Workspace]:
    """Load a workspace by name. Returns None if missing."""
    path = workspace_dir(config_dir) / f"{name}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return Workspace.from_json(f.read())
    except Exception as e:
        logger.warning("Failed to load workspace %s: %s", name, e)
        return None


def delete_workspace(config_dir: Path, name: str) -> bool:
    """Delete a workspace by name. Returns True if removed."""
    if name == "default":
        # Never delete the default workspace
        return False
    path = workspace_dir(config_dir) / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def _make_default_workspace() -> Workspace:
    """Return the default workspace (matches wave-1 main window)."""
    return Workspace(
        name="default",
        dock_layout={
            "top": "coordinate_bar",
            "right": "right_pane",
            "bottom": "bottom_panel",
            "left": "",
            "center": "canvas",
        },
        panel_layout="default",
        theme="system",
        toolbar_mode="essential",
        walkthrough_seen=False,
    )
