# Pires Forge — User Manual

Pires Forge is a desktop application for designing and
producing laser / CNC cuts. It started as a fork of
[Rayforge](https://github.com/barebaric/rayforge) and
has been progressively modernized.

This manual is written for the **end user** — the person
who wants to import a vector file, frame the cuts, and
send the job to a connected machine. If you're a
**developer** looking to extend the app, see
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) instead.

---

## Table of contents

1. [Getting started](#1-getting-started)
2. [The main window](#2-the-main-window)
3. [Importing and editing](#3-importing-and-editing)
4. [Operations and workflows](#4-operations-and-workflows)
5. [Sending jobs to the machine](#5-sending-jobs-to-the-machine)
6. [Settings and configuration](#6-settings-and-configuration)
7. [Keyboard shortcuts](#7-keyboard-shortcuts)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Getting started

### 1.1 System requirements

- Linux (X11 or Wayland), macOS, or Windows 10+
- 4 GB RAM minimum, 8 GB recommended for large designs
- A connected GRBL / Ruida / Smoothieware-compatible
  machine (or just a file — Pires Forge is useful even
  without hardware)

### 1.2 First launch

The first time you open Pires Forge, a 5-card walkthrough
introduces the main UI zones:

  1. **Canvas** — your work area
  2. **Right pane** — operations and properties
  3. **Toolbar** — frame, then send
  4. **Coordinate bar** — live X/Y + selection size
  5. **Command palette** — `Ctrl+Shift+P` for anything

You can re-show the walkthrough any time from
**Help → Show Tour**.

After the walkthrough, **coach marks** appear when you
first interact with each zone. These small popovers
explain *what to do* in each surface, not just *what it
is*. They never re-show once dismissed. Reset them from
**Help → Replay Coach Marks** if you want them again.

### 1.3 Connecting a machine

1. Open the **Machine** menu (or the machine selector
   in the toolbar).
2. Pick the connection type (USB / network / mock).
3. Click **Connect**. The mode badge in the status bar
   turns blue (Framing) when ready.

If you don't have a machine yet, choose **Mock Machine**
to explore the UI without hardware.

---

## 2. The main window

```
┌──────────────────────────────────────────────────────────┐
│ Header bar: file / edit / view / machine / help menus    │
├──────────────────────────────────────────────────────────┤
│ Toolbar: [New] [Open] [Save] [Frame] [Send] ...         │
├──────────────────────────────────────────────────────────┤
│ Coordinate bar: X  Y   L  W  H    [unit: mm]            │
├──────────┬───────────────────────────────────┬──────────┤
│          │                                   │          │
│          │                                   │ Right    │
│  Canvas  │          Drawing surface          │ pane:    │
│          │                                   │ Workflow │
│          │                                   │   |      │
│          │                                   │ Props    │
├──────────┴───────────────────────────────────┴──────────┤
│ Bottom panel: Layers | G-code | Console | History       │
├──────────────────────────────────────────────────────────┤
│ Status bar: [Mode] X Y layer op progress                │
└──────────────────────────────────────────────────────────┘
```

### 2.1 The canvas

The canvas is a vector drawing surface. You can:

- **Pan** with middle-mouse drag, or hold `Space` and drag.
- **Zoom** with the mouse wheel.
- **Select** an object with a single click.
- **Box-select** by dragging on empty canvas.
- **Move** selected objects by dragging them.
- **Rotate** with `R`.
- **Delete** with `Delete` or `Backspace`.

### 2.2 The right pane (tabbed)

The right pane has two tabs:

- **Workflow** — the operations stack (cut, engrave, score).
  Drag operations to reorder them.
- **Properties** — the selected object's properties.
  Auto-shows when you click an object.

You can also use the **View → Layout** submenu to switch
between three preset layouts:

- **Default** — both right and bottom visible
- **Compact** — right only (canvas focus)
- **Expanded** — bottom only (logs focus)

### 2.3 The status bar

At the bottom of the window, you'll see:

- **Mode badge** — colored circle indicating the current
  state. Green = designing, blue = framing, yellow =
  sending, orange = paused, red = alarm, gray = idle.
- **Cursor X / Y** — live coordinates of the mouse.
- **Layer** — current layer index (e.g. "Layer 2/5").
- **Operation** — the active operation.
- **Progress** — fills during job execution.

### 2.4 The bottom panel

Switch between four tabs:

- **Layers** — add, remove, reorder, lock layers.
- **G-code** — preview the instructions before sending.
- **Console** — live machine output (when connected).
- **History** — undo / redo stack.

---

## 3. Importing and editing

### 3.1 Supported file formats

| Format | Use case |
|---|---|
| SVG | vector designs |
| DXF | CAD drawings |
| PNG / JPG | raster (auto-vectorized) |
| PDF | multi-page vector |
| existing Pires Forge / Rayforge files | round-trip |

### 3.2 The import wizard

**File → Import** opens a wizard:

1. Pick the file.
2. Choose the import mode (vectorize, embed, reference).
3. Set the origin and scale.
4. Confirm.

### 3.3 The edit toolbar

When an object is selected, the edit toolbar appears
above the canvas with:

- **Move** (`M`)
- **Rotate** (`R`)
- **Scale** (`S`)
- **Align** (left / right / top / bottom / center)
- **Distribute** (horizontal / vertical)
- **Group** / **Ungroup** (`Ctrl+G` / `Ctrl+Shift+G`)

---

## 4. Operations and workflows

An operation is an instruction for the machine: "cut along
this path at this speed and power". A workflow is an
ordered list of operations applied to one or more layers.

### 4.1 Built-in operations

- **Cut** — full-power pass through the material.
- **Engrave** — raster or vector engraving at lower power.
- **Score** — light surface mark (paper, leather).
- **Pierce** — first pass at high power (for thick materials).

### 4.2 Creating a workflow

1. Select one or more objects in the canvas.
2. In the **Workflow** tab, click **+ Add Operation**.
3. Pick the operation type.
4. Adjust the parameters (power, speed, passes).
5. Repeat for as many operations as you need.
6. The operations run in order from top to bottom.

### 4.3 Per-layer workflows

Each layer can have its own workflow. This is useful when
you have multi-material jobs (e.g. "the top layer is
acrylic, the bottom is cardboard" — different ops per
material).

---

## 5. Sending jobs to the machine

### 5.1 Framing

Before sending a real cut, click **Frame** in the toolbar.
The machine moves to the bounding box of the design so
you can verify positioning. The mode badge turns blue.

### 5.2 Sending

When you're ready, click **Send** (or press `F5`). The
status bar mode badge turns yellow, and the progress
indicator starts filling. The bottom panel auto-switches
to the **Console** tab so you can watch the G-code stream.

### 5.3 Pause / Resume / Stop

During a job:

- **Pause** (`Ctrl+P`) — stop after the current segment.
- **Resume** — continue from where you paused.
- **Stop** (`Escape`) — abort. The machine returns to home.

If the machine enters an **Alarm** state (red badge), the
software prompts you to home the machine before resuming.

---

## 6. Settings and configuration

**Preferences** opens a settings dialog. Key settings:

- **Theme** — System / Light / Dark.
- **UI density** — Comfortable (default) / Compact.
- **Toolbar mode** — Essential (8 buttons) / All.
  Configurable from the toolbar's "..." button.
- **Layout preset** — Default / Compact / Expanded.
  Configurable from View → Layout.
- **Walkthrough / Coach marks** — see the Help menu.
- **Local insights** — see [Section 6.1](#61-local-insights).

### 6.1 Local insights

**Help → Insights** (or `Ctrl+Shift+I`) opens a dialog
with usage stats — session time, top actions, current
mode, etc. Everything is local; no data is sent to any
server. Use the **Reset session** button to start a
fresh measurement.

---

## 7. Keyboard shortcuts

### 7.1 Global

| Action | Shortcut |
|---|---|
| New file | `Ctrl+N` |
| Open file | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Shift+Z` |
| Command palette | `Ctrl+Shift+P` |
| Insights | `Ctrl+Shift+I` |
| Quit | `Ctrl+Q` |

### 7.2 Canvas

| Action | Shortcut |
|---|---|
| Select tool | `V` |
| Pan tool | `H` (or hold `Space`) |
| Frame the design | `F` |
| Send the job | `F5` |
| Pause / resume | `Ctrl+P` |
| Stop | `Escape` |
| Delete selection | `Delete` |
| Duplicate | `Ctrl+D` |
| Select all | `Ctrl+A` |

### 7.3 View

| Action | Shortcut |
|---|---|
| Toggle right pane | `Ctrl+]` |
| Toggle bottom panel | `Ctrl+[` |
| Zoom in | `Ctrl+=` |
| Zoom out | `Ctrl+-` |
| Zoom to fit | `Ctrl+0` |
| Zoom 1:1 | `Ctrl+1` |
| Top view | `Numpad 7` |
| Front view | `Numpad 1` |
| Right view | `Numpad 3` |
| Isometric | `Numpad 0` |

---

## 8. Troubleshooting

### 8.1 "Machine not connecting"

- Check the USB cable / network.
- On Linux, you may need to add your user to the `dialout`
  group: `sudo usermod -aG dialout $USER`, then log out
  and back in.
- Try a different USB port — some are power-limited.

### 8.2 "The walkthrough won't stop showing"

Open `~/.config/pires-forge/config.yaml` and set
`walkthrough_seen: true`. (Or click Done on the
walkthrough dialog.)

### 8.3 "Reset all my preferences"

Delete `~/.config/pires-forge/`. The next launch will
re-create it with default values. Note: this also
deletes your machine configurations.

### 8.4 "The status bar is in the wrong language"

Pires Forge uses your system locale. Override with
the `LANGUAGE` environment variable:

```sh
LANGUAGE=pt_BR pires-forge
```

Available locales: en, de, es, fr, pt, uk, zh_CN.

### 8.5 "The performance is slow"

- Check the **Insights** dialog (`Ctrl+Shift+I`) to see
  if any action is taking unusually long.
- Set `RAYFORGE_TRACE=1` and re-launch. The trace report
  is dumped to stderr on exit.
- File a bug with the trace output attached.

---

## License

Pires Forge is open-source software, licensed under the
GPL-3.0. See [LICENSE](LICENSE) for the full text.

## Contributing

See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for the
developer manual. Bug reports and feature requests go
to the [GitHub issue tracker](https://github.com/yuri-schmaltz/pires-forge/issues).
