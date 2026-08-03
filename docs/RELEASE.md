# Release Process

This document describes how to cut a new release of Pires Forge.
The process is **single-maintainer** and **manual**; there is no
automated release bot.

## Versioning

- Internal version: `MAJOR.MINOR.PATCH` (PEP 440, e.g. `1.0.0`).
- Git tag: same as the internal version with a `v` prefix
  (e.g. `v1.0.0`).
- The build workflows strip the `v` from the tag to obtain the
  internal version (see the `Set Version` step in each build
  workflow).

Pires Forge follows [semver](https://semver.org/) for the major /
minor / patch parts. The `+resilience.X` suffix used in the
initial 1.9.0 series is **deprecated** — releases from 1.0.0
onward use a clean `MAJOR.MINOR.PATCH` version.

## Pre-release checklist

1. **Run the full test suite** locally:
   ```bash
   pixi run test
   ```
   All tests must pass before cutting a release.

2. **Update the changelog** (`CHANGELOG.md`): add a new section
   at the top with the version, date, and a short summary of
   user-visible changes. Group entries as
   `Added / Changed / Fixed / Removed`.

3. **Bump the version** in `pyproject.toml`:
   ```toml
   [project]
   name = "pires-forge"
   # dynamic = ["version"]   # Old: versioning via setuptools-git-versioning
   version = "X.Y.Z"
   ```
   Then add a new entry to `debian/changelog` using `dch`:
   ```bash
   cd debian
   dch --newversion "X.Y.Z-1" "New upstream release X.Y.Z"
   ```

## Build the installers

The three platform workflows trigger on tag push. To build them
manually for testing before publishing a release:

```bash
# Linux .deb (Ubuntu 24.04)
./scripts/build-deb.sh

# macOS universal .dmg
./scripts/mac/mac_build.sh

# Windows .exe NSIS installer (from MSYS2 shell)
scripts/win/win_build.sh
```

Each script writes its output to `dist/`:

- `dist/pires-forge-linux.deb`
- `dist/pires-forge-macos.dmg`
- `dist/pires-forge-windows.exe`

## Tag and push

Once the changelog is updated and you're ready to publish:

```bash
# Commit the changelog + version bump
git add -A
git commit -m "release: vX.Y.Z"

# Tag the release
git tag -a vX.Y.Z -m "Pires Forge vX.Y.Z"

# Push the tag — this triggers the three build workflows
git push origin vX.Y.Z
```

The workflows (`.github/workflows/build-deb.yml`,
`build-macos-universal.yml`, `build-exe.yml`) will run, and each
produces one installer asset uploaded to the GitHub release.

## Create the GitHub release

After the build workflows finish (5–15 min):

1. Open `https://github.com/yuri-schmaltz/pires-forge/releases`
2. Click **"Draft a new release"**
3. Choose the `vX.Y.Z` tag
4. Title: `Pires Forge X.Y.Z`
5. Description: copy the relevant section from `CHANGELOG.md`
6. **Do not** attach files manually — the build workflows
   already uploaded the 3 platform installers as release assets.
7. Click **"Publish release"**

## Post-release verification

Within 24 hours, ideally within an hour, verify:

- [ ] The release appears at
  `https://github.com/yuri-schmaltz/pires-forge/releases/tag/vX.Y.Z`
- [ ] All 3 assets are attached:
  - `pires-forge-linux.deb`
  - `pires-forge-macos.dmg`
  - `pires-forge-windows.exe`
- [ ] The asset URLs are not URL-encoded versions (GitHub
  sometimes encodes `+` as `.`; the build workflow should
  already produce correct URLs but double-check the download
  works)
- [ ] On Linux, install the `.deb` and run `pires-forge` from
  the application menu (and from the command line) to confirm
  the binary name, `.desktop` file, MIME types, and translations
  all work end-to-end.

## Force-merging hotfixes

If a release has a critical bug and a fix needs to ship before
the next planned release, you can add commits to the existing
release tag by force-moving the tag:

```bash
# Fix the bug
git commit -m "fix: <description>"

# Move the tag
git tag -d vX.Y.Z
git tag -a vX.Y.Z -m "Pires Forge vX.Y.Z"
git push --force origin vX.Y.Z
```

This rewrites the tag to point at the fix commit. **Use this
sparingly** — it breaks anyone who has already downloaded the
original release and forces them to re-download.

For non-critical fixes, prefer a follow-up patch release
(`vX.Y.(Z+1)`) over rewriting the existing tag.
