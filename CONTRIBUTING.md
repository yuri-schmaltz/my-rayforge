# Contributing to Pires Forge

Thanks for your interest in contributing to
[Pires Forge](https://github.com/yuri-schmaltz/pires-forge)! This
document explains how to set up a development environment, how the
contribution workflow works, and what we expect from PRs.

If you only want to **report a bug or request a feature** (no code
involved), see [SUPPORT.md](SUPPORT.md).

## About this project

Pires Forge is an independent, single-maintainer fork of the
[Rayforge](https://github.com/barebaric/rayforge) project. The fork:

- Is **production-ready, security-hardened, and free of monetization
  cruft** (no Patreon / affiliate links / upsells).
- Keeps the **Python module path** (`rayforge/`) and **addon API**
  (`rayforge-addon-*`) identical to upstream for compatibility with
  the existing ecosystem.
- Renames the **user-visible identity** (display name, AppStream ID,
  Debian package, .desktop, .metainfo) from `Rayforge` to
  `Pires Forge`.
- Has its **own release cadence** and **update check is off by
  default**.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold it. Please report unacceptable
behaviour to the maintainer at <security@yuri-schmaltz.dev> — please
mention "Code of Conduct" in the subject line.

## Development setup

### Prerequisites

- **Python 3.11+** (the project pins `python = ">=3.11"` in `pixi.toml`)
- **pixi** — [installation instructions](https://pixi.sh/latest/)
- **Git** (any recent version)
- On Linux, the system packages that `pixi.toml` resolves via conda
  (cairo, gtk4, libvips, librsvg, poppler, openslide, etc.) are
  installed automatically when you run `pixi install`. No manual
  `apt-get install` needed for the `default` environment.
- On macOS, pixi handles the system dependencies via Homebrew under
  the hood.

### First-time setup

```bash
# Clone the fork
git clone https://github.com/yuri-schmaltz/pires-forge.git
cd pires-forge

# Install all dependencies (first run takes ~10 minutes)
pixi install

# Verify the install
pixi run test --collect-only
```

### Run the app

```bash
pixi run rayforge
```

This starts the GTK4 GUI in a window. The app uses an X11/Wayland
display; if you're running headless, see the headless smoke test
section below.

### Run the tests

```bash
# Backend tests (no GTK required)
pixi run test

# All tests including UI (requires a display)
pixi run uitest

# Coverage report
pixi run coverage
```

### Run the linters

```bash
pixi run lint
pixi run format
```

## Project layout

```
rayforge/                 # Main Python package
  builtin_addons/         # Built-in addons (laser, materials, post-proc, etc.)
  core/                   # Core models (doc, workpiece, step, etc.)
  doceditor/              # Document editor
  machine/                # Machine drivers (GRBL, Marlin, Ruida, etc.)
  pipeline/               # Compute pipeline (ops, transformers, producers)
  ui_gtk/                 # GTK4 UI
  ...
hooks/                    # PyInstaller hooks (for .exe / .dmg build)
typings/                  # Type stubs (pyright)
data/                     # .desktop, .metainfo, MIME types, icons
debian/                   # .deb packaging
docs/                     # User-facing documentation
scripts/                  # Build, dev, and release scripts
tests/                    # Test suite
```

## Contribution workflow

1. **Open an issue first.** Describe the change you want to make.
   We discuss design before code.
2. **Fork the repo** and create a topic branch (e.g. `fix/load-svg-svg`).
3. **Make your change** in the worktree. Follow the coding style
   (ruff format, see `.pre-commit-config.yaml` for hooks).
4. **Add tests** for the new behavior. Run `pixi run test` and
   `pixi run lint` locally before pushing.
5. **Open a pull request** against `main`. The PR description should
   explain **what** changed and **why**, and reference the issue it
   closes.
6. **Address review feedback**. We may request changes.

## Coding conventions

- **Line length**: 79 characters (configured in `pyproject.toml`).
- **Quote style**: double quotes (ruff default).
- **Naming**: snake_case for functions/variables, PascalCase for
  classes, SCREAMING_SNAKE_CASE for module-level constants.
- **Imports**: stdlib → third-party → local, separated by blank
  lines. No wildcard imports.
- **Type hints**: use them. The project runs `pyright` in CI; the
  build will fail on `reportMissingTypeStubs` errors.
- **i18n**: user-visible strings go through `gettext` (`from gettext
  import gettext as _`). New strings must be added to the `.pot`
  template.

## Security

To report a vulnerability, see [SECURITY.md](SECURITY.md). Please
**do not** open a public issue for security bugs.

## License

By contributing, you agree that your contributions will be licensed
under the [MIT License](LICENSE). The codebase contains code originally
written by Samuel Abels and Rayforge contributors; see [NOTICE](NOTICE)
for the attribution.
