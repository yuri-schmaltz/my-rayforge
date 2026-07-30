# Code Signing Setup Guide

This document explains how to set up code signing for the
`yuri-schmaltz/rayforge` fork. The fork does **not** sign its
binaries by default (the maintainer doesn't have the signing
certificates), which means:

- **Windows**: users see a SmartScreen warning on first launch.
  They must click "More info" → "Run anyway" to proceed.
- **macOS**: users see a Gatekeeper warning on first launch. They
  must right-click the app and choose "Open" to proceed.
- **Debian/Ubuntu**: if a self-hosted apt repository is used, `apt`
  will warn about an untrusted package.

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
- **Debian/Ubuntu**: apt trusts the package and installs it
  without warnings.

For a production release that you want users to install with
confidence, code signing is a hard requirement. It's not a
"nice to have".

## Cost

Code signing certificates cost money (or in some cases, time):

| Platform | Certificate | Cost | Validity |
|----------|-------------|------|----------|
| Windows | Code-signing cert from a trusted CA (DigiCert, Sectigo, GlobalSign, etc.) | $200-500/year | 1-3 years |
| macOS | Apple Developer Program (includes "Developer ID Application" cert) | $99/year | 1 year |
| Debian | Self-generated GPG key (free) | Free | Until expiry / no expiry |

The Windows and macOS certs need to be renewed annually. The
Debian GPG key is free and can have no expiry date.

## Windows setup

### 1. Purchase a code-signing certificate

Buy from a CA that the Windows SmartScreen trust list includes.
As of 2026, the most reliable options are:

- **DigiCert**: ~$500/year, 3-year max, hardware token required
- **Sectigo (Comodo)**: ~$250/year, 1-year, software cert
- **GlobalSign**: ~$250/year, 1-year, software cert

Avoid self-signed certs — they don't help with SmartScreen
reputation.

### 2. Export the .pfx file

After the CA issues the cert, export it as a .pfx file with a
strong password. The .pfx file contains both the public cert
and the private key.

```bash
# In Windows Certificate Manager (certmgr.msc):
#  Personal → Certificates → [your cert] → All Tasks → Export
#  → "Yes, export the private key"
#  → Personal Information Exchange - PKCS #12 (.PFX)
#  → Check "Include all certificates in the certification path"
#  → Set a strong password (20+ random characters)
#  → Save to file
```

### 3. Base64-encode the .pfx

```bash
base64 -w 0 cert.pfx > cert.pfx.b64
# On macOS: base64 -i cert.pfx -o cert.pfx.b64
# On Windows: certutil -encode cert.pfx cert.pfx.b64
```

### 4. Add the secrets to GitHub

1. Go to https://github.com/yuri-schmaltz/rayforge/settings/secrets/actions
2. Click "New repository secret"
3. Add two secrets:
   - `WINDOWS_CERT_PFX_BASE64`: paste the contents of `cert.pfx.b64`
   - `WINDOWS_CERT_PASSWORD`: the password you set in step 2

### 5. Verify the next release is signed

The next time the `build-exe.yml` workflow runs (on a release tag),
the `sign.yml` workflow will:
1. Download the unsigned .exe artifact
2. Import the .pfx certificate
3. Sign the .exe with `signtool /fd SHA256`
4. Upload the signed .exe as a new artifact
5. The maintainer downloads the signed .exe and attaches it to
   the GitHub release (replacing the unsigned one)

## macOS setup

### 1. Enroll in the Apple Developer Program

1. Go to https://developer.apple.com/programs/enroll/
2. Pay the $99/year fee (or renew annually)
3. Wait for approval (usually 1-2 business days)

### 2. Generate a Developer ID Application certificate

1. Open Keychain Access on a Mac that has Xcode installed
2. Keychain Access → Certificate Assistant → Request a
   Certificate from a Certificate Authority
3. Fill in your email and common name, select "Saved to disk"
4. Go to https://developer.apple.com/account/resources/certificates/list
5. Click "+" to create a new certificate, select "Developer ID
   Application", upload the CSR from step 3
6. Download the resulting certificate and double-click to
   install it in your keychain
7. Find the cert in Keychain Access, right-click → Export
   "Developer ID Application: Your Name" → save as .p12 with a
   strong password

### 3. Set up an App Store Connect API key for notarization

Apple notarization requires an API key:

1. Go to https://appstoreconnect.apple.com/access/api
2. Click "+" to generate a new key
3. Name: "Rayforge Notarization"
4. Access: "Developer"
5. Download the .p8 file (you can only download it once)
6. Note the Key ID and Issuer ID

