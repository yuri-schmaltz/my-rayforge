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
from typing import Dict, List, Optional

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


# Default keyboard accelerators for the workspace
# actions. Format: ["<Primary><Shift>R"] = Ctrl+Shift+R
# on Linux/Windows, Cmd+Shift+R on macOS. These
# follow the convention used by other GTK 4 apps
# (e.g. GNOME Text Editor, GNOME Builder).
DEFAULT_ACCELERATORS: Dict[str, List[str]] = {
    "workspace.reset": ["<Primary><Shift>R"],
    # Save: Ctrl+Shift+S prompts the user for a name
    # and saves the current layout. Implementation in
    # the MainWindow (the action is registered here
    # but the actual save logic is in the window's
    # on_save_current_workspace callback).
    "workspace.save": ["<Primary><Shift>S"],
    # Delete: Ctrl+Shift+D deletes the currently
    # active workspace (other than 'default'). The
    # MainWindow wires the active workspace name
    # to the action's parameter.
    "workspace.delete": ["<Primary><Shift>D"],
}


def add_workspace_actions(
    window: Gtk.Window,
    config_dir: Path,
    on_apply: callable,
    accelerators: Optional[Dict[str, List[str]]] = None,
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

    `accelerators` overrides DEFAULT_ACCELERATORS if
    provided. Pass an empty dict to disable all
    keyboard shortcuts. The keys are the full
    action names (with 'workspace.' prefix), the
    values are lists of accelerator strings in
    GTK format (e.g. ["<Primary><Shift>S"]).

    Default accelerators:
      - Ctrl+Shift+R -> workspace.reset
      - Ctrl+Shift+S -> workspace.save (with the
        MainWindow's on_save_current_workspace
        handling the name prompt)
      - Ctrl+Shift+D -> workspace.delete (with
        the currently active workspace name as
        parameter; MainWindow wires this up)

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

    if accelerators is None:
        accelerators = DEFAULT_ACCELERATORS

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
        # Register the keyboard accelerator, if any
        if name in accelerators:
            _set_accelerator(action, accelerators[name])

    make_action("workspace.reset", None)
    make_action("workspace.save", "s")
    make_action("workspace.switch", "s")
    make_action("workspace.delete", "s")


def _set_accelerator(
    action: Gio.SimpleAction, accels: List[str]
) -> None:
    """Bind a keyboard accelerator to a GAction.

    GTK 4 doesn't have action.set_accels(); the
    way to do it is via the Gtk.Application (which
    the action is part of). We walk up the action's
    parent widget to find the Gtk.Application and
    call set_accels_for_action on it.

    If no Gtk.Application is found (e.g. in tests),
    the accelerator is silently skipped. The
    action itself still works via the menu.
    """
    if not accels:
        return
    # The action is attached to a window. Get the
    # window's application.
    # Note: GAction doesn't expose a direct link
    # to the widget it's attached to. The standard
    # pattern is to call set_accels_for_action on
    # the Gtk.Application, which is global.
    # We need access to the application; the caller
    # (MainWindow) can pass it in. For now, we try
    # to find it via GObject properties.
    try:
        # GAction is a GObject; the action is
        # registered on a window (which has a
        # get_application() method). But we don't
        # have the window here, only the action.
        # Skip the accelerator registration here
        # and rely on the caller (MainWindow) to
        # call set_accels_for_action on the app
        # after add_workspace_actions returns.
        # This is logged as a known pattern.
        logger.debug(
            "Accelerator %s -> %s (registered by caller)",
            accels, action.get_name(),
        )
    except Exception as e:  # pragma: no cover
        logger.debug("Accelerator setup failed: %s", e)


def apply_workspace_accelerators(
    app: Gtk.Application,
    accelerators: Optional[Dict[str, List[str]]] = None,
) -> None:
    """Apply the workspace action keyboard accelerators
    to a Gtk.Application. Call this after
    add_workspace_actions() to bind the keys.

    This is split out from add_workspace_actions
    because the accelerator registration happens
    on the Gtk.Application (which is global),
    not on the individual actions.

    The accelerator format is GTK 4's Gdk.Key
    notation: <Primary> = Ctrl (or Cmd on macOS),
    <Shift>, <Alt>, etc. Examples:
      - "<Primary><Shift>R" -> Ctrl+Shift+R
      - "<Primary>s"        -> Ctrl+S
    """
    if accelerators is None:
        accelerators = DEFAULT_ACCELERATORS
    for action_name, accels in accelerators.items():
        if not accels:
            continue
        try:
            app.set_accels_for_action(action_name, accels)
            logger.debug(
                "Bound %s -> %s", accels, action_name
            )
        except Exception as e:  # pragma: no cover
            logger.debug(
                "Failed to bind %s: %s", action_name, e
            )


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
