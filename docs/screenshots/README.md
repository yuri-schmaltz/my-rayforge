# Screenshots

This directory contains screenshots of the fork's UI for
the README, docs, and release notes.

## Capturing screenshots

Rayforge uses GTK4 + Adwaita. To capture screenshots:

### Linux

```bash
# Install screenshot tool
sudo apt install gnome-screenshot

# Launch rayforge
rayforge &

# Wait for the window to appear
sleep 3

# Capture the full screen
gnome-screenshot -f rayforge-main.png
```

Or use a more capable tool like `flameshot` (with
annotations and cropping):

```bash
sudo apt install flameshot
flameshot gui -p ~/screenshots/rayforge
```

### macOS

```bash
# Full screen
screencapture -x rayforge-main.png

# Window only
# Use Cmd+Shift+4, then Space, then click the window
```

### Windows

PowerShell:

```powershell
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bitmap = New-Object System.Drawing.Bitmap $screen.Bounds.Width, $screen.Bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Bounds.X, $screen.Bounds.Y, 0, 0, $screen.Bounds.Size)
$bitmap.Save("rayforge-main.png", [System.Drawing.Imaging.ImageFormat]::Png)
```

## Recommended screenshots

The README and release notes typically include:

1. **Main window**: the default view with a loaded project
2. **Machine controls**: the right panel with jog controls
3. **Material library**: the material management view
4. **Console output**: the bottom panel showing a job
5. **Settings dialog**: the preferences view

## File naming convention

- `main-window.png`: the main view
- `machine-controls.png`: machine jog and status
- `material-library.png`: material management
- `console.png`: console output
- `settings.png`: preferences dialog

Use lowercase, hyphens, no spaces.

## Dimensions and quality

- Recommended size: 1280x800 or 1920x1080
- Format: PNG (lossless) for screenshots, JPG only for
  photographic content
- File size: keep under 500 KB per screenshot
- Compress with `pngquant` or `oxipng` if needed:
  ```bash
  pngquant --quality=80-95 rayforge-main.png
  oxipng -o max rayforge-main.png
  ```

## Adding to the release

1. Capture the screenshots following the naming convention.
2. Commit them to this directory.
3. Reference them in the README:
   ```markdown
   ![Main window](docs/screenshots/main-window.png)
   ```
4. Reference them in the release notes body.

## Privacy

When capturing screenshots:

- **Do not include** personal data in the visible content
  (file paths under `~/Documents/work-project/...` are
  awkward; use `~/work/` or anonymize)
- **Do not include** the user's machine profile (e.g. the
  IP address of the laser cutter); the README screenshot
  should use a placeholder
- **Do not include** proprietary artwork in the loaded
  project; the project file in the screenshot should be
  the example project that ships with the repo
