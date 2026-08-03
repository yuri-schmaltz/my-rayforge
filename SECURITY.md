# Security Policy

This document describes the security policy for the
**`yuri-schmaltz/rayforge`** fork (the resilience fork of
[Rayforge](https://github.com/yuri-schmaltz/pires-forge)).

For the security model of upstream Rayforge, see
[yuri-schmaltz/pires-forge SECURITY.md](https://github.com/yuri-schmaltz/pires-forge/blob/main/SECURITY.md).
The fork inherits the upstream model for the parts of the code that
are shared; the differences are documented in [SECURITY_AUDIT.md](SECURITY_AUDIT.md).

## Supported versions

The fork ships patched releases on a rolling basis. Security fixes
land in `main` first, then are tagged as a new `1.9.0+resilience.X`
release.

| Version             | Supported          |
| ------------------- | ------------------ |
| `1.9.0+resilience.4` (latest) | ✅ Active |
| `1.9.0+resilience.3`          | ⚠️ Critical fixes only |
| `1.9.0+resilience.1` / `.2`   | ❌ End of life |
| `1.9.0` (upstream, unpatched) | ❌ Use the fork's release |

We do **not** support:
- Pre-1.9.0 versions (the resilience layer was introduced in 1.9.0).
- Upstream `1.9.0` directly (use the fork's `1.9.0+resilience.X`).
- The `my-rayforge` repository name (renamed to `rayforge` in
  July 2026).

## Reporting a vulnerability

**Please do not open a public GitHub issue for security bugs.**

Send a report to **`security at yuri-schmaltz dot dev  # placeholder; replace with a real mailbox when one is set up`** (PGP key below).
Include:

- A description of the vulnerability and its impact.
- Steps to reproduce (proof-of-concept code or screenshots welcome).
- The version affected (`rayforge --version` or check
  `Settings → About` in the app).
- Your name / handle for the credits (optional — anonymous reports
  are accepted).

We will:
- Acknowledge within **3 business days**.
- Triage within **7 days** (severity, affected versions, scope).
- Ship a fix in the next `1.9.0+resilience.X` release, or sooner
  for critical issues.

For critical issues (RCE, auth bypass, data exfiltration), we may
ship a hotfix release out-of-band.

### PGP key

```
-----BEGIN PGP PUBLIC KEY BLOCK-----
[Placeholder — replace before publishing]
-----END PGP PUBLIC KEY BLOCK-----
```

(Forking: the maintainer will publish the actual key when this
file is committed. Until then, the report can be sent in cleartext
with the understanding that the email is in transit over an
untrusted channel.)

## Security advisories

Past advisories are published as
[GitHub Security Advisories](https://github.com/yuri-schmaltz/rayforge/security/advisories)
on the fork. The fork uses GHSA IDs; the cross-references with the
upstream project (where relevant) are noted in the advisory body.

## Threat model

The fork's threat model is the same as upstream's, with two
additions:

1. **The fork ships a custom version scheme** (`1.9.0+resilience.X`)
   that mixes upstream's `1.9.0` and the fork's patches. The
   auto-update checker (`rayforge/updater.py`) and the
   version-comparison logic in `rayforge/version.py` are the
   single point of truth for "is the installed version newer than
   the latest known release?" — bugs there are critical. The
   SECURITY_AUDIT.md document covers the review checklist for
   these files.

2. **The fork's CI/CD pipeline is in the maintainer's GitHub
   account, not the upstream's.** A compromise of the maintainer's
   GitHub credentials could lead to malicious binaries being
   published via the existing release workflow. Mitigations:
   - The release workflow does not consume any external secrets
     (no PyPI token, no signing keys, no codecov token).
   - The `package-deb` and `package-exe` workflows only run on
     the fork's branches (the upstream `publish-deb.yml` and
     `publish-snap-store.yml` are gated to `yuri-schmaltz/pires-forge`).
   - All CI jobs run on `ubuntu-latest` (no self-hosted runners).

## Security-relevant changes

The following changes from upstream are security-relevant. Each is
documented in [SECURITY_AUDIT.md](SECURITY_AUDIT.md) with the full
review checklist:

- **PR #13**: sketcher `ParameterContext` now uses the AST-whitelisted
  `safe_evaluate` instead of bare `eval()`. Fixes a sandbox-escape
  vulnerability via `.lbrn` and `.sketch` files.
- **PR #14**: `hashlib.sha1(blob)` → `hashlib.sha1(blob,
  usedforsecurity=False)` for the cache-key hash in
  `rayforge/pipeline/intent_builder.py`.
- **PR #15**: SVG and LightBurn XML parsers now use `defusedxml`
  to block billion-laughs, XXE, and DTD-SSRF payloads.
- **PR #17**: bumped 3 dependencies to fix 12 CVEs in GitPython,
  pypdf, and cairosvg. Fixed a `project.version must be pep440`
  error in the `.deb` build pipeline that was preventing the
  build from completing (and thus preventing the security fix
  from reaching end users).
- **PR #18**: 17 `try-except-pass` cases were either given
  `logger.debug(...)` for diagnostic value, or marked with
  `# noqa: S110` where the silent pass is intentional (signal
  cleanup, shutdown teardown).

## Known intentional design choices (trust boundaries)

These are **features, not vulnerabilities**. They are documented
in [SECURITY_AUDIT.md](SECURITY_AUDIT.md#-documented-security-boundaries)
with the full review checklist. Reviewers should consult that
section before approving changes to the affected files.

- **`--uiscript <file.py>`** in `rayforge/uiscript.py`: the CLI
  flag takes a path to a Python script and `exec()`s it in a
  background thread inside the running application. This is
  equivalent to running `python -c "..."` with the user's own
  credentials. It is **not safe to expose in a multi-tenant
  environment** (kiosks, shared hosts, web services that pass
  untrusted input to `--uiscript`).

- **HTTP `Authorization: token <PAT>` in the bot's push URL**:
  the fork's release workflow uses HTTPS git URLs with embedded
  GitHub tokens. The tokens are scoped per-session, scoped to
  the fork's repo only, and discarded after each push. They
  never appear in PR bodies, commit messages, or file content.

## Out of scope

The following are **not** in the fork's threat model:

- **The auto-update network channel**: the update checker uses
  HTTPS to `api.github.com` (via the resilient HTTP layer). MITM
  attacks against the user's local network or the GitHub API
  are out of scope. The fork does not pin GitHub's certificate
  chain beyond what the system trust store provides.

- **The build host's security**: the `.deb`, `.dmg`, and `.exe`
  binaries are built on GitHub-hosted runners (`ubuntu-latest`,
  `macos-latest`, `windows-latest`). A compromise of GitHub Actions
  is out of scope.

- **The user's local security**: if the user installs the
  binary into a directory writable by other users, or runs it
  with elevated privileges, the local security model applies.

- **Upstream's security fixes**: the fork syncs with upstream
  periodically. If upstream ships a security fix between syncs,
  the fork will be a release or two behind. Check the
  [upstream release notes](https://github.com/yuri-schmaltz/pires-forge/releases)
  if you need the latest.

## Acknowledgments

Security researchers who report valid vulnerabilities to the fork
are credited in the corresponding GitHub Security Advisory (unless
they prefer to remain anonymous). Thank you for keeping the fork's
users safe.
