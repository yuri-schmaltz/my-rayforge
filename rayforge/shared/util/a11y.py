"""Accessibility helpers — ARIA-style labels, roles, descriptions.

GTK 4 exposes the AT-SPI accessibility interface via
Gtk.Accessible. For each widget we set:

  - accessible-role: the role (e.g. BUTTON, LABEL, TEXT)
  - accessible-label: a short string the screen reader
    announces (e.g. \"Save\")
  - accessible-description: an optional longer description
    (e.g. \"Save the current document\")
  - tooltip-text: the mouse hover hint (GTK shows this for
    sighted users, but AT-SPI can read it too)

This module is a thin wrapper that bundles all four
operations into one call, with the option to mark a
widget as having a 'live region' (so the screen reader
re-announces changes — useful for status bar updates,
progress bars, etc.).

The set_a11y_label function is idempotent: calling it
twice with the same args is a no-op. This matters
because some widgets are constructed once but their
label changes over time (e.g. the mode badge goes
'Idle' -> 'Designing' -> 'Sending').

Why this file? Without it, each call site would need to
remember 4+ methods + the AT-SPI property names. The
helpers centralize the pattern, make the code shorter,
and provide one place to swap implementations (e.g. if
we move to a different a11y bridge later).
"""
from __future__ import annotations

from typing import Optional

from gi.repository import Gtk


# AT-SPI roles. GTK 4 maps these via the AccessibleRole
# enum. The constants here are the common ones; add more
# as needed.
ROLE_BUTTON = Gtk.AccessibleRole.BUTTON
ROLE_LABEL = Gtk.AccessibleRole.LABEL
# GTK 4 renamed the Gtk 3 'TEXT' role to 'TEXT_BOX'
# (value 68). Use it for editable text widgets
# (GtkEntry, GtkTextView, etc.).
ROLE_TEXT = Gtk.AccessibleRole.TEXT_BOX
ROLE_CHECKBOX = Gtk.AccessibleRole.CHECKBOX
ROLE_TOGGLE_BUTTON = Gtk.AccessibleRole.TOGGLE_BUTTON
ROLE_PROGRESS_BAR = Gtk.AccessibleRole.PROGRESS_BAR
ROLE_SEPARATOR = Gtk.AccessibleRole.SEPARATOR
ROLE_TAB = Gtk.AccessibleRole.TAB
ROLE_TAB_PANEL = Gtk.AccessibleRole.TAB_PANEL
ROLE_TOOLBAR = Gtk.AccessibleRole.TOOLBAR
ROLE_GROUP = Gtk.AccessibleRole.GROUP
ROLE_STATUS = Gtk.AccessibleRole.STATUS
ROLE_DIALOG = Gtk.AccessibleRole.DIALOG


def set_a11y_label(
    widget: Gtk.Widget,
    label: str,
    *,
    description: Optional[str] = None,
    role: Optional[Gtk.AccessibleRole] = None,
    tooltip: Optional[str] = None,
) -> None:
    """Set accessibility metadata on a widget.

    Args:
        widget: The Gtk.Widget to annotate.
        label: A short string the screen reader announces
            (e.g. \"Save\", \"Open\"). Required.
        description: An optional longer string for context.
        role: The AT-SPI role. If unset, GTK infers from
            the widget type.
        tooltip: Optional tooltip text. Convenience field
            — sets the widget's tooltip AND the AT-SPI
            description if description is None.
    """
    if role is not None:
        # set_accessible_role is on the Accessible interface
        # that most Gtk.Widget subclasses implement.
        try:
            widget.set_accessible_role(role)
        except Exception:  # pragma: no cover
            pass
    try:
        widget.set_accessible_label(label)
    except Exception:  # pragma: no cover
        pass
    if description is not None:
        try:
            widget.set_accessible_description(description)
        except Exception:  # pragma: no cover
            pass
    if tooltip is not None:
        widget.set_tooltip_text(tooltip)
        # If no explicit description, use the tooltip.
        if description is None:
            try:
                widget.set_accessible_description(tooltip)
            except Exception:  # pragma: no cover
                pass


def mark_live_region(
    widget: Gtk.Widget, *, polite: bool = True
) -> None:
    """Mark a widget as a live region.

    Live regions tell the screen reader to re-announce
    the widget's contents whenever they change. Useful
    for status bars, progress bars, and toasts.

    Args:
        widget: The widget to mark.
        polite: True (default) for AT-SPI 'polite' live
            region (announce at next pause, no interrupt).
            False for 'assertive' (interrupt current speech).
    """
    # GTK 4 doesn't have a set_accessible_live API; we use
    # AT-SPI properties via the GObject property system.
    # 'accessible-live' is the property name; values are
    # 'polite' / 'assertive' / 'off'.
    try:
        widget.update_property(
            [Gtk.AccessibleProperty.LIVE], [int(polite)]
        )
    except Exception:  # pragma: no cover
        # Older GTK or different bridge: skip silently.
        pass
