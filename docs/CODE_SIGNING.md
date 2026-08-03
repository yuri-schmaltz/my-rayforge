# Code Signing Setup Guide

This document explains how to set up code signing for
[Pires Forge](https://github.com/yuri-schmaltz/pires-forge). The
fork does **not** sign its binaries by default (the maintainer
doesn't have the signing certificates), which means:

- **Windows**: users see a SmartScreen warning on first launch.
  They must click "More info" → "Run anyway" to proceed.
- **macOS**: users see a Gatekeeper warning on first launch. They
  must right-click the app and choose "Open" to proceed.
- **Debian/Ubuntu**: the `.deb` is not signed with a release key.
  apt will warn about an untrusted package; users can install with
  `sudo apt install --allow-unauthenticated`.

This guide walks through the setup of code signing on each
platform. The fork's CI workflow (`.github/workflows/sign.yml`)
is already in place — once you add the corresponding secrets to
the fork's GitHub Actions settings, the next release will be
signed automatically.

## Why code signing matters

Without code signing, end users see scary warnings when they
try to install the app. With code signing:

- **Windows**: SmartScreen trusts the certificate and the warning
  goes away (or is significantly reduced).
- **macOS**: Gatekeeper accepts the app without manual override.
  Apple notarization (a separate step from code signing) is
  required for macOS Catalina and later.
- **Debian/Ubuntu**: apt verifies the package against the maintainer's
  GPG key in `Release.gpg` and installs without warning.

## Windows (Authenticode)

### Requirements

- An **Authenticode** code signing certificate. Options:
  - **Self-signed** (free; Windows still warns on first launch,
    but the warning is reduced to "Unknown publisher" instead of
    "Windows protected your PC").
  - **CA-issued** (paid; ~$200/year from providers like
    Certum, SSL.com, or Sectigo).
  - **Azure Trusted Signing** (paid; Microsoft's cloud signing
    service).
- A **hardware token** (e.g. YubiKey, USB smartcard) for storing
    the certificate. Some CAs require this for EV certificates.
- [`signtool.exe`](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
  from the Windows SDK.

### Steps

1. **Obtain the certificate** from a CA. They will email you a
   `.pfx` file (or instructions to download it).
2. **Add the certificate** to the Windows certificate store
   (`certmgr.msc` → Personal → Certificates).
3. **Add the secrets** to the GitHub repository's Actions secrets:
   - `WINDOWS_CERTIFICATE_BASE64` — the `.pfx` file, base64-encoded.
   - `WINDOWS_CERTIFICATE_PASSWORD` — the certificate's password.
4. The CI workflow will sign the `.exe` automatically on the
   next release.

### Test locally

```bash
# Sign an .exe
signtool.exe sign /fd SHA256 /a /tr http://timestamp.digicert.com \
    /td SHA256 path/to/Rayforge.exe

# Verify
signtool.exe verify /pa path/to/Rayforge.exe
```

## macOS (Developer ID + Notarization)

### Requirements

- An **Apple Developer ID** ($99/year, individual or organization).
- A **Developer ID Installer** or **Developer ID Application**
  certificate (free once you have the Developer ID).
- An **app-specific password** for notarization.
- `codesign`, `notarytool`, `xcrun` (Xcode command line tools).

### Steps

1. **Join the Apple Developer Program** at
   <https://developer.apple.com/programs/>.
2. **Create a Developer ID Application certificate** in
   <https://developer.apple.com/account/resources/certificates>.
3. **Export the certificate** as a `.p12` file from Keychain Access.
4. **Add the secrets** to the GitHub repository's Actions secrets:
   - `MACOS_CERTIFICATE_P12_BASE64` — the `.p12`, base64-encoded.
   - `MACOS_CERTIFICATE_PASSWORD` — the certificate password.
   - `MACOS_NOTARIZATION_APPLE_ID` — your Apple ID.
   - `MACOS_NOTARIZATION_PASSWORD` — the app-specific password.
   - `MACOS_NOTARIZATION_TEAM_ID` — your Apple Developer team ID.
5. The CI workflow will sign and notarize the `.app` and `.dmg`
   automatically on the next release.

### Test locally

```bash
# Sign the .app
codesign --force --deep --options=runtime \
    --sign "Developer ID Application: Your Name (TEAMID)" \
    Rayforge.app

# Notarize
xcrun notarytool submit Rayforge.dmg \
    --apple-id your@email.com \
    --password <app-specific-password> \
    --team-id TEAMID \
    --wait

# Staple the notarization ticket
xcrun stapler staple Rayforge.dmg

# Verify
spctl --assess --type execute --verbose=2 Rayforge.app
```

## Debian / Ubuntu (GPG)

### Requirements

- A **GPG key** (free; you probably already have one).
- A **Launchpad account** (free; required for the PPA).

### Steps

1. **Generate or use an existing GPG key**:

   ```bash
   gpg --list-keys  # check if you have one
   gpg --full-generate-key  # create a new one
   ```

2. **Upload the key** to a keyserver:

   ```bash
   gpg --send-keys YOUR_KEY_ID
   ```

3. **Configure `debsign` and `dput`** on the CI runner. The
   `.github/workflows/sign.yml` workflow already calls `debsign`
   and `dput ppa:yuri-schmaltz/pires-forge` on the built
   `.changes` file.

4. **Add the secrets**:
   - `GPG_PRIVATE_KEY_BASE64` — the GPG private key, base64-encoded.
   - `GPG_PASSPHRASE` — the GPG key's passphrase.
   - `LAUNCHPAD_API_KEY` — the API token for `dput`.

5. The CI workflow will sign the `.dsc`, `.changes`, and
   `.deb` files automatically on the next release.

## What the fork does today

Pires Forge `1.0.0` is **unsigned**. This is documented in the
release notes. Users see the appropriate platform warnings
(SmartScreen, Gatekeeper, apt untrusted).

If you want to fund code signing for the fork, the maintainer
accepts donations at <security@yuri-schmaltz.dev>.
