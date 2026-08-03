# Snap Store Submission Guide

This document explains how to submit the Rayforge snap
package to the Snap Store (snapcraft.io/rayforge).

## The fork's situation

The fork `yuri-schmaltz/rayforge` is a community fork. The
upstream `yuri-schmaltz/pires-forge` already publishes to the Snap
Store under the same snap name (`rayforge`), but they own
the Snapcraft credentials.

The fork's maintainer has **two options**:

1. **Submit to a different snap name** (e.g. `rayforge-fork`
   or `rayforge-community`). This requires reserving the
   new name on https://snapcraft.io and using the fork's
   own Snapcraft credentials.
2. **Contact upstream** and ask to take over the existing
   `rayforge` name. This is a coordination step with the
   upstream maintainer.

This document covers option 1 (the cleanest and most
self-contained).

## Prerequisites

- A Snapcraft account (free): https://snapcraft.io/account
- The fork's GitHub repository
- A release tag in the format `X.Y.Z+resilience.N` (or any
  other PEP 440-compliant version)

## Step 1: Reserve the snap name

1. Go to https://snapcraft.io/publisher
2. Click "Register a new snap name"
3. Enter the name you want to use (e.g. `rayforge-fork`)
4. Snapcraft will check that the name is available

## Step 2: Create a Snapcraft App

1. Go to https://snapcraft.io/apps
2. Click "Create app" (or click the reserved name)
3. Choose a default track (typically `latest`)
4. Note the **store ID** (you'll need it for the next step)

## Step 3: Generate a Snapcraft store login

There are two options:

### Option A: Snapcraft credentials JSON (recommended for CI)

```bash
snapcraft login --with login
# This opens a browser, you log in, then it writes the
# credentials to ~/.snapcraft/login.json
```

Then add the contents of `~/.snapcraft/login.json` as a
secret called `SNAPCRAFT_STORE_CREDENTIALS` in your fork's
GitHub settings:
https://github.com/yuri-schmaltz/rayforge/settings/secrets/actions

The existing workflow
(`.github/workflows/publish-to-snap-store.yml`) is already
set up to use this secret. It just needs the upstream
guard removed (or a separate workflow per fork).

### Option B: Manual upload (no CI)

If you don't want to set up CI credentials, you can:

1. Download the verified `.snap` artifact from the GitHub
   Actions run (see Step 4)
2. Go to https://snapcraft.io/rayforge-fork/releases
3. Click "Upload a revision"
4. Drag the `.snap` file
5. Choose the release channel (stable, beta, edge, candidate)
6. Click "Publish"

## Step 4: Trigger the snap build

The fork's CI workflow `.github/workflows/verify-snap.yml`
runs on every release tag. To trigger it:

1. Create a release tag in the fork:
   ```bash
   git tag 1.9.0+resilience.5
   git push origin 1.9.0+resilience.5
   ```
2. GitHub Actions will:
   - Build the .snap
   - Install it in a clean LXD container
   - Run smoke tests (`--help`, `--version`, headless launch)
   - Upload the .snap as a workflow artifact named
     `rayforge-snap`
3. If the build fails, the maintainer is alerted via the
   failed CI check.
4. If the build succeeds, download the artifact and upload
   it to Snapcraft (Option B) or set up CI (Option A).

## Step 5: Set up automatic publishing (optional)

If you want the next release to publish automatically:

1. Add the `SNAPCRAFT_STORE_CREDENTIALS` secret (Option A
   above)
2. Modify `.github/workflows/publish-to-snap-store.yml`:
   - Remove the `if: github.repository == 'yuri-schmaltz/pires-forge'`
     guard from the `build-publish-snap` job
   - Or copy it to a new workflow file in the fork

The existing publish step in the upstream workflow is:

```yaml
- name: Publish to Snapcraft
  if: steps.release_info.outputs.channel != ''
  uses: snapcore/action-publish@v1
  env:
    SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.STORE_LOGIN }}
  with:
    snap: ${{ steps.build.outputs.snap }}
    release: ${{ steps.release_info.outputs.channel }}
```

Note: upstream uses secret name `STORE_LOGIN`. The fork can
use any name. The cleanest approach is `SNAPCRAFT_STORE_CREDENTIALS`
to match the snapcraft.io convention.

## Step 6: Verify the published snap

After publishing, verify the snap is installable from the
store:

```bash
# On a Linux machine with snapd installed
sudo snap install rayforge-fork
rayforge --version
```

The output should show the version you just published.

## Snap store requirements

The snapcraft.yaml at `snap/snapcraft.yaml` already meets
all the requirements for Snap Store submission:

- **name**: `rayforge` (will be `rayforge-fork` if you
  rename)
- **base**: `core24` (latest stable, supported)
- **confinement**: `strict` (most secure, requires plugs
  to be explicit)
- **grade**: defaults to `stable` (no need to set)
- **common-id**: `org.rayforge.rayforge` (the D-Bus name,
  matches the .desktop file)
- **plugs**: all the right interfaces for a desktop app
  with serial port access (laser cutters)
- **slots**: D-Bus session for inter-process communication

## Confinement caveats

The snap uses **strict confinement** (most secure). This
means:

- The app can only access files in the user's home
  directory (`home` plug).
- Network access is explicit (`network` plug).
- The serial port is accessible (`serial-port` plug).
- The camera is accessible (`camera` plug).
- USB removable media is accessible (`removable-media` plug).

If the user reports that a feature doesn't work, the most
likely cause is a missing plug. Add it to `snap/snapcraft.yaml`
and rebuild.

## Updating the snap

When the user installs a new version:

1. Build the new snap (via the workflow or manually)
2. Upload the new `.snap` to the Snap Store
3. Bump the release channel (e.g. from `beta` to `stable`)
4. Users with auto-update enabled get the new version
   within ~6 hours

## Channel strategy

The existing publish workflow uses three channels:

- **edge**: every push to `main` (auto-update off by
  default; only the maintainer installs this for testing)
- **beta**: every tag matching `X.Y.Z-` (pre-release)
- **stable**: every other tag (production release)

For the fork, you can use the same strategy or simplify
to just `stable` and `edge`.

## Cost

Snap Store submission is **free** for personal/community
publishers. The snap is hosted by Canonical at no cost.
The only requirement is that you don't violate the snap
store terms of service.

## When to set this up

Snap Store submission is most valuable when:

- The fork has a meaningful user base (e.g. >100 active
  users)
- The fork has a clear differentiator from upstream (e.g.
  the resilience patches are not in upstream)
- The maintainer wants to reach Linux users who don't
  want to use the .deb

For a personal/development fork, manual .deb
distribution is sufficient.

## See also

- `docs/CODE_SIGNING.md` (signing the .deb and .exe)
- `docs/DIAGNOSTICS.md` (privacy-respecting crash logs)
- `SUPPORT.md` (where users report issues with the snap)
- `CHANGELOG.md` (mentions snap store updates)
- https://snapcraft.io/docs (official Snapcraft docs)
