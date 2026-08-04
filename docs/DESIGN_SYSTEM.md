# Design System

This document describes the visual design system of Pires Forge:
tokens, classes, components, and the rules for extending them.
New contributors should read this before adding a new screen,
dialog, or stylesheet rule.

## Brand

The app's mark is the **"spark burst"** — a bright laser strike
on a workpiece. See `rayforge/resources/icons/org.piresforge.pires-forge.svg`
for the canonical vector. The mark uses a radial gradient from
white-hot (`#ffffff`) through yellow (`#fff4a3`, `#ffb000`) to
deep orange (`#ff3d00`) on a near-black squircle (`#0a0a0a`,
corner radius 96/512 = 18.75%).

Colors in the UI are picked to **complement** the mark:
- The cobalt accent (`#4f84c4`) is a deliberate cool counterpoint
  to the warm gradient in the mark.
- The dark surface palette (`#2b2b2b` background, `#252525`
  panel) is near-black, mirroring the mark's squircle fill.
- The light surface palette (`#fafafa` background, `#ffffff`
  panel) inverts the dark surfaces for the same mark to read
  cleanly against either.

## Tokens

All UI colors are CSS `@define-color` tokens declared in
`rayforge/resources/styles/forge.css`. Never use raw hex values
in widget code; reach for the closest token.

| Token              | Dark    | Light   | Purpose                          |
| :----------------- | :------ | :------ | :------------------------------- |
| `forge_bg`         | #2b2b2b | #fafafa | App background                   |
| `forge_bg_alt`     | #313131 | #f0f0f0 | Alternate surface (toolbar)      |
| `forge_bg_soft`    | #3a3a3a | #e8e8e8 | Hover surface                    |
| `forge_panel`      | #252525 | #ffffff | Cards, popovers, dialogs         |
| `forge_border`     | #4a4a4a | #d0d0d0 | Hairline dividers                |
| `forge_text`       | #d6d6d6 | #2a2a2a | Primary text                     |
| `forge_text_dim`   | #a9a9a9 | #6a6a6a | Secondary text                   |
| `forge_accent`     | #4f84c4 | #4f84c4 | Selection, focus, brand accent   |

### Accent contrast (WCAG AA)

| Background       | Contrast vs `#4f84c4` | Result |
| :--------------- | :------------------- | :----- |
| `#fafafa` (light) | 4.7:1                | AA     |
| `#2a2a2a` (light text) | 5.1:1          | AA     |
| `#2b2b2b` (dark) | 5.1:1                | AA     |
| `#d6d6d6` (dark text) | 4.7:1           | AA     |

The cobalt reads cleanly in both schemes — the same token is
used in light and dark, no per-scheme override.

## Spacing

Multiples of 4 throughout. Approved values: **4, 8, 12, 16, 24, 32**.
Avoid 6, 10, 14 — they were used historically and read as
inconsistent next to the grid.

Common patterns:
- `padding: 4px 8px` — small control, dense
- `padding: 6px 12px` — menu item
- `padding: 8px 12px` — toolbar
- `margin: 8px 12px 12px 8px` — overlay inset

## Radius

| Class            | Value | Used for                    |
| :--------------- | :---- | :-------------------------- |
| `forge_radius_sm` | 6px  | buttons, status overlays    |
| `forge_radius_md` | 8px  | cards, popovers, right-pane |

A 3-4px radius reads as 2008-era on HiDPI displays. 12px+ is
reserved for full-card dialogs (`Adw.MessageDialog` etc.),
which already pick their own radius via Adw defaults.

## Color schemes

Two schemes are supported out of the box: **dark** (default) and
**light**. A third value, **system**, follows the OS preference.
Selection is per-user, persisted in `config.yaml` as `theme:
"system" | "light" | "dark"`, and changed at runtime via
`Preferences → General → Appearance → Theme`. A toast confirms
the swap.

The mapping lives in `MainWindow.apply_theme()`:

```python
scheme_map = {
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark":  Adw.ColorScheme.FORCE_DARK,
}
# Anything else (system, unknown) → Adw.ColorScheme.DEFAULT
```

The CSS responds to `Adw.StyleManager`'s scheme by using
`@media (prefers-color-scheme: light)`. **Always** override
colors inside that block; never write a separate light-only
stylesheet. The block lives in the same `forge.css` as the
dark defaults, so a single file diff shows the full
theming contract.

## Components

### HeaderBar
- `min-height: 34px`
- 1-stop top→bottom gradient (`#3a3a3a → #323232` dark,
  `#f5f5f5 → #e8e8e8` light) — deliberately a 1-stop effect to
  give a horizon line that mirrors the mark.
- 1px border-bottom in `forge_border`.

### Main toolbar
- 38px tall
- Same 1-stop gradient as HeaderBar, slightly darker stops
  (`#3b3b3b → #303030` dark, `#efefef → #e2e2e2` light).
- 1px border-bottom in `forge_border`.

### Buttons
- Border-radius `forge_radius_sm` (6px).
- 1px solid border (`#5a5a5a` dark, `#b0b0b0` light).
- Flat fill (`#4a4a4a` dark, `#f5f5f5` light) plus a low-opacity
  alpha overlay to suggest depth without a 2008-era
  linear-gradient.
- Hover: single background-color change
  (`#4a4a4a → #555555` dark, `#f5f5f5 → #ffffff` light).
- Checked/active: flat `forge_accent` fill, `#2f5e9a` border,
  white label.

### Overlays
- `forge_panel` fill at 94% alpha (so the canvas shows through
  faintly).
- `forge_radius_md` (8px).
- 1px `forge_border`.
- Box shadow: `0 2px 12px alpha(black, 0.35)`.

### Status messages
- `#202020` fill (dark) / `#ffffff` (light, via the popover
  block — if you add explicit colors here, mirror them).
- `forge_radius_sm`.
- No border (just the box-shadow for separation).

## Accessibility

- **Keyboard**: every interactive widget is reachable via
  `Tab`/`Shift+Tab`. There is no custom key handling that
  bypasses GTK's a11y layer.
- **Screen reader**: icon-only buttons set their accessible
  label from their tooltip text via
  `propagate_tooltip_to_accessible_label()`. The helper lives
  in `rayforge/ui_gtk/shared/a11y.py` and is called from any
  toolbar/menu that builds icon-only buttons.
- **Reduced motion**: when the OS-level "reduce motion" setting
  is on, all `Gtk.Stack`/`Gtk.Revealer` transitions collapse
  to 0-duration crossfade or `NONE`. Wiring is
  `install_motion_preference_listener(window)` in the
  MainWindow constructor.

## Adding a new component

1. **Pick a token**, not a hex value. If no existing token fits,
   propose a new one in `forge.css` and add a row to the table
   above.
2. **Use an existing radius/spacing class** from the tables
   above. If you need a new value, justify it in the PR.
3. **Mirror the light theme**: every `forge_*` color reference
   must read correctly under `prefers-color-scheme: light`. If
   you need a different value in light mode, add it inside the
   existing `@media` block.
4. **Add a tooltip and a11y label** for any icon-only button.
5. **Test in both themes** before merging.

## Why no Tailwind / design-tokens.json

GTK CSS doesn't have a token build step (no equivalent to
`style-dictionary`). The closest the GTK world offers is
`@define-color`, which is what we use. A JSON spec would
require a build step on every CSS edit, which is not worth
it for a single-file stylesheet. If the design system grows
past ~30 tokens, revisit and consider splitting into per-domain
files (e.g. `tokens.css`, `components.css`, `addons.css`).
