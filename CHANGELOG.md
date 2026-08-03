# Changelog

All notable changes to **Pires Forge** will be documented in this
file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Pires Forge is a fork of the [Rayforge](https://github.com/barebaric/rayforge)
project. The rebrand was completed in 1.0.0. For the upstream history
prior to the fork, see the Rayforge repository.

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
