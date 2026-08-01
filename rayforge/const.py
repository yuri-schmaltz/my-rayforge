"""Constants for Pires Forge application."""

APP_NAME = "Pires Forge"
APP_NAME_SHORT = "pires-forge"
MIME_TYPE_PROJECT = "application/x-piresforge-project"
MIME_TYPE_SKETCH = "application/x-piresforge-sketch"

# This is a rebrand / fork of the upstream Rayforge project. The upstream
# repository is kept as the source of bug reports and release metadata
# (since Pires Forge is built from upstream and most user-facing bugs
# originate there), but the user-visible identity is "Pires Forge".
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/barebaric/rayforge/releases/latest"
)
GITHUB_URL = "https://github.com/barebaric/rayforge"
ISSUES_URL = "https://github.com/barebaric/rayforge/issues"
DOWNLOAD_URL = "https://rayforge.org/docs/getting-started/installation"
