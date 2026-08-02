"""Constants for Pires Forge application."""

APP_NAME = "Pires Forge"
APP_NAME_SHORT = "pires-forge"
MIME_TYPE_PROJECT = "application/x-piresforge-project"
MIME_TYPE_SKETCH = "application/x-piresforge-sketch"

# This is a rebrand / fork of the upstream Rayforge project. The upstream
# repository is kept as the source of bug reports and release metadata
# (since Pires Forge is built from upstream and most user-facing bugs
# originate there), but the user-visible identity is "Pires Forge".
#
# Update checks point to the FORK (yuri-schmaltz/rayforge), not upstream
# (barebaric/rayforge), because Pires Forge is a separate distribution
# with its own release cadence. The version check is also off by default
# (see core/config.py) — users must opt in via Settings → Preferences.
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/yuri-schmaltz/rayforge/releases/latest"
)
GITHUB_URL = "https://github.com/yuri-schmaltz/rayforge"
ISSUES_URL = "https://github.com/yuri-schmaltz/rayforge/issues"
DOWNLOAD_URL = (
    "https://github.com/yuri-schmaltz/rayforge/releases"
)
