"""i18n POT extraction + .po update script.

Wraps xgettext / msgmerge so the extraction step is
reproducible across machines and CI. The script:

  1. Runs xgettext on the rayforge/ tree to produce
     rayforge/locale/rayforge.pot (a fresh template)
  2. Runs msgmerge for each .po file in
     rayforge/locale/<lang>/LC_MESSAGES/, updating it
     with any new strings from the .pot (existing
     translations are preserved)

Run with:

  python3 -m rayforge.util.i18n_extract

  # Or with --check to fail if the .pot changed
  # (used in CI to detect 'someone added a new string
  # but didn't regenerate the .pot'):
  python3 -m rayforge.util.i18n_extract --check

The script is intentionally simple. It does NOT
translate anything (that's a human's job in POEdit
or similar); it only extracts and updates templates.

Why a Python wrapper around xgettext/msgmerge? The
two commands are powerful but have 15+ flags each,
most of which don't apply to a Python gettext
project. This wrapper hard-codes the flags that
matter (--keyword=_, --from-code=UTF-8, --add-comments,
etc.) so a contributor can run one command and get
the right output.

xgettext is a gettext standard tool, available in:
  - Debian/Ubuntu: apt install gettext
  - macOS: brew install gettext
  - Windows: MSYS2 gettext-devel
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list, check: bool = True) -> int:
    """Run a command, print it, return exit code."""
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check)
    return result.returncode


def extract_pot(repo_root: Path, output: Path) -> None:
    """Run xgettext on the rayforge/ tree to produce a .pot.

    The flags:
      --language=Python    : tokenize as Python (not C)
      --keyword=_          : extract _(s) calls
      --from-code=UTF-8    : source is UTF-8
      --add-comments=TRANSLATORS : keep TRANSLATORS: comments
      --package-name=Pires Forge
      --package-version=1.0.0
      --copyright-holder=Yuri Schmaltz
    """
    cmd = [
        "xgettext",
        "--language=Python",
        "--keyword=_",
        "--keyword=ngettext:1,2",
        "--from-code=UTF-8",
        "--add-comments=TRANSLATORS",
        "--package-name=Pires Forge",
        "--package-version=1.0.0",
        "--copyright-holder=Yuri Schmaltz",
        "--msgid-bugs-address=security@yuri-schmaltz.dev",
        "--output=" + str(output),
    ]
    # xgettext needs the input files. We pass all .py
    # files in rayforge/ (excluding tests/ and __pycache__/).
    sources = []
    for py in sorted((repo_root / "rayforge").rglob("*.py")):
        # Skip tests, __pycache__, and the extracted POT
        # directory itself.
        parts = py.parts
        if "tests" in parts or "__pycache__" in parts:
            continue
        sources.append(str(py))
    cmd.extend(sources)
    _run(cmd)


def merge_po(repo_root: Path, pot: Path) -> int:
    """Run msgmerge for each .po file under rayforge/locale/.

    Returns the number of .po files that changed (a
    changed .po means a new string was added and the
    existing translations are now stale — translators
    need to update the .po).
    """
    changed = 0
    locale_dir = repo_root / "rayforge" / "locale"
    if not locale_dir.exists():
        print(f"no locale dir at {locale_dir}")
        return 0
    for lang_dir in sorted(locale_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        po_files = list(lang_dir.glob("LC_MESSAGES/*.po"))
        for po in po_files:
            # msgmerge writes to a temp file then moves
            # the result in place, so an interrupted run
            # doesn't corrupt the .po.
            tmp = po.with_suffix(".po.new")
            cmd = [
                "msgmerge",
                "--update",
                "--backup=none",
                "--quiet",
                str(po),
                str(pot),
            ]
            _run(cmd)
            # msgmerge --update always rewrites; check if
            # the content actually changed.
            with open(po, "rb") as f:
                new_hash = hashlib.sha256(f.read()).hexdigest()
            with open(tmp, "rb") as f:
                old_hash = hashlib.sha256(f.read()).hexdigest() if tmp.exists() else None
            if new_hash != old_hash:
                changed += 1
                print(f"  updated {po.relative_to(repo_root)}")
            if tmp.exists():
                tmp.unlink()
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help=(
            "Exit non-zero if the .pot would change. "
            "Use in CI to detect 'new string was added "
            "but .pot not regenerated'."
        ),
    )
    ap.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip the msgmerge step (only update the .pot).",
    )
    args = ap.parse_args()

    repo_root = Path.cwd()
    pot = repo_root / "rayforge" / "locale" / "rayforge.pot"

    if not shutil.which("xgettext"):
        print("xgettext not found; install gettext")
        return 1
    if not shutil.which("msgmerge"):
        print("msgmerge not found; install gettext")
        return 1

    # Save current .pot hash (if --check) for diff
    if args.check and pot.exists():
        with open(pot, "rb") as f:
            before = hashlib.sha256(f.read()).hexdigest()
    else:
        before = None

    extract_pot(repo_root, pot)

    if args.check and before is not None:
        with open(pot, "rb") as f:
            after = hashlib.sha256(f.read()).hexdigest()
        if before != after:
            print(
                f"\nFAIL: rayforge.pot changed.\n"
                f"  before: {before[:12]}...\n"
                f"  after:  {after[:12]}...\n"
                f"Run \`python3 -m rayforge.util.i18n_extract\` "
                f"locally and commit the result."
            )
            return 2
        print("OK: rayforge.pot unchanged")
        return 0

    if args.no_merge:
        print(f"\nWrote {pot}")
        return 0

    changed = merge_po(repo_root, pot)
    print(f"\nWrote {pot}")
    print(f"Updated {changed} .po file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
