# Splash screen placeholder

This directory contains the **placeholder** splash screen assets
for Pires Forge. The current files are a starting point — they
are committed so the directory structure is reviewable, but the
runtime splash window is **not yet wired up** in
`rayforge/app.py:startup()`.

## Files

| File | Purpose |
| :--- | :------ |
| `splash.svg` | Vector source (800×500, 16:10). The build pipeline should convert this to a PNG of the same size for the GTK splash window. |
| `splash.png` | (to be generated) The PNG that the application actually loads. |
| `README.md` | This file. |

## Design

- **Background**: black-to-dark-gray vertical gradient.
- **App icon**: centered top, 256×256, reuses the spark-burst
  motif from `rayforge/resources/icons/org.piresforge.pires-forge.svg`.
- **App name**: "Pires Forge" in light gray, large weight.
- **Tagline**: "2D CAD, G-code sender, and laser control".
- **Status line**: "vX.Y.Z · loading…" (updated at runtime).

## Wiring up the splash window

The GTK 4 / Libadwaita idiom for a splash screen is to show a
borderless `Gtk.Window` during application startup, then close
it once the main window is ready. The minimal skeleton is:

```python
# rayforge/app.py (add to startup())
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GdkPixbuf

class SplashWindow(Gtk.Window):
    def __init__(self, version: str):
        super().__init__()
        self.set_default_size(800, 500)
        self.set_decorated(False)

        # Load the splash image
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            "/path/to/splash.png",
            width=800, height=500,
            preserve_aspect_ratio=False,
        )
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        self.set_child(image)
```

Call this from `Application.do_startup()` and `do_activate()`
(see `rayforge/app.py`).

## Generating the runtime PNG

```bash
# From the project root:
rsvg-convert -w 800 -h 500 data/splash/splash.svg \
    -o data/splash/splash.png
```

The `rsvg-convert` binary is part of the `librsvg2-bin` package
on Debian/Ubuntu and is already a dependency in the
`pixi.lock`.

## Next steps

- [ ] Generate `splash.png` from `splash.svg` and commit it
- [ ] Add a `rayforge/ui_gtk/splash.py` module with the
      `SplashWindow` class
- [ ] Wire up in `rayforge/app.py:startup()` to show on cold
      start (skip on warm restart)
- [ ] Animate the "loading…" line during long initial loads
      (e.g. while addons are being discovered)
- [ ] Add a `--no-splash` command-line flag for power users
- [ ] Optional: add a real progress bar driven by the
      `Application.startup_progress` signal
