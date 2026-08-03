# Security Policy

This document describes the security policy for
**[Pires Forge](https://github.com/yuri-schmaltz/pires-forge)** — an
independent, single-maintainer fork of the
[Rayforge](https://github.com/barebaric/rayforge) project maintained
by [Yuri Schmaltz](https://github.com/yuri-schmaltz).

Pires Forge inherits the upstream security model for the parts of the
code that are shared. The rebrand-focused changes in Pires Forge do
not introduce new attack surface.

## Supported versions

Pires Forge ships patched releases on a rolling basis. Security fixes
land in `main` first, then are tagged as a new release.

| Version | Supported | Notes |
| ------- | --------- | ----- |
| `1.0.0` (latest) | ✅ Active | First stable release of Pires Forge |
| `0.1.0` | ⚠️ Critical fixes only | Pre-rebrand rebase with `Rayforge` name |
| Upstream `1.9.0` (`barebaric/rayforge`) | ❌ Not supported by us | Use the fork instead |

We do **not** support:
- Pre-`1.0.0` versions.
- The `my-rayforge` repository name (renamed to `rayforge`, then to
  `pires-forge` in 2026).
- The original `barebaric/rayforge` repository directly — that is the
  upstream project, which is maintained by Samuel Abels and
  contributors; the Pires Forge rebrand lives here at
  `yuri-schmaltz/pires-forge`.

## Reporting a vulnerability

**Do not** open a public GitHub issue for security bugs.

Email: **<security@yuri-schmaltz.dev>**

Please include:
- A short description of the issue
- Steps to reproduce (proof of concept if possible)
- The commit / tag / version affected
- Your assessment of the impact

We will acknowledge receipt within 72 hours and aim to provide a
fix or mitigation within 30 days, depending on severity.

## Threat model

Pires Forge is a desktop application that:

- Reads **untrusted file formats** (SVG, DXF, PDF, PNG/JPG, BMP,
  LightBurn `.lbrn`/`.lbrn2`, Ruida `.rd`).
- Writes **G-code files** for laser cutters/engravers.
- Optionally sends G-code to **local network** devices (GRBL serial,
  GRBL/Smoothieware telnet, Marlin serial, Ruida UDP, OctoPrint HTTP).
- Optionally captures **USB camera** input for workpiece alignment.
- Does **not** auto-update, does **not** phone home, and does **not**
  collect telemetry by default.

### Security boundaries

| Boundary | Trust | Notes |
| -------- | ----- | ----- |
| **SVG / DXF / PDF / PNG / BMP** import | Untrusted | Parsed with `defusedxml` (when applicable) to block billion-laughs, XXE, and DTD-SSRF attacks. |
| **LightBurn `.lbrn` / `.lbrn2`** import | Untrusted | Parsed with `defusedxml` since the LightBurn format is XML-based. |
| **G-code output** | Trusted | Generated locally; not signed. |
| **Network I/O** to machines | Trusted LAN | The user explicitly configures the machine address. No inbound network listeners. |
| **Camera input** | Trusted OS device | Captured via the OS camera stack; no network access. |
| **Filesystem** | Trusted user space | Project files use `.ryp` (zip-based) with a manifest; arbitrary file extraction is constrained to the project directory. |
| **Configuration** (`~/.config/rayforge/`) | Trusted user space | YAML config; the parser rejects unknown keys but does NOT validate the schema. Do not load untrusted YAML configs. |
| **Update check** | Disabled by default | When enabled, queries the GitHub Releases API of `yuri-schmaltz/pires-forge` for new versions. Opt-in via Settings → Preferences. |

### Out of scope

- Vulnerabilities in **upstream Rayforge** that we have already
  patched in Pires Forge (report upstream if you also use it).
- Vulnerabilities in **third-party libraries** (Python packages,
  GTK, etc.) — report to the upstream maintainer.
- Denial of service against the local machine via malformed input
  (Pires Forge runs as a normal user; the OS limits the blast radius).

## Hardening

The Pires Forge build pipeline runs the following security gates:

- **`bandit`** — static analysis for common Python security issues
  (B101, B102, B104, B310, B324, B404/B405, B603/B606, etc.). The
  full set of suppressed checks with justification is in `.bandit`.
- **`pip-audit`** — checks the dependency tree for known CVEs.
- **`defusedxml`** — required runtime dependency for untrusted XML
  parsing (LightBurn, SVG fallback).
- **Reproducible builds** — `pixi.lock` pins the entire dep tree.

The Debian package additionally enforces:

- `python3-defusedxml` in `Depends:` (so apt refuses to install
  Pires Forge on a system without it).
- Lintian overrides documented in `debian/lintian-overrides` for
  known false positives.

## Disclosure policy

We follow **coordinated disclosure**: please give us a reasonable
time to patch before public disclosure. We will credit the reporter
in the release notes unless they prefer to remain anonymous.

## Contact

- Maintainer: Yuri Schmaltz
- Email: <security@yuri-schmaltz.dev>
- GitHub: <https://github.com/yuri-schmaltz/pires-forge>
- Issues (non-security): <https://github.com/yuri-schmaltz/pires-forge/issues>
