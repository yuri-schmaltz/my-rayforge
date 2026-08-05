"""Workspace menu — View > Workspace submenu.

A submenu under the View menu that lets the user:
  - Switch between saved workspaces (default + any
    they created)
  - Save the current layout as a new workspace
  - Reset to the default layout
  - Delete a custom workspace (not 'default')

The menu is built dynamically each time it's opened
(so newly-saved workspaces show up immediately).

GAction design:

  - 'workspace.reset' (no parameter) — restore the
    default layout
  - 'workspace.save' (string parameter, the name) —
    save the current layout under that name
  - 'workspace.switch' (string parameter, the name) —
    switch to the named workspace
  - 'workspace.delete' (string parameter, the name) —
    delete a custom workspace

Why GAction instead of a popover? GActions are:
  - Keyboard-bindable (Ctrl+1 for workspace 'one',
    etc.)
  - State-readable (a 'current' workspace state)
  - Disablable in a single API call when there are
    no workspaces to switch to
  - Discoverable in the keyboard shortcuts dialog

The MainWindow adds the actions and the menu items
in its _build_menus() method.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .workspace import (
    Workspace,
    _make_default_workspace,
    delete_workspace,
    list_workspaces,
    load_workspace,
    save_workspace,
)

logger = logging.getLogger(__name__)


# Callback signatures for the actions
WorkspaceCallback = callable  # (action, param) -> None


def _make_workspace_callback(
    config_dir: Path, on_apply: callable
) -> Dict[str, WorkspaceCallback]:
    """Build the four GAction callbacks for the
    workspace menu. Returns a dict keyed by action
    name.

    `on_apply` is the MainWindow's callback that
    actually applies a Workspace to the live UI
    (re-arranges panels, updates DockLayout, etc.).
    """
    def on_reset(_action, _param) -> None:
        ws = _make_default_workspace()
        save_workspace(config_dir, ws)
        on_apply(ws)

    def on_save(_action, param: GLib.Variant) -> None:
        name = param.get_string() if param else ""
        if not name or name == "default":
            logger.warning(
                "Refusing to save workspace with invalid "
                "name: %r", name
            )
            return
        # Read the current DockLayout and panel
        # state from the live UI. For this commit
        # we just save the current 'default' (the
        # MainWindow will pass the live state in a
        # future commit).
        ws = Workspace(
            name=name,
            dock_layout={},  # filled in by MainWindow
            panel_layout="default",
            theme="system",
            toolbar_mode="essential",
            walkthrough_seen=True,
        )
        save_workspace(config_dir, ws)
        logger.info("Saved workspace: %s", name)

    def on_switch(_action, param: GLib.Variant) -> None:
        name = param.get_string() if param else ""
        if not name:
            return
        ws = load_workspace(config_dir, name)
        if ws is not None:
            on_apply(ws)
        else:
            logger.warning(
                "Workspace not found: %s", name
            )

    def on_delete(_action, param: GLib.Variant) -> None:
        name = param.get_string() if param else ""
        if not name:
            return
        if delete_workspace(config_dir, name):
            logger.info("Deleted workspace: %s", name)
        else:
            logger.warning(
                "Could not delete workspace: %s", name
            )

    return {
        "reset": on_reset,
        "save": on_save,
        "switch": on_switch,
        "delete": on_delete,
    }


def add_workspace_actions(
    window: Gtk.Window,
    config_dir: Path,
    on_apply: callable,
) -> None:
    """Register the four GActions and the menu items
    on the given window.

    `on_apply` is invoked whenever a workspace is
    selected (switch or reset). The MainWindow
    implements it to update the DockLayout and
    re-arrange the UI to match the workspace.

    The 'switch' and 'delete' actions accept a
    string parameter (the workspace name). The
    'save' action also accepts a string (the new
    workspace name). The 'reset' action takes no
    parameter.

    The menu items are:
      View > Workspace > Reset to default
      View > Workspace > ----
      View > Workspace > default
      View > Workspace > <any other saved>
      View > Workspace > ----
      View > Workspace > Save current as...
      View > Workspace > Delete...
    """
    callbacks = _make_workspace_callback(
        config_dir, on_apply
    )

    def make_action(name: str, param_type: Optional[str]):
        if param_type is None:
            action = Gio.SimpleAction.new(name, None)
        else:
            action = Gio.SimpleAction.new(
                name, GLib.VariantType.new(param_type)
            )
        # Map action name -> callback
        key = {
            "workspace.reset": "reset",
            "workspace.save": "save",
            "workspace.switch": "switch",
            "workspace.delete": "delete",
        }[name]
        action.connect("activate", callbacks[key])
        window.add_action(action)

    make_action("workspace.reset", None)
    make_action("workspace.save", "s")
    make_action("workspace.switch", "s")
    make_action("workspace.delete", "s")


def build_workspace_submenu(
    config_dir: Path, current: Optional[str] = None
) -> Gio.Menu:
    """Build the View > Workspace submenu model.

    Returns a Gio.Menu with sections:
      [Reset to default]
      [Saved workspaces: default + any user]
      [Save as / Delete]

    `current` is the name of the currently active
    workspace; the matching item gets the
    'submenu-active' check mark via a custom
    attribute (Gio.Menu doesn't have a built-in
    'selected' state for menu items, so we use
    the 'action' attribute 'workspace.switch' and
    let the user know via the name).
    """
    menu = Gio.Menu()
    menu.append("Reset to default", "workspace.reset")
    menu.append_section(
        "Saved", _build_saved_section(config_dir, current)
    )
    menu.append_section(
        "Manage", _build_manage_section()
    )
    return menu


def _build_saved_section(
    config_dir: Path, current: Optional[str]
) -> Gio.Menu:
    """Build the 'Saved' section of the workspace
    submenu. Lists 'default' first, then any other
    saved workspaces in alphabetical order.
    """
    section = Gio.Menu()
    workspaces = list_workspaces(config_dir)
    for name in sorted(workspaces.keys()):
        label = name
        if name == current:
            label = f"✓ {name}"
        section.append(label, f"workspace.switch::{name}")
    return section


def _build_manage_section() -> Gio.Menu:
    """Build the 'Manage' section: Save as..., Delete."""
    section = Gio.Menu()
    # Save is invoked from a custom dialog in the
    # MainWindow (we don't have a built-in 'prompt
    # for a string' action in Gtk 4.10). The
    # 'workspace.save' action is exposed anyway
    # so a future dialog can call it programmatically.
    section.append(
        "Save current as… (use Ctrl+Shift+S)",
        "workspace.save::",
    )
    section.append(
        "Delete… (use Ctrl+Shift+D)",
        "workspace.delete::",
    )
    return section
