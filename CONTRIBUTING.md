# Contributing to Rayforge (yuri-schmaltz fork)

Thanks for your interest in contributing to the resilience fork of
[Rayforge](https://github.com/yuri-schmaltz/pires-forge)! This document
explains how to set up a development environment, how the contribution
workflow works, and what we expect from PRs.

If you only want to **report a bug or request a feature** (no code
involved), see [SUPPORT.md](SUPPORT.md).

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you agree to uphold it. Please report unacceptable
behaviour to the maintainer (see [SECURITY.md](SECURITY.md) for the
contact email — please mention "Code of Conduct" in the subject line).

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
- On Windows, see [WINDOWS.md](WINDOWS.md) for the MSYS2-based
  setup. The MSYS2 setup is not on the CI critical path because
  upstream has separate Windows runners; the fork only validates
  Linux + macOS in CI.

### First-time setup

```bash
# Clone the fork
git clone https://github.com/yuri-schmaltz/rayforge.git
cd rayforge

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
# Full test suite (Linux/macOS)
pixi run test

# Just lint (flake8 + pyflakes + pyright)
pixi run lint

# Just formatting check
pixi run format --check

# Apply formatting
pixi run format

# Security linter (bandit)
bandit -c .bandit -r rayforge/

# Type checker
pixi run pyright
```

The full suite takes ~1-2 minutes. The tests are split into:

- `tests/core/` — core data structures (doc, workpiece, step, etc.)
- `tests/image/` — image importers (SVG, DXF, PDF, LightBurn, etc.)
- `tests/machine/` — machine drivers (GRBL, Marlin, Ruida, etc.)
- `tests/shared/` — shared utilities (HTTP resilience, tasker, etc.)
- `tests/ui_gtk/` — GTK UI tests (require a display)
- `tests/addon_mgr/` — addon manager and addon loading
- `tests/builtin_addons/*/tests` — built-in addon tests (laser,
  print-and-cut, sketcher)

UI tests are skipped by default in headless environments. To run
them locally on Linux, set `DISPLAY=:99` and start `Xvfb :99 &`
before invoking `pixi run test`.

### Headless smoke test (no display required)

```bash
# Verify the package imports cleanly
pixi run python -c "import rayforge; print(rayforge.__version__)"

# Run the import-time gate that CI uses
pixi run python -c "
import time, rayforge
t0 = time.monotonic()
import rayforge.image.svg
import rayforge.image.dxf
import rayforge.image.lightburn
import rayforge.machine.driver.grbl
print(f'Import time: {time.monotonic() - t0:.2f}s')
"
```

This is what the `Import Time Gate` CI job runs.

## Contribution workflow

### 1. Pick an issue (or open one)

- Check the [open issues](https://github.com/yuri-schmaltz/rayforge/issues)
  for things tagged `good first issue` or `help wanted`.
- If you have a new idea, open an issue first. It is much easier to
  get alignment on the design before you write code.
- For security issues, **do not open a public issue** — see
  [SECURITY.md](SECURITY.md).

### 2. Create a branch

```bash
# Sync your fork
git fetch origin
git checkout main
git pull --ff-only

# Create a feature branch
git checkout -b fix/your-descriptive-name
# or
git checkout -b feature/your-descriptive-name
```

Branch naming: `<type>/<short-description>` where `<type>` is one
of `fix/`, `feature/`, `docs/`, `chore/`, `refactor/`, `test/`,
`ci/`. Lowercase, hyphens only.

### 3. Make your changes

- Write the code.
- Add tests for any new behaviour. The existing test layout is a
  good guide — one test file per module, one test function per
  behaviour. Use `pytest`, prefer fixtures over setUp/tearDown, and
  name tests `test_<thing>_<expected>`.
- If you changed something user-visible, update `CHANGELOG.md` under
  the `## Unreleased (fork only)` section.
- If you changed a public CLI flag, security boundary, or trust
  model, update `SECURITY_AUDIT.md` (the file is the audit doc that
  also serves as a "what is intentional" reference for reviewers).
- Run `pixi run format` to apply the project formatting.
- Run `pixi run lint` and fix any issues it reports.

### 4. Commit

- Write a commit message that explains **why** the change is needed,
  not what (the diff shows what). Format:
  ```
  <type>(<scope>): <one-line summary>

  <paragraph explaining the motivation, the design choice, and any
  trade-offs>

  Refs: <issue or PR number>
  ```
  Where `<type>` is one of `fix`, `feat`, `docs`, `chore`, `refactor`,
  `test`, `ci`. Scope is the affected module (`svg`, `lightburn`,
  `updater`, `image`, `machine`, etc.).
- Keep commits focused. One logical change per commit. Squash WIP
  commits before pushing.

### 5. Push and open a PR

```bash
git push -u origin fix/your-descriptive-name
```

Then open a PR against the fork's `main` branch (NOT against upstream
`yuri-schmaltz/pires-forge` — see the [fork policy](#fork-policy) below).
The PR template will ask you to fill in:

- **What does this PR do?** (1-3 sentences)
- **Why is this change needed?** (motivation, linked issue)
- **How was it tested?** (manual steps, automated test results)
- **Screenshots / recordings** (for UI changes)
- **Breaking changes** (call them out explicitly if any)

A maintainer will review within a few days. The CI pipeline will
run automatically; PRs with failing CI will not be merged. If you're
unsure why a CI check is failing, ask in the PR comments.

### 6. Address review feedback

- Push follow-up commits to the same branch (don't force-push during
  review, it makes the reviewer's diff view harder to read).
- After approval, the maintainer will squash-merge the PR. The
  resulting commit message will be rewritten for clarity.

## Coding conventions

### Python style

- **Formatter**: ruff format (run `pixi run format`).
- **Type hints**: required on all new public functions and methods.
  The codebase targets Python 3.11+; use modern union syntax
  (`int | None`, not `Optional[int]`).
- **Imports**: sorted by `ruff`. No wildcard imports.
- **Line length**: 79 (matches `pyproject.toml`'s `[tool.ruff]`).
- **Naming**: `snake_case` for functions and variables, `PascalCase`
  for classes, `UPPER_SNAKE_CASE` for module-level constants.
- **Logging**: use the per-module `logger = logging.getLogger(__name__)`
  pattern. Never `print()` for diagnostic output.

### Security

- **XML parsing**: always use `defusedxml`, never the stdlib
  `xml.etree.ElementTree` directly. The stdlib parser is vulnerable
  to billion-laughs, XXE, and DTD-SSRF.
- **Subprocess**: always resolve the binary via `shutil.which()`
  first, and use the `argv=[...]` form — never `shell=True` with
  user-controlled input.
- **Hashing**: for non-security content hashes, pass
  `usedforsecurity=False` (Python 3.9+).
- **Eval / exec**: never call `eval()` or `exec()` on user-supplied
  input. The sketcher expression evaluator (`rayforge.core.expression`)
  is the only place that needs to evaluate user-supplied Python-like
  expressions, and it uses an AST whitelist. Don't bypass it.
- **Network**: prefer `rayforge.shared.util.http.resilient_get` /
  `resilient_post` over raw `requests` / `urllib`. The resilient
  wrapper provides retry-with-backoff and is the single chokepoint
  for HTTP exceptions.
- **File paths**: use `pathlib.Path`, not `os.path`. Validate any
  user-supplied path with `Path.resolve()` and check that the
  resolved path is within the expected directory.

### Testing

- Use `pytest`. The repo has `pytest-asyncio` and `pytest-mock` for
  the cases that need them.
- Prefer fixtures over setUp/tearDown. The `conftest.py` at the root
  of `tests/` defines shared fixtures.
- Mock external I/O (network, filesystem, subprocess) at the
  `unittest.mock` level. Don't actually hit the network in tests.
- For GTK UI tests, use the existing pattern in `tests/ui_gtk/`:
  build the widget, don't show it (`widget.show()` is not needed
  for headless tests), drive the state machine, check the signals.
- Aim for 80%+ coverage on new code. Run `pixi run pytest --cov=rayforge`
  to check locally.

### Commit message hygiene

- Subject line: 50-72 chars, no trailing period, imperative mood
  ("Add X", not "Added X" or "Adds X").
- Body wrapped at 72 chars per line.
- Use the body to explain **why**, not what. The diff shows what.
- Reference issues and PRs with `Refs: #1234` or `Fixes #1234`.
- The CI `lint-commits` job (if active) checks for trailing
  whitespace, tab characters, and subject length.

## Fork policy

This is a **fork-only repository**. The maintainer does not interact
with upstream `yuri-schmaltz/pires-forge` for this fork's changes. All
branches, PRs, tags, and releases happen exclusively inside the
fork via self-PRs (`origin:fix/...` → `origin:main`).

- ✅ Push branches to `origin` (this fork).
- ✅ Open PRs against `origin:main`.
- ❌ Do not open PRs against `yuri-schmaltz/pires-forge` from this fork.
- ❌ Do not expect changes here to be reviewed by the upstream
  maintainer.

If you want to contribute an improvement that should also land
upstream, open a separate PR in the upstream repo and reference
the fork PR for context.

## Adding new code

When adding a new module under `rayforge/`:

1. **Module docstring**: 1-2 sentences describing what the module
   does and (if relevant) which standard or protocol it implements.
2. **Imports**: standard library first, then third-party, then
   local — each group separated by a blank line.
3. **Public API**: every public class and function gets a docstring
   with `Args:`, `Returns:`, and `Raises:` sections. Use the
   Google docstring format.
4. **Tests**: at least one happy-path test and one error-path test
   per public function.
5. **Logging**: include the `logger = logging.getLogger(__name__)`
   line, even if you don't use it yet. Future maintainers will
   thank you.

## Adding new addons

Built-in addons live under `rayforge/builtin_addons/<name>/`. Each
addon has:

- `__init__.py` declaring the addon manifest
- `manifest.yaml` with the addon metadata
- `locale/<lang>/LC_MESSAGES/<name>.po` for translatable strings
- `tests/` mirroring the addon's source layout

For third-party addons, see `docs/addon-development.md` (TBD —
upstream docs are in `yuri-schmaltz/pires-forge`).

## Release process

The maintainer cuts releases by:

1. Merging PRs into `main`.
2. Bumping the version (the fork uses `1.9.0+resilience.X` semver
   build metadata).
3. Tagging the merge commit (e.g. `git tag -a 1.9.0+resilience.5 -m
   "..." 1ed2cb3`).
4. Pushing the tag (`git push origin 1.9.0+resilience.5`).
5. The CI workflow builds `.deb`, `.dmg`, and `.exe` and creates
   a GitHub release.
6. The maintainer uploads the assets and edits the release notes.

You don't need to do any of this for a typical contribution — just
open the PR and let the maintainer handle the release.

## License

By contributing, you agree that your contributions will be licensed
under the same [MIT License](LICENSE) as the rest of the project.

## Questions?

- For bugs and feature requests: [open an issue](https://github.com/yuri-schmaltz/rayforge/issues/new/choose).
- For security issues: see [SECURITY.md](SECURITY.md).
- For everything else: open a discussion in
  [GitHub Discussions](https://github.com/yuri-schmaltz/rayforge/discussions).
