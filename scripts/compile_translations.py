#!/usr/bin/env python3
"""
Compile all .po translation files to .mo files using the pure-Python
rayforge.shared.util.po_compiler module.

This is used by the CI build workflows (build-deb, build-exe, build-macos)
to ensure that gettext at runtime can find translated strings.

Why a separate script and not inline:
  - YAML in GitHub Actions breaks on `:` characters inside `run: |` blocks
    (YAML interprets them as map keys), so embedding Python in workflows
    is fragile.
  - The script is reusable across all 3 build workflows and the local
    build-deb.sh, ensuring consistent behavior.

Why pure-Python and not gettext/msgfmt:
  - Ubuntu 24.04 ships gettext 0.21, but update_translations.sh requires
    0.25+. The pure-Python compiler works on any platform with Python 3.
  - The compiled .mo files are byte-compatible with msgfmt output for the
    subset of PO features we use (no plural forms, no msgctxt, no obsolete
    entries).
  - rayforge.addon_mgr.addon_manager already uses this module for runtime
    addon translation compilation, so it's battle-tested.
"""

import sys
from pathlib import Path

# Allow running before the package is installed (e.g. during a
# pre-build step in CI). The repo root is always the parent of scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rayforge.shared.util.po_compiler import compile_po_to_mo  # noqa: E402


def main() -> int:
    root = Path(".")
    if not root.exists():
        print("ERROR: current directory does not exist", file=sys.stderr)
        return 1

    compiled = 0
    skipped = 0
    for po in sorted(root.rglob("*.po")):
        # Skip generated/dependency directories that might contain .po files
        if any(
            part in po.parts
            for part in ("build", ".git", ".pixi", "dist", "node_modules")
        ):
            continue
        mo = po.with_suffix(".mo")
        if compile_po_to_mo(po, mo):
            compiled += 1
        else:
            skipped += 1

    print(f"Compiled {compiled} .mo files (skipped {skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
