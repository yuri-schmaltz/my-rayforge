# Installation

This document describes all the ways to install the
`yuri-schmaltz/rayforge` fork on all supported platforms.

If you're a first-time user, the **recommended path** is
the .deb on Ubuntu (or the .exe on Windows, or the .dmg
on macOS). All three are pre-built for each release tag.

If you want to use a different package manager (Flatpak,
AUR, Nix, etc.) or build from source, see the relevant
section below.

## TL;DR

| Platform | Format | Source | Auto-update? |
|----------|--------|--------|--------------|
| Ubuntu 24.04+ | `.deb` | [Releases page](https://github.com/yuri-schmaltz/rayforge/releases) | No (manual) |
| Windows 10/11 | `.exe` | [Releases page](https://github.com/yuri-schmaltz/rayforge/releases) | No (manual) |
| macOS 12+ | `.dmg` | [Releases page](https://github.com/yuri-schmaltz/rayforge/releases) | No (manual) |
| Linux (snap) | `.snap` | Manual upload to snap store (see [SNAP_STORE.md](SNAP_STORE.md)) | Yes (via snapd) |
| Linux (Flatpak) | None (build from source) | See [Flatpak](#flatpak) below | No |
| Arch Linux | None (build from source) | See [AUR](#aur) below | No |
| NixOS | None (build from source) | See [Nix](#nixos) below | No |
| From source | pixi | See [Build from source](#build-from-source) | n/a |

## Ubuntu / Debian (.deb)

Download the latest `.deb` from the
[Releases page](https://github.com/yuri-schmaltz/rayforge/releases):

```bash
# For Ubuntu 24.04 (noble)
wget https://github.com/yuri-schmaltz/rayforge/releases/download/1.9.0+resilience.5/Rayforge-1.9.0+resilience.5-Linux.deb
sudo dpkg -i Rayforge-1.9.0+resilience.5-Linux.deb
sudo apt-get install -f  # Install any missing dependencies
```

Or with `apt` directly (once the fork is added to a PPA,
which is not yet done — see the [Roadmap](#roadmap) below):

```bash
# Not yet available; this is the future PPA setup:
# sudo add-apt-repository ppa:yuri-schmaltz/rayforge
# sudo apt update
# sudo apt install rayforge
```

The .deb is the **primary distribution channel** for the
fork. The build workflow `.github/workflows/build-deb.yml`
runs on every release tag.

## Windows (.exe)

Download the latest `.exe` from the
[Releases page](https://github.com/yuri-schmaltz/rayforge/releases):

1. Go to https://github.com/yuri-schmaltz/rayforge/releases/latest
2. Download `Rayforge-<version>-Windows.exe`
3. Double-click the .exe to run the installer
4. If you see a SmartScreen warning, click "More info" →
   "Run anyway". The fork is not code-signed (the
   maintainer doesn't have a Windows code-signing
   certificate); see [CODE_SIGNING.md](CODE_SIGNING.md) for
   the setup guide.

## macOS (.dmg)

Download the latest `.dmg` from the
[Releases page](https://github.com/yuri-schmaltz/rayforge/releases):

1. Go to https://github.com/yuri-schmaltz/rayforge/releases/latest
2. Download `Rayforge-<version>-macOS.dmg`
3. Open the .dmg (double-click)
4. Drag Rayforge.app to /Applications
5. If you see a Gatekeeper warning, right-click the app
   and choose "Open" → "Open" in the dialog. The fork is
   not signed or notarized (the maintainer doesn't have
   an Apple Developer account); see
   [CODE_SIGNING.md](CODE_SIGNING.md) for the setup guide.

## Snap

The fork does not currently publish to the Snap Store
because the `rayforge` name is owned by upstream
`yuri-schmaltz/pires-forge`. To publish the fork as a snap:

1. Reserve a different snap name (e.g. `rayforge-fork`)
2. Build the .snap using `.github/workflows/verify-snap.yml`
3. Upload manually to https://snapcraft.io/rayforge-fork

See [SNAP_STORE.md](SNAP_STORE.md) for the full guide.

## Flatpak

The fork does not currently publish a Flatpak. To build
your own from source:

### 1. Install flatpak-builder

```bash
# Ubuntu / Debian
sudo apt install flatpak flatpak-builder

# Fedora
sudo dnf install flatpak flatpak-builder

# Arch
sudo pacman -S flatpak flatpak-builder
```

### 2. Use the manifest template

A flatpak manifest template is provided at
`flatpak/org.rayforge.rayforge.yaml`. Edit it to point to
the latest release tarball:

```bash
# Download the manifest template
wget https://raw.githubusercontent.com/yuri-schmaltz/rayforge/main/flatpak/org.rayforge.rayforge.yaml

# Build
flatpak-builder --repo=rayforge-repo build-dir org.rayforge.rayforge.yaml

# Install
flatpak install --user rayforge-repo org.rayforge.rayforge

# Run
flatpak run org.rayforge.rayforge
```

### 3. Publish to Flathub (optional)

If you want to publish the fork to Flathub:

1. Fork https://github.com/flathub/flathub
2. Add a new app at `org.rayforge.rayforge-fork/` (or
   similar)
3. Use the manifest from step 2
4. Open a PR to flathub/flathub
5. Flathub reviewers will check the build, and if approved,
   the fork becomes available via `flatpak install flathub
   org.rayforge.rayforge-fork`

See https://docs.flathub.org/docs/for-app-authors/ for the
full Flathub submission guide.

## AUR (Arch User Repository)

The fork does not currently publish to the AUR. To package
the fork for Arch:

### 1. Get an AUR account

Create an account at https://aur.archlinux.org and set up
SSH keys per https://wiki.archlinux.org/title/AUR_submission_guidelines.

### 2. Create a PKGBUILD

A template PKGBUILD is provided at `aur/rayforge-fork/PKGBUILD`.
The package name must be unique on the AUR; `rayforge` is
already taken by upstream, so use `rayforge-fork` (or
similar).

```bash
# Clone the AUR repo
git clone ssh://aur@aur.archlinux.org/rayforge-fork.git
cd rayforge-fork

# Copy the template
wget https://raw.githubusercontent.com/yuri-schmaltz/rayforge/main/aur/rayforge-fork/PKGBUILD
wget https://raw.githubusercontent.com/yuri-schmaltz/rayforge/main/aur/rayforge-fork/rayforge-fork.install

# Update the .SRCINFO
makepkg --printsrcinfo > .SRCINFO

# Test the build
makepkg -si

# Submit
git add PKGBUILD rayforge-fork.install .SRCINFO
git commit -m "Initial upload: rayforge-fork 1.9.0+resilience.5"
git push
```

### 3. Update on new releases

When a new release is tagged:

```bash
# Update the PKGBUILD version
sed -i 's/^pkgver=.*/pkgver=1.9.0+resilience.6/' PKGBUILD
# Update the checksums
updpkgsums
# Rebuild .SRCINFO
makepkg --printsrcinfo > .SRCINFO
# Commit
git commit -am "upgpkg: rayforge-fork 1.9.0+resilience.6"
git push
```

## NixOS

The fork does not currently have a Nix package. To use it
on NixOS, build from source (see below) or write a
Nix derivation. A template derivation is provided at
`nix/default.nix`.

## Build from source

Requires `pixi` (https://pixi.sh):

```bash
git clone https://github.com/yuri-schmaltz/rayforge
cd rayforge
pixi install
pixi run -e dev rayforge
```

For a release-mode build (without the dev environment):

```bash
pixi run -e build compile-translations
pixi run -e build build-pkg
# The .deb is at dist/rayforge_*.deb
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full
development setup.

## Roadmap

The fork is working towards a more comprehensive
distribution:

- [x] `.deb` for Ubuntu 24.04
- [x] `.exe` for Windows
- [x] `.dmg` for macOS
- [x] `.snap` build (manual upload to snap store)
- [ ] Flatpak (template manifest only; no build)
- [ ] AUR (template PKGBUILD only; no submission)
- [ ] Nix (template derivation only; no submission)
- [ ] Auto-update via the GitHub releases API (currently
      manual download)

## See also

- [CODE_SIGNING.md](CODE_SIGNING.md) — for the maintainer
  to acquire certs and sign the binaries
- [SNAP_STORE.md](SNAP_STORE.md) — for publishing the
  fork to the Snap Store
- [DIAGNOSTICS.md](DIAGNOSTICS.md) — for getting a debug
  bundle to file an issue
- [SUPPORT.md](../SUPPORT.md) — for filing issues when
  installation doesn't work
- [CHANGELOG.md](../CHANGELOG.md) — for the latest release
  notes
"
