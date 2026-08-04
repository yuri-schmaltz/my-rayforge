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


# Transition types we want to short-circuit to NONE when the user
# has prefers-reduced-motion enabled. Gtk.StackTransitionType.NONE
# doesn't exist; we use CROSSFADE as the least-distracting fallback
# and set duration to 0 so the swap is effectively instant.
_NO_MOTION_STACK_TRANSITION = "CROSSFADE"
_NO_MOTION_REVEALER_TRANSITION = "NONE"


def apply_motion_preference_recursive(widget: Gtk.Widget) -> None:
    """Disable animations on a widget and all its descendants.

    Walks the widget tree and, on every Gtk.Stack / Gtk.Revealer it
    finds, sets the transition duration to 0 (or picks the most
    subtle transition type). Stacks and Revealers are the only
    GTK4 widgets with a public transition API; custom Cairo
    animations would need to be handled separately by their owners.

    Safe to call on any widget. Idempotent.
    """
    if not prefers_reduced_motion():
        return
    _kill_motion_on(widget)


def _kill_motion_on(widget: Gtk.Widget) -> None:
    """Internal walker — kill motion on this widget and all children."""
    if isinstance(widget, Gtk.Stack):
        try:
            from gi.repository import Gtk as _Gtk

            widget.set_transition_type(
                getattr(_Gtk.StackTransitionType, _NO_MOTION_STACK_TRANSITION)
            )
            widget.set_transition_duration(0)
        except (AttributeError, TypeError):
            pass
    elif isinstance(widget, Gtk.Revealer):
        try:
            from gi.repository import Gtk as _Gtk

            widget.set_transition_type(
                getattr(
                    _Gtk.RevealerTransitionType, _NO_MOTION_REVEALER_TRANSITION
                )
            )
        except (AttributeError, TypeError):
            pass
    child = widget.get_first_child()
    while child is not None:
        _kill_motion_on(child)
        child = child.get_next_sibling()


def install_motion_preference_listener(window: Gtk.Window) -> None:
    """React to runtime changes in the 'reduce motion' setting.

    Connects to Gtk.Settings' 'gtk-enable-animations' property so
    that toggling the system preference (e.g. via GNOME Control
    Center) immediately re-applies the motion preference across the
    whole window's widget tree. The listener is installed once;
    calling it again is a no-op.
    """
    settings = Gtk.Settings.get_default()
    if settings is None:
        logger.debug("No Gtk.Settings — cannot listen for motion changes")
        return
    # We can't use a normal 'notify::gtk-enable-animations' connection
    # from Python without leaking handlers, so use connect_after to
    # avoid recursion and a hasattr check to make this idempotent.
    if getattr(window, "_motion_listener_installed", False):
        return
    window._motion_listener_installed = True

    def _on_anim_setting_changed(_settings, _pspec):
        apply_motion_preference_recursive(window)

    settings.connect("notify::gtk-enable-animations", _on_anim_setting_changed)
    # Apply once at install time so existing widgets are correct.
    apply_motion_preference_recursive(window)
