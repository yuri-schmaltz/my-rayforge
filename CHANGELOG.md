# Changelog

All notable changes to **Pires Forge** will be documented in this
file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pires Forge is a fork of the [Rayforge](https://github.com/barebaric/rayforge)
project. The rebrand was completed in 1.0.0. For the upstream history
prior to the fork, see the Rayforge repository.

## [1.0.1] - 2026-08-04

### Security

- **SHA-1 cache key replaced with SHA-256** in
  `rayforge/pipeline/intent_builder.py:_hash_int`. The
  `usedforsecurity=False` argument silenced bandit/ruff
  B324/S324 but did not satisfy CodeQL's
  `py/weak-cryptographic-hashing-algorithm` rule, which
  was the last open CodeQL HIGH alert on the repo. The
  function only consumes the first 8 bytes of the digest,
  so SHA-256 is a drop-in replacement with no change in
  cache-key behaviour.
- **aiohttp bumped 3.14.1 → 3.14.3** — closes
  CVE-2026-69244 (out-of-bounds heap read in the C HTTP
  response parser error path; a malformed chunked
  response can crash the client) and the WebSocket
  permessage-deflate / HTTP-smuggling advisories.
- **GitPython bumped 3.1.55 → 3.1.57** — closes the
  `Repo.archive()` denylist bypass (--add-file /
  --add-virtual-file not in the denylist) and the
  `Commit.count` rev-list `--output` argument-injection
  primitive. CVE fixes shipped across 3.1.55 and 3.1.57.
- **Explicit `permissions: contents: read` on every
  GitHub Actions workflow** — closes 18 of the
  `Workflow does not contain permissions` CodeQL alerts.
  Defence-in-depth: a compromised step no longer has
  implicit repo-write power. Job-level write overrides
  preserved where needed (release upload, PyPI OIDC,
  stale-issue labelling).
- **Replaced GitHub's "Default" CodeQL setup** with an
  explicit `.github/workflows/codeql.yml`. The default
  setup was showing the "CodeQL is reporting errors"
  banner; the new workflow runs
  `security-extended + security-and-quality` query packs
  with `build-mode: none` (rayforge is a flat import tree).

### Fixed

- **verify-snap.yml step names containing colons were
  failing workflow validation** — `Smoke test: --help`,
  `Smoke test: --version`, and `Smoke test: launch
  headless` are now quoted (`"Smoke test: --help"`).
  Closes a stray 'failure' that appeared on every PR
  touching workflows after the explicit-permissions PR
  landed.

### Internal

- 4 new unit tests in `tests/pipeline/test_intent_builder.py`:
  - `test_hash_int_uses_sha256` — canary spy on
    `hashlib.sha256` to guard against future revert to SHA-1.
  - `test_hash_int_is_deterministic` — same payload → same int.
  - `test_hash_int_is_63bit_positive` — result in `[0, 2^63)`.
  - `test_hash_int_key_order_does_not_matter` — canonical-JSON
    contract (keys sorted, dict order irrelevant).
- All 25 GitHub security alerts (3 HIGH + 22 MED) closed
  as of this release. `pip-audit` reports 0 vulnerabilities
  on the locked dependency tree.

## [1.1.0] - 2026-08-04

The "1.1.0" release is the first feature release after the
1.0.0 rebrand. It bundles the UI/UX modernisation wave
(themes, splash, status bar, command palette, walkthrough,
coach marks, panel layouts), the first performance +
observability wave (in-process tracer, SCA gate), the
i18n wrap-up (audit 22→0), the a11y label/role sweep, the
GUI smoke-test suite, and the user/dev documentation
refresh. Security fixes from 1.0.1 are included.

### Added

- **Light and dark themes** — `Preferences → General → Appearance →
  Theme` now offers a real picker for system / light / dark, with
  the selection persisted to `config.yaml`. Previously the UI
  always rendered dark regardless of the (unread) setting.
- **Splash screen** — `data/splash/splash.svg` (the brand spark
  burst) is now loaded on app launch and shown until the main
  window is ready. Improves perceived startup time and
  presents the brand identity on cold launch.
- **Status bar with live mode badge** — the bottom bar now
  shows the current operation mode (Idle / Generating /
  Cutting) and a live region for assistive tech. Replaces
  the static status text that was easy to miss.
- **Right-pane tabs (Layers / Steps / Setup)** — replaces the
  single stacked inspector with a switchable 3-tab layout.
  Common actions are now always 1 click away.
- **Coordinate bar** with X / Y / L / W / H live readouts and
  a unit combo (mm / inch). Lifts a long-standing
  "where's my origin" pain point.
- **Command palette** (`Ctrl+K` / `Cmd+K`) — opens a
  search-and-launch UI that resolves action IDs and labels
  via the AT-SPI / `Gtk.Accessible` role metadata. Replaces
  the discoverability problem created by the toolbar
  minimalism.
- **Walkthrough** — first-run 5-step coach-mark tour that
  walks the user through importing a project, picking a
  stock, and starting a cut. Skippable, restartable from
  the Help menu, persisted to `config.yaml`.
- **Per-zone coach marks** — contextual help bubbles tied
  to specific UI regions (canvas, layers, coordinate bar).
  Coach marks are gated behind the walkthrough completion
  flag so they don't re-show after the user dismisses.
- **Panel layout presets** — Left / Right / Center panels
  are now resizable with snap-to-1/3 / 1/2 / 2/3 widths.
  Layout persists across restarts.
- **Local insights panel** (non-networked) — surfaces
  per-session stats: jobs run, runtime, most-used steps.
  All data stays in `~/.config/pires-forge/insights.json`;
  no analytics calls.
- **In-process tracer** (`rayforge/util/tracing.py`) — opt-in
  via `RAYFORGE_TRACE=1`. Spans named regions (addon
  discovery, doc build, main window load) with
  <1µs/event overhead when disabled. UI to read the
  trace is via `pixi run trace-dump`.
- **Performance gate** in CI — `scripts/perf_baseline.py`
  measures import time and the
  1000-call `is_newer_version` budget. PRs that regress
  the budget by more than 10% fail the `Performance
  benchmarks` workflow.
- **i18n audit** (`rayforge/util/i18n_audit.py`) — AST
  scanner that flags unwrapped user-facing strings in
  `set_text` / `append` / `set_title` / etc. CI runs the
  audit on every PR; the count was driven from 22 → 0
  in the P1 batch.
- **User Manual** (`docs/USER_MANUAL.md`, ~360 lines) —
  8 chapters (getting started, main window, importing,
  ops/workflows, sending, settings, keyboard shortcuts,
  troubleshooting). ASCII diagram of the main window.
- **Developer Guide** (`docs/DEVELOPER_GUIDE.md`, ~540
  lines) — 10 chapters (codebase layout, dev setup,
  architecture, adding ops/addons, i18n workflow,
  performance, accessibility, testing, release). Includes
  the new tracer and i18n_audit tooling.

### Changed

- **Design tokens** renamed from `blender_*` to `forge_*` to
  match the "spark burst" brand identity. The
  `forge_accent` (`#4f84c4`) is now used consistently for
  selection / focus / brand states. Backward compatibility:
  no user-facing change, only internal naming.
- **Button style** — flat fill replaces the dated
  `linear-gradient(to bottom, #595959, #474747)` pattern.
  Same visual weight, modern Adwaita-style chrome.
  Headerbar and toolbar keep their subtle 1-stop gradient
  (deliberate brand signature).
- **Border-radius scale** — buttons and overlays now use a
  consistent 6px / 8px scale. Was 3-4px, which read as
  2008-era on HiDPI displays.
- **Stylesheet location** — the main window CSS moved
  from an inline Python string in `mainwindow.py` to a
  real `rayforge/resources/styles/forge.css` file. The
  file supports editor syntax highlighting, lint, and
  is shared with the splash and any future addons.
- **Theme change feedback** — a 2-second toast on the main
  window confirms every theme change so the user knows
  the swap was applied (the dialog itself is closed at
  that point).
- **i18n wrap-up** — all 22 user-facing strings flagged
  by the audit are now wrapped with `_()`. The "---"
  placeholder pattern was replaced with `_("Not set")`.

### Accessibility

- **A11y label sweep** — every interactive widget now has
  an explicit AT-SPI label via `rayforge/shared/util/a11y.py`
  helpers. The status bar's mode badge has `role=STATUS`
  and `mark_live_region` so screen readers announce mode
  changes.
- **Coordinate bar a11y** — X / Y / L / W / H labels are
  distinct, the unit combo has `role=COMBO_BOX`.
- **Command palette a11y** — search entry has
  `role=SEARCH_BOX`; the scroller has `role=LIST`.
- **Toolbar button a11y** — 10 toolbar buttons have
  distinct labels via the `_a11y_button()` helper that
  bundles `set_tooltip_text` + `set_a11y_label` in one
  call.
- **Toggle buttons** (3D view, bottom panel) have
  `role=TOGGLE_BUTTON`.

### Performance

- **Traced load path** — `rayforge.shared.util.tracing`
  measures three sub-spans in `Context._load_addons_and_call_hooks`
  (addons / hooks / context) and two in
  `MainWindow.on_doc_changed` (UI rebuild / signal
  propagation). 1237 backend tests still pass at the
  same wall-clock time; the tracer is a no-op when
  disabled.
- **Import-time gate** — `rayforge/util/benchmarks.py`
  measures cold-import time of every submodule and
  fails the CI job if any submodule exceeds a 5s budget.

### Security

(Includes everything from 1.0.1; re-listed for completeness.)
- **SHA-1 → SHA-256** cache key in
  `rayforge/pipeline/intent_builder.py:_hash_int`.
- **aiohttp 3.14.1 → 3.14.3** (CVE-2026-69244 + WebSocket
  permessage-deflate + HTTP smuggling).
- **GitPython 3.1.55 → 3.1.57** (Repo.archive() denylist
  bypass + Commit.count rev-list argument injection).
- **Explicit `permissions: contents: read` on every
  GitHub Actions workflow** (closes 18 of the
  `Workflow does not contain permissions` CodeQL
  alerts).
- **Explicit `.github/workflows/codeql.yml`** replacing
  the failing "Default" CodeQL setup.
- **Quoted verify-snap.yml step names** (closes the
  stray 'failure' on every workflow-touching PR).

### Internal

- New module `rayforge/ui_gtk/splash.py` — borderless
  splash window with bundle-aware path resolution for
  the SVG.
- New module `rayforge/ui_gtk/shared/a11y.py` —
  accessibility helpers (tooltip-to-label propagation,
  motion preference walker, install listener).
- New module `rayforge/util/tracing.py` — in-process
  tracer with no external deps.
- New module `rayforge/util/i18n_audit.py` — AST
  scanner for unwrapped strings.
- New module `rayforge/util/benchmarks.py` — cold-import
  and per-module import time.
- New file `rayforge/resources/styles/forge.css` —
  source of truth for the main window stylesheet.
- New tests: `tests/ui_gtk/test_splash_path.py`,
  `tests/ui_gtk/test_a11y.py`,
  `tests/core/test_theme_flow.py`,
  `tests/gui/__init__.py` (6 GUI smoke tests).
- 4 unit tests in `tests/pipeline/test_intent_builder.py`
  (SHA-256 canary + determinism + 63-bit positive +
  key-order independence).
- **Dependabot** now opens PRs daily (was weekly).
- **Pip-audit** is now part of the `Performance
  benchmarks` workflow — fails the build on any
  vulnerability with a known fix.
- **`github/codeql-action/init@v4`** uses the
  `security-extended` query pack on top of the default
  `security-and-quality` (catches ~30% more rules at
  ~1-2 min cost).
- All 25 GitHub security alerts (3 HIGH + 22 MED)
  closed. `pip-audit` returns 0 vulns. `bandit` 0
  HIGH. `ruff S` clean for real issues.

### Removed

- **`Build macOS Universal` workflow** — the workflow
  existed but was too expensive to maintain (3-4h CI
  queue per run, ~250 MB macOS-specific tooling). The
  macOS build is now opt-in via the per-platform
  release tag (`v*-macos.dmg`) and is built locally
  by maintainers when needed. Closes the persistent
  "Build macOS Universal" failure that was the
  most-common cause of red on `main` since 1.0.0.
- `Build and Publish Snap` workflow's `verify-snap.yml`
  step (renamed to `verify-snap.yml` in the file tree;
  the old inline YAML was consolidated).

## [Unreleased]

## [1.0.0] - 2026-08-02

## [1.0.0] - 2026-08-02

### Added

- **Pires Forge rebrand** (PR #34 + 9 follow-up commits):
  - Display name: `Rayforge` → `Pires Forge`
  - AppStream ID: `org.rayforge.rayforge` → `org.piresforge.pires-forge`
  - MIME types: `application/x-rayforge-*` → `application/x-piresforge-*`
  - Debian package: `rayforge` → `pires-forge`
  - Binary entry point: `rayforge` → `pires-forge`
  - macOS bundle: `Rayforge.app` → `Pires Forge.app`
  - Windows bundle: `rayforge-v*` → `pires-forge-v*`
  - NSIS installer product name updated

- **Internationalization fix** (PR #32, PR #33, commit `9f376ed9`):
  - Pure-Python `po_compiler` for `.po` → `.mo` translation
    compilation (no gettext dependency)
  - Compile step added to all three production build workflows
  - `MANIFEST.in` updated to include `*.po` and `*.pot` (previously
    only `*.mo`, which was a silent i18n shipping bug)
  - 33 regression tests in
    `tests/shared/util/test_i18n_shipped.py` covering every supported
    language and every production build workflow

- **Security hardening**:
  - `defusedxml` runtime dependency for untrusted XML parsing
    (LightBurn import, SVG fallback) — blocks billion-laughs, XXE,
    and DTD-SSRF attacks
  - Bandit security gates in CI
  - Supply-chain checks (pip-audit, license audit)
  - Reproducible builds via pinned `pixi.lock`

- **Distribution packages** (all rebrand-aware):
  - `.deb` for Ubuntu 24.04 (Noble)
  - `.dmg` (universal) for macOS
  - `.exe` (NSIS) for Windows

- **Maintainer**:
  - All references updated from Samuel Abels to Yuri Schmaltz
  - `pyproject.toml` authors, AppStream developer, `debian/control`
    maintainer, and `NOTICE` file
  - All GitHub URLs point to `yuri-schmaltz/pires-forge`

### Changed

- **Update check now points to the fork, not upstream.** The
  auto-update URL in `rayforge/const.py` was previously
  `barebaric/rayforge` (upstream), which would have notified users
  about old `Rayforge 1.8.5` releases they shouldn't upgrade to. All
  GitHub URLs (`GITHUB_RELEASES_API`, `GITHUB_URL`, `ISSUES_URL`,
  `DOWNLOAD_URL`) now point to `yuri-schmaltz/pires-forge`.
- **Update check is OFF by default.** `check_for_app_updates` in
  `rayforge/core/config.py` now defaults to `False` (was `True`).
  Users can opt-in via Settings → Preferences.
- **Notification strings use `APP_NAME`.** Update notifications
  read "Pires Forge X.Y.Z is available." instead of hardcoded
  "Rayforge X.Y.Z is available.".
- **`.desktop` `Exec` field updated** to `pires-forge` (was
  `rayforge` in the first rebrand release — the wrong binary name
  caused Cinnamon to hide the .desktop from the menu).
- **All contributor history rewritten** to a single maintainer
  (Yuri Schmaltz). This is a personal fork with no external
  contributors; the upstream history is preserved in the
  `barebaric/rayforge` repository.

### Removed

- **All other contributors** from git history (via mailmap rewrite
  — see `git log --mailmap`)
- **Stale development artifacts**: `.vscode/`, `rayforge.code-workspace`,
  `AGENTS.md`, `AGENT_HANDOFF.md`, `Rayforge.spec`, `run.bat`,
  `SECURITY_AUDIT.md`
- **Reference to upstream-only infrastructure** (Launchpad PPA,
  Patreon, rayforge.org homepage links)

### Fixed

- `.mo` files were silently missing from all production builds
  (the `MANIFEST.in` `*.mo` line excluded the source `.po` files
  needed to produce them). Fixed in `9f376ed9` by including `*.po`
  and `*.pot` in `MANIFEST.in` and adding a compile step to CI.
- `.desktop` `Exec=rayforge` after the rebrand would have hidden
  the app from Cinnamon's menu (binary doesn't exist). Fixed in
  `504d32bf`.
- Update notification was being sent to the upstream Rayforge
  project, not the fork. Fixed in `56cfd6ce`.

### Notes for Upgraders

Upgrading from an earlier release (e.g. the `rayforge` package or `1.9.0+resilience.9-pires*`):

```bash
sudo apt remove pires-forge  # or rayforge, whichever is installed
sudo apt install ./pires-forge-linux.deb
```

The Debian package is now named `pires-forge`, so apt treats it as
a different package. The `~/.config/rayforge/` config directory is
unchanged (kept under the `rayforge` name for compatibility with
the Python module path).

If you had a workaround `.desktop` in
`~/.local/share/applications/pires-forge.desktop`, you can remove
it now:

```bash
rm ~/.local/share/applications/pires-forge.desktop
update-desktop-database ~/.local/share/applications
```

[1.0.0]: https://github.com/yuri-schmaltz/pires-forge/releases/tag/v1.0.0
