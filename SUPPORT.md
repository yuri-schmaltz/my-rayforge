# Support / Troubleshooting

This document covers the most common questions and issues with
**[Pires Forge](https://github.com/yuri-schmaltz/pires-forge)**.

If your problem isn't here, search the
[open issues](https://github.com/yuri-schmaltz/pires-forge/issues)
or [open a new one](https://github.com/yuri-schmaltz/pires-forge/issues/new/choose).

> For security issues, email **<security@yuri-schmaltz.dev>** — please
> do not open a public issue for security bugs.

## Installation

### Linux (`.deb` for Ubuntu 24.04)

```bash
sudo apt install /path/to/pires-forge-linux.deb
pires-forge
```

The `.deb` installs the binary at `/usr/bin/pires-forge`, the desktop
entry at `/usr/share/applications/org.piresforge.pires-forge.desktop`,
and the icon at `/usr/share/icons/hicolor/scalable/apps/org.piresforge.pires-forge.svg`.

After installing, run:

```bash
sudo update-desktop-database
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
```

Then log out and back in (Cinnamon refreshes the menu cache on
session start). The app should appear in **Menu → Graphics → Pires Forge**.

> If you previously had an older release installed, remove it first
> because the Debian package was renamed from `rayforge` to
> `pires-forge`:
>
> ```bash
> sudo apt remove rayforge  # or pires-forge, whichever is installed
> sudo apt install /path/to/pires-forge-linux.deb
> ```

### macOS (`.dmg`)

Open the `.dmg`, drag `Pires Forge.app` to `/Applications`, and
double-click to launch. You may need to allow the app in
**System Settings → Privacy & Security** the first time.

### Windows (`.exe`)

Run the NSIS installer (`pires-forge-v1.0.0-installer.exe`). The
default install location is `C:\Program Files\Pires Forge`. The
Start Menu entry is under **Pires Forge**.

## Application is in Portuguese but the UI is in English

The first .deb build shipped without `.mo` translation files. This
was fixed in `1.0.0-pires2` / `1.0.0`:

- `MANIFEST.in` was updated to include `*.po` and `*.pot` (was:
  `*.mo` only, which was a silent i18n shipping bug).
- A `compile .po → .mo` step was added to all three production
  build workflows (Linux, macOS, Windows).
- 33 regression tests in
  `tests/shared/util/test_i18n_shipped.py` verify every supported
  language is present in every build.

If your `.deb` has the bug (i.e. the UI is in English even after
selecting Portuguese in Settings → Language), upgrade to `1.0.0` or
later and reinstall.

## The app doesn't appear in the Cinnamon / MATE menu

The most common cause is a stale `.desktop` `Exec=` field pointing
to the old binary name. The first rebrand release shipped with
`Exec=rayforge` (the old binary name) which causes Cinnamon to
hide the entry because the binary doesn't exist. Fixed in
`1.0.0-pires2` / `1.0.0` with `Exec=pires-forge`.

If you have the old `.deb` installed, either:

1. **Upgrade** to the new `.deb` (recommended).
2. **Override** the broken `.desktop` in your home directory:

   ```bash
   mkdir -p ~/.local/share/applications
   cat > ~/.local/share/applications/pires-forge.desktop << 'EOF'
   [Desktop Entry]
   Version=1.0
   Type=Application
   Name=Pires Forge
   Comment=Laser cutting and engraving
   Exec=pires-forge
   Icon=org.piresforge.pires-forge
   Terminal=false
   Categories=Graphics;2DGraphics;VectorGraphics;Engineering;
   StartupNotify=true
   StartupWMClass=org.piresforge.pires-forge
   EOF
   update-desktop-database ~/.local/share/applications
   ```

   Then log out and back in.

## Update check is silent

The app update check defaults to **off** in Pires Forge. To opt in:

1. Open Pires Forge.
2. Go to **Settings → Preferences → General**.
3. Enable **Check for updates**.

When enabled, the app queries the
[Pires Forge releases](https://github.com/yuri-schmaltz/pires-forge/releases)
page (not the upstream Rayforge releases — those are for the
upstream project, not the fork).

## G-code file won't open

Pires Forge opens:

- `.ryp` (Pires Forge / Rayforge project files)
- `.rfs` (Pires Forge / Rayforge sketch files)
- `.svg`, `.dxf`, `.pdf`, `.png`, `.jpg`, `.bmp` (import formats)
- `.lbrn`, `.lbrn2` (LightBurn files, imported as new projects)
- `.rd` (Ruida files, imported as new projects)

It does **not** open:

- `.gcode`, `.nc`, `.tap` (G-code files) — these are output formats
  only.
- Raw G-code from upstream Rayforge pre-1.0 — project format is
  compatible, but if you have very old files (`.rfp` instead of
  `.ryp`), see
  [upstream migration notes](https://github.com/barebaric/rayforge/blob/main/MIGRATION.md).

## Performance is slow on a large SVG

Pires Forge parses the SVG to extract vector geometry, then converts
it to ops (laser commands). For files with many thousands of
elements:

- Use **Shrink Wrap** in the step settings to clip the geometry to
  the stock.
- Reduce the number of layers before importing.
- Use the **Simplify** post-processor to reduce point count.

If the file is raster (PNG/JPG), the import converts it to
binarized paths which is slow at high DPI. Try a lower DPI
(150–300 for vector output, 600+ for raster engraving).

## The 3D preview is blank

The 3D preview requires a working OpenGL context. If it's blank:

1. Check that the OS has working OpenGL drivers installed
   (`glxinfo | grep "OpenGL version"` on Linux).
2. If running over SSH or in a Wayland session without a GPU,
   set the env var `RAYFORGE_DISABLE_3D=1` to disable the 3D
   preview at startup.
3. Check the log file (Help → Open Log Folder) for OpenGL errors.

## Where are the logs?

- **Linux**: `~/.local/share/rayforge/rayforge.log`
- **macOS**: `~/Library/Application Support/rayforge/rayforge.log`
- **Windows**: `%APPDATA%\rayforge\rayforge.log`

To generate a debug bundle (zip of logs, project state, and
environment): **Help → Save Debug Log**. The bundle is privacy-
respecting: it never leaves your machine automatically.

## Still stuck?

1. Check [open issues](https://github.com/yuri-schmaltz/pires-forge/issues)
   for similar problems.
2. [Open a new issue](https://github.com/yuri-schmaltz/pires-forge/issues/new/choose)
   with the debug bundle attached.
3. For sensitive bugs (security, data loss), email
   <security@yuri-schmaltz.dev> instead of opening a public issue.
