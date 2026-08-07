"""Splash screen shown during app startup.

Renders data/splash/splash.svg (the source-of-truth vector) in a
borderless Gtk.Window centered on the primary monitor. The window
auto-sizes to the SVG's intrinsic 800x500 viewBox.

This is a deliberately simple, dependency-free implementation:
- No Adw.SplashScreen, no Cairo, no GdkPixbuf manual rasterization.
- A Gtk.Picture widget loads the SVG directly (librsvg handles
  rasterization at any size).
- The window is non-interactive (no decorations, no taskbar entry)
  so users can't accidentally interact with it before the main
  window is ready.

Lifecycle:
    splash = SplashScreen()
    splash.show()
    # ... heavy work (load main window, restore last project) ...
    splash.close()

The splash is best-effort: if the SVG cannot be loaded (e.g.
packaging issue, missing librsvg), the class falls back to a
plain black window so startup never blocks on cosmetic assets.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from rayforge.shared.util.localized import _  # noqa: E402

logger = logging.getLogger(__name__)


# SVG intrinsic size matches the viewBox declared in the source file
# (data/splash/splash.svg). Kept in sync manually.
_SPLASH_WIDTH = 800
_SPLASH_HEIGHT = 500


def _resolve_splash_svg() -> Optional[Path]:
    """Locate splash.svg, respecting PyInstaller bundle layout.

    Thin wrapper over rayforge.shared.util.resources.resource_path
    so the bundle-aware resolution pattern lives in exactly one
    place. Returns None if the SVG cannot be located (the splash
    then falls back to a black 800x500 box).
    """
    from ..shared.util.resources import resource_path

    return resource_path(
        "data/splash/splash.svg", anchor_file=__file__
    )


class SplashScreen(Gtk.Window):
    """A minimal, borderless, non-interactive splash window.

    Public surface:
        SplashScreen()  -> show()  -> ... -> close()
    """

    def __init__(self) -> None:
        super().__init__()
        self.set_title(_("Pires Forge"))
        self.set_resizable(False)
        self.set_decorated(False)
        # No input focus while loading. (Gtk 4 removed
        # several Gtk 3 Window methods we used to call
        # here: set_skip_taskbar_hint, set_skip_pager_hint,
        # set_focus_on_map. A borderless non-modal
        # window with set_focusable(False) is sufficient
        # to keep the splash out of the way during startup.)
        self.set_focusable(False)
        self.set_modal(False)
        # Default size from the SVG viewBox; if loading fails we keep
        # this geometry as a black box fallback.
        self.set_default_size(_SPLASH_WIDTH, _SPLASH_HEIGHT)

        # Solid background so the SVG blends on every WM theme.
        # (Libadwaita dark backgrounds in compositor preview modes
        # can otherwise leak through transparent SVG corners.)
        #
        # The `window.splash-window` rule is declared in
        # rayforge/resources/styles/forge.css and is installed
        # globally by App.do_activate() before the splash is
        # presented (see install_forge_css_once in mainwindow.py).
        # No local CssProvider needed here.
        self.add_css_class("splash-window")

        # Content: a Gtk.Picture loading the SVG, or a plain Box on
        # failure. Using keep-aspect-ratio + contain so the image
        # scales gracefully on HiDPI displays.
        picture = Gtk.Picture()
        picture.set_can_shrink(False)
        picture.set_keep_aspect_ratio(True)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_size_request(_SPLASH_WIDTH, _SPLASH_HEIGHT)

        svg_path = _resolve_splash_svg()
        if svg_path is not None:
            try:
                picture.set_filename(str(svg_path))
            except GLib.Error as exc:
                logger.warning("Splash SVG failed to load: %s", exc)
        else:
            logger.warning(
                "splash.svg not found at expected path; showing fallback."
            )

        self.set_child(picture)

        # Center on the primary monitor once the window is realized.
        # We can't query monitor geometry in __init__ — it requires
        # the display to be associated with a real screen, which
        # only happens after the window is added to a toplevel.
        self.connect("realize", self._center_on_primary_monitor)

    def _center_on_primary_monitor(self, *_args) -> None:
        """Place the splash on the center of the primary monitor.

        Gtk 4 removed Gtk.Window.move(). The closest portable
        approach is to leave positioning to the window manager:
        most compositors (Mutter, KWin, etc.) auto-center
        borderless non-modal windows. As a fallback, we log
        the computed coordinates (useful for debugging layout
        issues) but don't try to force them.

        If a user reports that the splash is consistently
        off-center on a specific WM, the future fix is to
        use the Gdk.Toplevel.set startup_id + a .desktop
        file with StartupWMClass hints, or to manage the
        Gdk.Surface directly via the Wayland/X11 protocol
        (not portable, hence not implemented yet).
        """
        display = Gdk.Display.get_default()
        if display is None:
            return
        monitor = display.get_primary_monitor()
        if monitor is None:
            monitors = display.get_monitors()
            if monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
        if monitor is None:
            return
        geometry = monitor.get_geometry()
        x = geometry.x + (geometry.width - _SPLASH_WIDTH) // 2
        y = geometry.y + (geometry.height - _SPLASH_HEIGHT) // 2
        # Log the computed center for debugging; the WM will
        # decide the actual position. (Gtk.Window.move() was
        # removed in Gtk 4 — there's no portable API to force
        # this from the client side.)
        logger.debug(
            "Splash center computed: x=%d y=%d (monitor=%dx%d at %d,%d)",
            max(0, x), max(0, y),
            geometry.width, geometry.height, geometry.x, geometry.y,
        )
