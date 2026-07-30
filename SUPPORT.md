# Support / Troubleshooting

This document covers the most common questions and issues with the
`yuri-schmaltz/rayforge` fork. If your problem isn't here, search
the [open issues](https://github.com/yuri-schmaltz/rayforge/issues)
or [open a new one](https://github.com/yuri-schmaltz/rayforge/issues/new/choose).

> For **security** issues, see [SECURITY.md](SECURITY.md) — please
> do not open a public issue for security bugs.

## Installation

### I installed the `.deb` but the app doesn't appear in my menu

The `.deb` installs to `/usr/bin/rayforge` and the desktop entry to
`/usr/share/applications/`. After installing, run:

```bash
sudo update-desktop-database
sudo gtk-update-icon-cache /usr/share/icons/hicolor  # if not auto
```

Then log out and back in (or `killall gnome-shell` on GNOME), and
the app should appear in your app launcher.

### The `.deb` build fails with "project.version must be pep440"

This was a known issue on the fork. It was fixed in **PR #17** (the
`debian/rules` sed chain now handles the `+resilience.X` semver
build metadata). If you hit this, you're running an old build
script — pull the latest `main` and rebuild.

### The Windows installer complains about an unknown publisher

The fork does **not** code-sign the Windows binaries (the
maintainer doesn't have a Windows code-signing certificate). On
Windows 10/11, you may see a SmartScreen warning — click "More
info" → "Run anyway" to proceed. For a code-signed build, see
[SECURITY.md](SECURITY.md#-known-intentional-design-choices) — this
is on the roadmap (PR #23 in the production-readiness series).

### The macOS DMG fails to open ("unidentified developer")

The fork also does **not** notarize the macOS binaries. After
opening the DMG, right-click the app icon and choose "Open" to
bypass Gatekeeper. For a notarized build, see the same
SECURITY.md section.

## Auto-update

### The app says "You are up to date" but a new release was just published

The auto-update checker polls the GitHub API. There can be a delay
of a few minutes between the release being published and the
checker's next poll. To force a check, go to **Settings → About
→ Check for updates**.

The version comparison logic uses PEP 440 semantics. The fork's
tag scheme is `1.9.0+resilience.X` (semver build metadata), which
PEP 440 handles correctly:
- `1.9.0+resilience.4` is **newer** than `1.9.0` ✓
- `1.9.0+resilience.4` is **older** than `1.9.1` (when upstream
  ships a real release) ✓
- `1.9.0+resilience.4` is **older** than `1.9.0+resilience.5` ✓

If you see an unexpected "up to date" message, run the app from
the terminal:

```bash
rayforge --verbose
```

This will print the version checker's HTTP requests and the
parsed result. Open an issue with the output if the comparison
is wrong.

### The auto-update download fails / hangs

The fork's auto-update uses the same `resilient_get` HTTP layer
as the rest of the app (retry with exponential backoff, max 3
attempts). If it still fails:

1. Check your internet connection: `curl https://api.github.com`
2. Check if a corporate firewall is blocking the GitHub API.
3. Try a manual download from the [releases page](https://github.com/yuri-schmaltz/rayforge/releases).

## File formats

### The app opens a `.lbrn` file but the artwork is missing or garbled

LightBurn `.lbrn` files are XML. The fork parses them with
`defusedxml` (since PR #15) to block malicious payloads. If your
file was exported by a very old version of LightBurn, it may use
a non-standard XML construct that the strict parser rejects. Try
opening the file in LightBurn and re-saving it as `.lbrn2` (the
modern format).

### I get "XML Parse Error" on an SVG file that opens fine in Inkscape

The fork's SVG parser is strict on the SVG spec. Some Inkscape
extensions add non-standard elements that the fork does not
support. To fix, open the SVG in Inkscape → File → Clean up
document, then re-save.

### Imported DXF is mirrored on the Y axis

This is a known issue with the DXF importer — different CAD
programs use different Y-axis conventions. The fork follows the
AutoDesk convention (Y axis up). If your file is Y-down, the
fork's importer will mirror it. Workaround: apply a Y-flip
transform in the fork's editor after import, or pre-flip the
DXF in your CAD program.

## Addons

### The addon manager says "no addons available"

The fork's addon registry is at
`https://github.com/yuri-schmaltz/rayforge/tree/main/rayforge/builtin_addons`
plus any third-party addons. If the registry call fails, the
manager falls back to a cached snapshot from the last
successful fetch.

To reset the cache, delete `~/.cache/rayforge/addons/`.

### I get "addon signature verification failed" on a custom addon

The fork supports addons from any source, but it does verify
the addon manifest signature against a known key. The default
trusted key is in `rayforge/addon_mgr/keys/default.pub`. If you
want to add a custom key:

1. Generate a keypair: `gpg --gen-key --quick-generate-key
   "Your Name <you@example.com>" default default never`
2. Export the public key: `gpg --export --armor your@email.com
   > ~/.config/rayforge/keys/custom.pub`
3. Sign your addon manifests with the private key
4. Distribute the `.pub` file to your users and have them drop
   it in `~/.config/rayforge/keys/`

This is a non-trivial setup. For most users, using the
default trusted key is fine.

## Networking

### The app can't reach the network (e.g. the addon manager or update check)

The fork's network code is in `rayforge/shared/util/http.py`. It
uses `aiohttp` with a custom DNS resolver and exponential
backoff on retry. If you're behind a corporate proxy:

1. Set `HTTP_PROXY` and `HTTPS_PROXY` environment variables
   (the fork uses `aiohttp` which honours them by default).
2. If the proxy uses a self-signed cert, set
   `REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt`.
3. If the proxy intercepts TLS (man-in-the-middle), the fork
   will fail to verify the certificate chain. You'll need to
   add the proxy's CA to the system trust store.

### My machine (GRBL/Marlin) doesn't connect over USB

The fork uses `pyserial` for the serial connection. Common
issues:

- **Permission denied on `/dev/ttyUSB0`**: add your user to the
  `dialout` group: `sudo usermod -aG dialout $USER`, then log
  out and back in.
- **Device not found**: run `ls /dev/tty*` to see what's there.
  On some systems, the device appears as `/dev/ttyACM0`
  (Arduino-based GRBL boards).
- **Wrong baud rate**: the fork defaults to 115200. If your
  machine is set to 9600, change it in **Settings → Machine →
  Connection → Baud rate**.

## Performance

### The app feels slow on startup

The fork uses GTK4 with Libadwaita, which has a non-trivial
startup cost (CSS parsing, theme loading, font registration).
On a typical Linux desktop, expect 2-3 seconds from `rayforge` to
the main window. On older hardware, this can stretch to 5-10
seconds.

The fork's `Import Time Gate` CI job measures the time to import
the package (without starting the GUI). As of 1.9.0+resilience.4,
this is under 30 seconds (the CI budget). If your local import
is much slower, check for:

- Conflicts with site-packages in your Python environment
  (use `pixi run` to get a clean env).
- Slow I/O on the user's home directory (e.g. NFS mount).

### Renders are slow

The fork uses `libvips` (via `pyvips`) for image processing. On
modern hardware, renders should take seconds. If yours take
minutes:

1. Check that `libvips` was built with all the format plugins
   (`pixi info` should show it).
2. Reduce the render DPI in **Settings → Render**.
3. Disable anti-aliasing for the preview (live preview only).

## Logs and crash reports

### Where are the logs?

- **Linux**: `~/.local/share/rayforge/rayforge.log`
- **macOS**: `~/Library/Logs/rayforge/rayforge.log`
- **Windows**: `%APPDATA%\rayforge\rayforge.log`

The log file is rotated when it reaches 5 MB. The last 3 rotations
are kept. To increase the log level, set the `RAYFORGE_LOG_LEVEL`
environment variable to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or
`CRITICAL`.

### The app crashed. How do I report it?

1. Open the logs (see above) and find the crash traceback.
2. Open a [bug report](https://github.com/yuri-schmaltz/rayforge/issues/new?template=bug_report.md).
3. Include the traceback, the version (`rayforge --version`),
   your OS, and the steps to reproduce.

## Contributing back

Found a bug fix or a feature? See [CONTRIBUTING.md](CONTRIBUTING.md)
for the workflow. For design questions, open a
[discussion](https://github.com/yuri-schmaltz/rayforge/discussions)
before opening a PR.

## Still stuck?

- 💬 [GitHub Discussions](https://github.com/yuri-schmaltz/rayforge/discussions) — for general questions
- 🐛 [Issue tracker](https://github.com/yuri-schmaltz/rayforge/issues) — for confirmed bugs
- 🔒 [SECURITY.md](SECURITY.md) — for security issues
- 📖 [CONTRIBUTING.md](CONTRIBUTING.md) — for code contributions
