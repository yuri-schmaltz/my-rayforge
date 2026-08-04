# Pires Forge — Developer Guide

This guide is for **contributors** — people extending,
patching, or building Pires Forge. If you're an end user,
see [USER_MANUAL.md](USER_MANUAL.md) instead.

Pires Forge is a Python / GTK 4 desktop app. It started
as a fork of [Rayforge](https://github.com/barebaric/rayforge);
the codebase is roughly 60k LOC of Python plus 5k LOC of
GLSL (the canvas shaders).

---

## Table of contents

1. [Codebase layout](#1-codebase-layout)
2. [Development setup](#2-development-setup)
3. [Architecture](#3-architecture)
4. [Adding an operation](#4-adding-an-operation)
5. [Adding an addon](#5-adding-an-addon)
6. [i18n workflow](#6-i18n-workflow)
7. [Performance work](#7-performance-work)
8. [Accessibility](#8-accessibility)
9. [Testing](#9-testing)
10. [Release process](#10-release-process)

---

## 1. Codebase layout

```
rayforge/
  app.py                # Application entry point
  context.py            # Process-wide context (singleton)
  config.py             # User config (YAML-backed)
  const.py              # App constants (APP_NAME, etc.)
  usage.py              # Umami cloud-telemetry tracker

  core/                 # Domain model
    doceditor/          # Document + layer + workflow + ops
    machine/            # Machine driver + connection
    pipeline/           # G-code generation
    artifact/           # Computation cache
    vectorization_spec.py
    registration.py     # Strategy registry hookups

  ui_gtk/               # GTK 4 UI
    mainwindow.py       # Top-level window
    main_menu.py        # Menu model
    actions.py          # Gio.SimpleAction registration
    status_bar.py       # Bottom status bar
    coordinate_bar.py   # Top coordinate readout
    command_palette.py  # Ctrl+Shift+P overlay
    walkthrough.py      # First-run 5-card dialog
    coach_marks.py      # Per-zone first-interaction popovers
    insights_panel.py   # Help > Insights
    panel_manager.py    # Right + bottom panel show/hide
    doceditor/          # Doc editor UI
    machine/            # Machine settings UI
    settings/           # App settings UI
    shared/             # Shared UI utilities (a11y, keyboard)

  addon_mgr/            # Addon discovery + lifecycle
  builtin_addons/       # Built-in addons
  doceditor/            # Layout strategies (auto / pack)
  shared/
    util/               # local_tracker, localized, a11y
    tasker.py           # Background task runner
  util/
    tracing.py          # In-process perf tracer
    benchmarks.py       # CLI micro-benchmarks
    i18n_audit.py       # Static analyzer for missing _()

  locale/               # .pot / .po files
  resources/            # icons, .css, GLSL

tests/
  core/                 # Unit tests for the domain model
  addon_mgr/            # Addon manager tests
  gui/                  # Smoke tests for the main window
  conftest.py           # Pytest fixtures
```

---

## 2. Development setup

### 2.1 Pixi (recommended)

```sh
# Install pixi: https://pixi.sh
git clone https://github.com/yuri-schmaltz/pires-forge
cd pires-forge
pixi install              # creates .pixi/ with all deps
pixi run pires-forge       # launches the app
pixi run pires-forge-test  # runs the test suite
```

### 2.2 Manual (system packages)

```sh
# Debian / Ubuntu
sudo apt install \
  python3-gi python3-gi-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 \
  python3-pip python3-venv

python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2.3 Editor setup

- **Python**: VS Code / PyCharm / Neovim with `pyright`
- **GLSL**: any editor with shader-language support
- **CSS**: any editor (we use 4-space indent)
- **pre-commit** (optional): `pip install pre-commit && pre-commit install`

### 2.4 Verifying a build

```sh
pixi run pires-forge-test
python3 -m rayforge.util.benchmarks    # performance baseline
python3 -m rayforge.util.i18n_audit    # i18n coverage
```

---

## 3. Architecture

### 3.1 Process model

Pires Forge is a single-process GTK 4 app. The
`Application` (in `rayforge/app.py`) creates the
`MainWindow`; the window drives the document editor and
the G-code pipeline.

The main UI thread runs the GTK event loop. Heavy work
(G-code generation, image vectorization, machine
communication) runs in background tasks managed by
`rayforge/shared/tasker.py`. The `tasker` posts results
back to the main thread via `GLib.idle_add` or
`AsyncResult`.

### 3.2 Context

`rayforge/context.py` is the process-wide singleton. It
holds:

- The artifact store (computation cache)
- The addon manager
- The plugin manager (pluggy)
- The config

`init_context()` must be called before any UI. It scans
addon directories, loads worker entry points (always) and
frontend entry points (only if `headless=False`).

### 3.3 Document model

The `Doc` (in `rayforge/doceditor/`) is a tree:

```
Doc
  ├── Layer 0
  │     ├── Workflow
  │     │     ├── Operation 1 (Cut)
  │     │     ├── Operation 2 (Engrave)
  │     │     └── Operation 3 (Score)
  │     └── Items (the actual paths to cut)
  ├── Layer 1
  │     └── ...
  └── Workpiece (the physical stock)
```

Each layer has its own workflow. Operations are applied
in order. The document is serialized to YAML for save
/ load.

### 3.4 Pipeline

The pipeline (`rayforge/pipeline/`) converts a `Doc` +
machine config into G-code. The pipeline is staged:

1. **Render** — produce a 2D representation of the doc
   (vertices, no styling).
2. **Ops** — for each operation, generate the moves
   (path, power, speed).
3. **Encode** — turn the ops into the machine's native
   dialect (GRBL, Ruida, etc.).

Each stage caches its output in the artifact store so
re-running the pipeline (e.g. after a small doc edit) is
fast.

### 3.5 UI

The UI is GTK 4 + libadwaita. The main window is a
vertical box:

```
vbox
  ├── toolbar
  ├── coordinate_bar
  ├── canvas_overlay
  │     ├── canvas (2D)
  │     ├── canvas3d (3D, Adw.ViewStack)
  │     └── right_pane (Adw.ViewStack)
  ├── bottom_panel
  └── status_bar
```

The `PanelManager` (`rayforge/ui_gtk/panel_manager.py`)
coordinates the right + bottom panel show/hide across the
three layout presets (default, compact, expanded).

### 3.6 Addons

Addons extend the app via pluggy hooks:

```python
# my-addon/my_addon.py
from rayforge.core.registration import hookimpl

@hookimpl
def rayforge_init(context):
    """Called once at app start."""
    pass

@hookimpl
def get_ops():
    """Return a list of operation classes this addon provides."""
    return [MyCustomOp]

@hookimpl
def get_frontend():
    """Return a list of GTK widgets to add to the UI."""
    return [MyFrontendPanel]
```

See `rayforge/addon_mgr/` for the full API.

---

## 4. Adding an operation

Operations live in `rayforge/core/ops/`. Each is a class
that implements the `Operation` protocol:

```python
from dataclasses import dataclass
from rayforge.core.ops.op import Op

@dataclass
class MyOp(Op):
    speed: float = 1000.0
    power: float = 0.5

    def render(self, context):
        """Yield Vertex objects for the move path."""
        for vertex in self._path:
            yield vertex

    def to_dict(self):
        return {"speed": self.speed, "power": self.power}

    @classmethod
    def from_dict(cls, d):
        return cls(speed=d["speed"], power=d["power"])
```

Register the op in `rayforge/core/registration.py` so
the UI knows about it.

---

## 5. Adding an addon

A minimal addon has this layout:

```
my-addon/
  manifest.yaml        # addon metadata
  __init__.py          # the hook implementations
```

`manifest.yaml`:

```yaml
name: my-addon
version: 0.1.0
description: Does the thing
author: You <you@example.com>
provides:
  worker: my_addon:rayforge_init
  frontend: my_addon:get_frontend
```

Drop the directory into the addons folder (or use
**Settings → Addons → Install from disk**). The addon
manager picks it up on next launch.

See `rayforge/builtin_addons/rayforge-addon-laser/` for
a full example.

---

## 6. i18n workflow

### 6.1 Marking strings

All user-facing strings must be wrapped in `_()`:

```python
from rayforge.shared.util.localized import _

label = Gtk.Label(label=_("Save"))
label.set_text(_("Open file: %s") % filename)
```

The `_` function is patched at startup to delegate to
the per-addon gettext domains (see
`rayforge/shared/util/localized.py`).

### 6.2 Generating the .pot file

```sh
pixi run i18n-extract
# or, manually:
xgettext --language=Python --keyword=_ \
  --from-code=UTF-8 \
  --output=rayforge/locale/rayforge.pot \
  rayforge/**/*.py
```

### 6.3 Updating translations

For each `.po` file in `rayforge/locale/<lang>/`:

```sh
msgmerge --update \
  rayforge/locale/de/LC_MESSAGES/rayforge.po \
  rayforge/locale/rayforge.pot
```

Then translate the new strings in the `.po` file
(using [Poedit](https://poedit.net/) or any editor).

### 6.4 Auditing missing markers

```sh
python3 -m rayforge.util.i18n_audit --format text
# or for CI:
python3 -m rayforge.util.i18n_audit --format json
```

The audit is advisory, not a build blocker.

---

## 7. Performance work

### 7.1 Tracing

The tracer (`rayforge/util/tracing.py`) records
`(name, duration_ns)` pairs. Wrap hot code:

```python
from rayforge.util.tracing import get_tracer

tracer = get_tracer()
with tracer.span("pipeline.render"):
    self._render_step()
```

Enable with `RAYFORGE_TRACE=1`. The report is dumped
to stderr on exit:

```sh
RAYFORGE_TRACE=1 pixi run pires-forge 2> trace.log
```

The tracer is a singleton, disabled by default, and
adds <1µs per event.

### 7.2 Benchmarks

```sh
python3 -m rayforge.util.benchmarks
python3 -m rayforge.util.benchmarks --output bench.json
python3 -m rayforge.util.benchmarks --compare old.json
```

Output is a mean/p95/n table plus optional JSON for
diffing between runs.

### 7.3 Profiling

For deeper work, use `cProfile` or `py-spy`:

```sh
py-spy record -o profile.svg -- pixi run pires-forge
```

### 7.4 Hot paths (where to look first)

- `rayforge/pipeline/encoder/` — G-code generation
- `rayforge/image/lightburn/importer.py` — LB importer
- `rayforge/ui_gtk/doceditor/canvas.py` — 2D canvas render
- `rayforge/addon_mgr/addon_manager.py` — addon discovery

---

## 8. Accessibility

Pires Forge exposes the AT-SPI interface via
`Gtk.Accessible`. Use the helpers in
`rayforge/shared/util/a11y.py`:

```python
from rayforge.shared.util.a11y import set_a11y_label, mark_live_region

set_a11y_label(my_button,
    label=_("Save"),
    description=_("Save the current document"),
    role=Gtk.AccessibleRole.BUTTON,
)

mark_live_region(status_bar, polite=True)
```

### 8.1 Testing

Run with the screen reader of your choice:

```sh
orca &     # GNOME
# or
echo "Run orca and then launch pires-forge"
pixi run pires-forge
```

Verify each new widget has a non-empty accessible label
by running `tests/gui/` (see [Section 9](#9-testing)).

---

## 9. Testing

### 9.1 Unit tests

```sh
pytest tests/core/ tests/addon_mgr/ -v
```

### 9.2 GUI smoke tests

```sh
pytest tests/gui/ -v
```

These tests launch a real `MainWindow` in offscreen
mode and walk the widget tree. They verify:

- The window constructs
- The major surfaces are present (toolbar, status bar,
  coordinate bar, right pane, bottom panel, canvas)
- The accessibility labels are reachable

### 9.3 Writing a new GUI test

Add to `tests/gui/__init__.py`:

```python
def test_my_widget_present(self):
    win = _launch_main_window()
    try:
        widgets = _collect_widgets(win)
        found = any("my-css-class" in w.get_css_classes() for w in widgets)
        assert found
    finally:
        win.destroy()
```

### 9.4 Performance regression test

```sh
python3 -m rayforge.util.benchmarks --output bench.json
# Compare against main:
git checkout main
python3 -m rayforge.util.benchmarks --compare bench.json
```

---

## 10. Release process

### 10.1 Versioning

Pires Forge follows [SemVer](https://semver.org/).
The current version is in `pyproject.toml` and
`rayforge/const.py`.

### 10.2 Cutting a release

1. Update the version in `pyproject.toml` and
   `rayforge/const.py`.
2. Update `NEWS.md` with the changelog entry.
3. Tag the commit: `git tag v1.2.3`
4. Build the wheel: `pixi run build`
5. Push the tag: `git push origin v1.2.3`
6. Build artifacts are uploaded by CI.

### 10.3 Hotfix release

Same as a regular release, but on a `hotfix/v1.2.4` branch
cut from the `v1.2.3` tag. The hotfix branch is merged
back to main after release.

---

## License

Pires Forge is open-source software, licensed under the
GPL-3.0. See [LICENSE](LICENSE) for the full text.

## Community

- **GitHub**: [yuri-schmaltz/pires-forge](https://github.com/yuri-schmaltz/pires-forge)
- **Issues**: file bugs and feature requests on GitHub.
- **Discussions**: GitHub Discussions for Q&A and
  show-and-tell.

## See also

- [USER_MANUAL.md](USER_MANUAL.md) — end-user manual
- [README.md](README.md) — quick-start
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution rules
