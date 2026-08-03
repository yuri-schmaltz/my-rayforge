# Security Policy

Pires Forge is a personal fork maintained by a single developer
([Yuri Schmaltz](https://github.com/yuri-schmaltz)). This page
documents how to report a vulnerability and what to expect.

## Supported Versions

Only the latest release receives security fixes. Older releases
are not patched.

| Release | Supported          |
| :------ | :----------------- |
| Latest  | ✅                 |
| Older   | ❌                 |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security bugs.**

Email **<security@yuri-schmaltz.dev>** with:

- A short description of the issue
- Steps to reproduce (or a minimal test case)
- Affected version and platform (Linux / macOS / Windows)

### Response

- **Acknowledgement** within 72 hours
- **Triage decision** within 7 days (accepted / won't fix / needs more info)
- **Fix** delivered in the next release, or sooner if the issue is severe
- **Credit** in the release notes (unless you ask to stay anonymous)

## Out of Scope

The following are not security issues and should be reported
via the regular [issue tracker](../../issues) instead:

- Feature requests
- General bugs that don't have a security impact
- Build failures on unsupported platforms
- Translation errors

## Threat Model (high level)

Pires Forge handles user-provided files (SVG, DXF, PDF, images,
project files) and renders them in a GTK application. The fork
ships hardening against the following classes of attack:

- **XML external entities (XXE)** and **billion-laughs** in SVG
  and project files: all untrusted XML is parsed with
  `defusedxml`.
- **Command injection** in CLI / external-tool calls: validated
  paths, argv-form subprocess invocations.
- **Update check by default**: disabled. The user must opt in
  via the settings dialog if they want to check for new versions
  against the fork's release API.
- **Telemetry**: disabled (`UMAMI_URL` and `UMAMI_WEBSITE_ID`
  are empty).

This is a small personal fork, not a hardened enterprise
product. The mitigations above are best-effort and reviewed
periodically, but the project does not run a formal
vulnerability-management program.
