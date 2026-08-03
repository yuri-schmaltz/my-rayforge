# Documentation

User-facing documentation for Pires Forge.

## Getting Started

- [`INSTALLATION.md`](INSTALLATION.md) — Install pre-built binaries
  (`.deb` for Ubuntu 24.04, `.dmg` for macOS, `.exe` for Windows).
- [`docs/screenshots/README.md`](screenshots/README.md) — A small
  gallery of app screenshots (placeholder; the upstream Rayforge
  website is the canonical gallery).

## Building from Source

- [`BUILDING.md`](BUILDING.md) — Build the app and the three
  platform installers from source using `pixi` and the platform
  build scripts.

## Reference

- [`DIAGNOSTICS.md`](DIAGNOSTICS.md) — Enable debug logging,
  capture crash logs, and report issues with actionable
  diagnostics.
- [`CODE_SIGNING.md`](CODE_SIGNING.md) — Sign the Windows
  installer and the macOS `.app` bundle with a developer
  certificate. **Read this before distributing a release**
  — without signing, users see SmartScreen / Gatekeeper
  warnings.

## Process

- [`RELEASE.md`](RELEASE.md) — The full release process: how to
  bump the version, build installers, publish a GitHub release,
  and what to verify after the release is out.

## Security

Security policy and contact info live at
[`../.github/SECURITY.md`](../.github/SECURITY.md). For sensitive
bugs, email **<security@yuri-schmaltz.dev>** directly.
