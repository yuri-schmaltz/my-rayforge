"""Accessibility helpers.

GTK 4 with Libadwaita exposes most widgets to AT-SPI (the Linux
accessibility bus) automatically: Gtk.Button is reported as
ATK_ROLE_PUSH_BUTTON, Gtk.ToggleButton as CHECK_BOX, etc. The
attribute that often goes missing is the *accessible label* — what
a screen reader announces when focus lands on a button. GTK only
derives this from the visible label, so icon-only buttons
(`Gtk.Button(child=icon_widget)`) are announced as "button" with
no name, which is unusable for non-sighted users.

This module offers two helpers:

    propagate_tooltip_to_accessible_label(widget)
        One-shot setter: copies the widget's existing tooltip text
        into the AT-SPI accessible label. Safe to call on any
        widget; no-op if the widget has no tooltip or if the GTK
        build doesn't support the property update API.

    prefers_reduced_motion() -> bool
        Returns True if the user has enabled the system-wide
        'reduce motion' preference. Used to disable expensive
        transition animations on the main UI for vestibular
        sensitivity.

We don't (yet) ship a full a11y audit pass — the goal of this
module is to make the most common icon-only buttons in the
toolbar and main menus announce correctly without requiring the
caller to do anything special.
"""
from __future__ import annotations

import logging
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

logger = logging.getLogger(__name__)


def propagate_tooltip_to_accessible_label(widget: Gtk.Widget) -> None:
    """Copy the widget's tooltip into its accessible label.

    If the widget has no tooltip text set, this is a no-op. If the
    GTK build doesn't support the AccessibleProperty update API
    (older 4.x builds), the call is silently skipped — the tooltip
    will still be read by most screen readers via the legacy
    ATK_TOOLTIPS mechanism.
    """
    tooltip = widget.get_tooltip_text()
    if not tooltip:
        return
    try:
        # Gtk 4.10+: AccessibleProperty is the modern AT-SPI label
        # channel. On older builds the enum value isn't bound, so
        # the AttributeError is caught below.
        from gi.repository import Gtk as _Gtk  # noqa: F401

        widget.update_property(
            [_Gtk.AccessibleProperty.LABEL], [tooltip]
        )
    except (AttributeError, TypeError) as exc:
        # Fall back to the legacy ATK description API. The result is
        # not perfectly equivalent (description != label) but it
        # gives screen readers *something* to announce.
        try:
            widget.get_accessible_object().set_description(tooltip)
        except Exception:
            logger.debug(
                "Could not set accessible label on %s: %s",
                widget.__class__.__name__,
                exc,
            )


def prefers_reduced_motion() -> bool:
    """Return True if the user has enabled system 'reduce motion'.

    Reads Gdk.Settings 'gtk-enable-animations' (a per-Wayland/X11
    setting driven by the system 'reduce motion' preference on
    GNOME, KDE, and macOS-Cinnamon). When the system disables
    animations, callers should switch to non-animated transitions.
    """
    try:
        seat = Gdk.Display.get_default().get_default_seat()
        if seat is None:
            return False
        device = seat.get_keyboard()
        if device is None:
            return False
        settings = device.get_settings() if hasattr(device, "get_settings") else None
        # The above path doesn't exist in all GTK 4.x; the canonical
        # way is Gtk.Settings.get_default(). Some GTK versions also
        # expose this via Gdk.Display.
    except Exception:
        pass
    settings = Gtk.Settings.get_default()
    if settings is None:
        return False
    try:
        return not settings.get_property("gtk-enable-animations")
    except (TypeError, AttributeError):
        return False


def announce(message: str, priority: str = "normal") -> None:
    """Best-effort screen-reader announcement.

    GTK doesn't have a stable 'live region' API yet; the closest
    cross-platform mechanism is to flash a transient toast (which
    screen readers do pick up if the user is in a watch-toasts
    mode). This helper is a no-op stub for now; the real
    implementation will land in a follow-up once GTK 4.14+
    AccessibleAnnouncement is more widely available.
    """
    logger.debug("a11y.announce(%r, %r) — stub", message, priority)