### 4. Add the secrets to GitHub

1. Go to https://github.com/yuri-schmaltz/rayforge/settings/secrets/actions
2. Add the following secrets:
   - `MACOS_CERT_P12_BASE64`: `base64 -i cert.p12`
   - `MACOS_CERT_PASSWORD`: the .p12 password
   - `MACOS_NOTARY_KEY_ID`: from step 3
   - `MACOS_NOTARY_ISSUER_ID`: from step 3
   - `MACOS_NOTARY_KEY_P8_BASE64`: `base64 -i AuthKey_XXXXXX.p8`

### 5. Verify the next release is signed and notarized

The next time the `build-macos-universal.yml` workflow runs (on
a release tag), the `sign.yml` workflow will:
1. Download the unsigned .dmg artifact
2. Import the .p12 into a temporary keychain
3. Sign the .app and .dmg with `codesign --deep --options runtime`
4. Submit the .dmg to Apple's notary service
5. Staple the notarization ticket to the .dmg
6. Upload the signed+notarized .dmg as a new artifact
7. The maintainer downloads the signed .dmg and attaches it to
   the GitHub release (replacing the unsigned one)

## Debian/Ubuntu setup

The fork's `.deb` package is built by the
`build-deb.yml` workflow and uploaded as a workflow artifact
(not pushed to a PPA, since the upstream `publish-deb.yml` is
gated to the `barebaric/rayforge` repository).

If you want to set up a self-hosted apt repository (e.g. via
aptly + nginx) and have the packages signed, follow these steps:

### 1. Generate a GPG key

```bash
gpg --batch --gen-key <<EOF
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: Rayforge APT Repository
Name-Email: security@yuri-schmaltz.dev
Expire-Date: 0
%commit
EOF
```

The 4096-bit key with no expiry is recommended for an apt repo
signing key. **Back up the private key** (you'll need it for
the GitHub secret) and store a printed copy in a safe (if the
key is lost, all existing installations will fail to update).

### 2. Export the private key

```bash
gpg --armor --export-secret-keys security@yuri-schmaltz.dev > deb-gpg.asc
base64 -w 0 deb-gpg.asc > deb-gpg.asc.b64
```

### 3. Add the secrets to GitHub

1. Go to https://github.com/yuri-schmaltz/rayforge/settings/secrets/actions
2. Add:
   - `DEB_GPG_PRIVATE_KEY_BASE64`: contents of `deb-gpg.asc.b64`
   - `DEB_GPG_PASSPHRASE`: empty (because we used `%no-protection`)

If you DID set a passphrase, also add `DEB_GPG_PASSPHRASE` with
the passphrase.

### 4. Verify the next release is signed

The next time the `build-deb.yml` workflow runs (on a release
tag), the `sign.yml` workflow will:
1. Download the unsigned .deb artifact
2. Import the GPG key
3. Sign the .deb with `debsigs`
4. Upload the signed .deb as a new artifact
5. The maintainer uploads it to the self-hosted apt repo

## Cost summary

For all three platforms signed:
- Year 1: ~$450 (DigiCert $500 + Apple $99 - $150 bundle discount sometimes available)
- Year 2+: $350+ (renewals)

For Windows + macOS only (skip Debian):
- Year 1: $600+
- Year 2+: $500+

For just Debian (free):
- Year 1: $0
- Year 2+: $0

## When to set this up

Code signing is most valuable just before a public release. If
you're still in development, the unsigned binaries are fine for
internal testing. Set up code signing when you're ready to:

1. Post on social media / Reddit / Hacker News
2. Email your existing user base about the release
3. Publish on Flathub / Snap Store / AUR
4. List on product directories like AlternativeTo

Before any of those, you want users to install the app without
warnings.

## What if I don't want to pay for certs?

For personal/development use, the unsigned binaries are fine. The
warnings are annoying but not blocking. The fork's CI will still
build and publish the unsigned binaries — you just need to mention
in the release notes that users should expect the warnings.

For a self-published fork that's not for profit, this is a
reasonable trade-off. The maintainer of this fork made that
trade-off for `1.9.0+resilience.4` and below; future releases
may add signing if the certs are acquired.

## See also

- `SUPPORT.md`: end-user troubleshooting (includes the warnings
  and how to bypass them)
- `SECURITY.md`: the security policy
- `CHANGELOG.md`: release notes (mention signing status)
