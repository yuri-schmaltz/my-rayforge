# Diagnostics and Crash Logs

This document explains how Rayforge handles diagnostics and
"crash logs". Rayforge is **privacy-respecting by design**:
nothing is sent anywhere automatically. This page documents
the opt-in model.

## The opt-in model

Rayforge has **no automatic crash reporting**. There is no
Sentry, no telemetry, no remote upload, no background process
that captures state. The only diagnostic feature is the
**Save Debug Log** menu action, which the user triggers
manually:

- **Help → Save Debug Log** (or via the keyboard shortcut if
  configured)
- A dialog appears explaining exactly what is included
- The user clicks Save and chooses where to save the .zip
- The user then decides what to do with the file (most users
  attach it to a GitHub issue or send it to the maintainer)

The user is in control of the entire flow. Nothing happens
without an explicit user action.

## What is in the bundle

The debug .zip contains:

| File | Content | Why |
|------|---------|-----|
| `session-YYYY-MM-DD_HH-MM-SS.log` | Latest session log (INFO+ level) | What happened before the issue |
| `system_info.txt` | OS, Python, PyGObject, Gtk, all installed deps | Reproduce on your machine |
| `active_machine.yaml` | Current machine profile | Machine config relevant to the issue |
| `app_config.yaml` | App config (no secrets) | Replicate the user's environment |
| `all_machines.yaml` | All user-defined machines | Multi-machine setups |
| `custom_dialects.yaml` | Custom G-code dialects | Reproduce dialect-specific issues |
| `addons.yaml` (if exists) | Addon config | Addon-related issues |
| `project.ryp` (optional) | Current project file | Issues that need the project to reproduce |

**What is NOT in the bundle** (privacy):

- No API keys, OAuth tokens, or passwords
- No machine IP addresses or hostnames
- No file paths from the user's filesystem (only filenames)
- No telemetry about which features you use
- No telemetry about how long you used the app
- No information about the contents of your other projects
- No analytics from the upstream `analytics.barebaric.com`
  service (the analytics only count first-launch events and
  are governed by the separate "Help improve Rayforge" prompt)

## How to use the bundle

If you hit a bug and want to report it:

1. **Reproduce the issue** with the current session. The log
   is in the most recent `session-*.log` file in the log dir.
2. **Open Help → Save Debug Log**
3. **Uncheck "Include current project"** if your project
   contains sensitive dimensions or proprietary artwork.
4. Click **Save** and choose a location
5. **Open a GitHub issue** at
   https://github.com/yuri-schmaltz/rayforge/issues
6. **Attach the .zip** to the issue
7. The maintainer will review the contents and follow up

## Where the log lives

The latest session log is always at:

- **Linux**: `~/.local/state/rayforge/log/session-*.log`
- **macOS**: `~/Library/Logs/rayforge/session-*.log`
- **Windows**: `%LOCALAPPDATA%\rayforge\rayforge\Logs\session-*.log`

Only the **5 most recent** session logs are kept (older ones
are deleted automatically to avoid filling the disk). The
debug bundle includes only the most recent one.

## When to NOT use the bundle

- **If your project contains confidential information**
  (proprietary artwork, customer-specific dimensions,
  trade-secret designs): uncheck "Include current project"
  before saving. The project file is the only part of the
  bundle that contains user-specific data. The logs and
  system info are generic.
- **If you don't want to share your machine profile**:
  delete `active_machine.yaml` and `all_machines.yaml`
  from the .zip before attaching to the issue. The
  maintainer can usually reproduce issues without them.
- **If you don't want to share your app config**: delete
  `app_config.yaml`. The maintainer can usually reproduce
  without it.
- **If you're worried about a specific dependency version**:
  the `system_info.txt` file lists all installed Python
  packages. If you don't want a particular package version
  visible, edit the file before attaching.

## Privacy summary

| Question | Answer |
|----------|--------|
| Does Rayforge send anything automatically? | **No.** |
| Does Rayforge run a background process that captures state? | **No.** |
| Does the debug bundle include API keys or tokens? | **No** (the dump manager never touches them). |
| Does the debug bundle include the project file? | Only if the user checks the box. |
| Can the user edit the bundle before sharing? | **Yes** (it's a regular .zip file). |
| Does the maintainer have access to your system without your action? | **No.** |
| Is there a "crash report" auto-sent on uncaught exception? | **No.** |

## See also

- `SUPPORT.md`: how to report issues
- `SECURITY.md`: security disclosures
- `CHANGELOG.md`: mentions if the diagnostic flow changes
