# Diagnostics and Crash Logs

This document explains how [Pires Forge](https://github.com/yuri-schmaltz/pires-forge)
handles diagnostics and "crash logs". Pires Forge is
**privacy-respecting by design**: nothing is sent anywhere
automatically. This page documents the opt-in model.

## The opt-in model

Pires Forge has **no automatic crash reporting**. There is no
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
| ---- | ------- | --- |
| `rayforge.log` | Recent log output (last N lines) | Helps diagnose runtime errors |
| `config.yaml` | The user's config file (PII-redacted) | Helps reproduce bugs related to settings |
| `machine_profiles/*.yaml` | The user's machine profiles (PII-redacted) | Helps diagnose device-driver issues |
| `addon_registry.yaml` | The list of installed addons | Helps reproduce addon compatibility issues |
| `version.txt` | The Pires Forge version | Identifies which build the user is on |
| `python_version.txt` | The Python version | Helps diagnose platform-specific bugs |
| `platform.txt` | `linux-64`, `macos-arm64`, etc. | Identifies the user's platform |
| (optional) `current_project.ryp` | The currently open project | Helps reproduce issues with specific files |

## What is **NOT** in the bundle

The following are **excluded** by the dump logic:

- **API keys** for AI providers, OctoPrint, etc. (these are stored
  in the system keyring, not the config file).
- **Camera captures** (these can contain sensitive data; the user
  should manually attach them if needed).
- **Other users' files** (the bundle only includes files from
  the current user's config directory).
- **The system clipboard** contents.
- **Network traffic** (Pires Forge does not capture this).
- **Any telemetry** — there is none to capture.

## How to use the debug bundle

1. Reproduce the bug with **Help → Save Debug Log** open.
2. Click **Save** to write the bundle to your disk.
3. **Open a GitHub issue** at
   <https://github.com/yuri-schmaltz/pires-forge/issues/new/choose>
   and attach the `.zip` file.
4. The maintainer will review the bundle locally and may ask
   follow-up questions. The bundle is **not** automatically
   uploaded anywhere.

## Where are the logs?

If you don't want to generate a full bundle, you can also find
the raw log file at:

- **Linux**: `~/.local/share/rayforge/rayforge.log`
- **macOS**: `~/Library/Application Support/rayforge/rayforge.log`
- **Windows**: `%APPDATA%\rayforge\rayforge.log`

## Telemetry and analytics

Pires Forge has **no telemetry**. The
`rayforge.usage.UsageTracker` module exists in the source tree for
backward compatibility with the upstream Rayforge, but the
`UMAMI_URL` and `UMAMI_WEBSITE_ID` constants are set to empty
strings in `rayforge/config.py`. The tracker is a no-op.

To verify, open **Settings → Preferences → Privacy** in the app:
there is no "Send anonymous usage data" toggle because there is
nothing to send.

## Security contact

For sensitive bugs (security vulnerabilities, data loss, etc.),
email **<security@yuri-schmaltz.dev>** instead of opening a public
GitHub issue.
