"""Static-analysis audit for missing gettext markers.

Scans the rayforge/ tree for user-facing string literals that
are NOT wrapped in gettext (the `_()` helper). Reports a
sorted list of file:line candidates so a developer can wrap
them in _() at their own pace.

The scanner is heuristic, not perfect: it uses AST to find
calls to user-facing methods (`set_text`, `append`,
`set_label`, etc.) and checks if the literal argument is
already wrapped in _(). A few false positives are accepted
(the developer can ignore them).

Run as: `python3 -m rayforge.util.i18n_audit`

Options:
  --path PATH    : root to scan (default: ./rayforge)
  --format text  : human-readable output (default)
  --format json  : machine-readable output for CI

CI usage:

  python3 -m rayforge.util.i18n_audit --format json \
      > /tmp/i18n-audit.json
  if [ -s /tmp/i18n-audit.json ]; then
      echo "::warning::i18n audit found candidates"
  fi

(Non-fatal in CI: warnings only, not errors. The audit is
advisory — wrapping 50 strings is a 1-2 day task per locale.)
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import List, Tuple

USER_FACING_METHODS = frozenset({
    "set_text",
    "set_label",
    "append",
    "set_placeholder_text",
    "set_tooltip_text",
    "set_title",
    "set_message",
    "set_subtitle",
    "set_markup",
    "set_primary_text",
    "set_secondary_text",
    "set_description",
    "set_text_column",
    "set_tooltip_markup",
})

# Strings we never want to flag: XML/SVG fragments, CSS
# class names, URLs, paths.
SKIP_PATTERNS = (
    "</",      # closing tag
    "<",       # opening tag (markup, not for translation)
    ".css",
    "/tmp/",
    "http://",
    "https://",
    "file://",
    "Pango",
)


def _is_already_wrapped(node: ast.Call) -> bool:
    """True if any of the call's arguments is a _(...) call."""
    for arg in node.args:
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
            if arg.func.id == "_":
                return True
        if isinstance(arg, ast.JoinedStr):
            for v in arg.values:
                if (
                    isinstance(v, ast.Call)
                    and isinstance(v.func, ast.Name)
                    and v.func.id == "_"
                ):
                    return True
    return False


def _literal_value(node: ast.AST) -> str | None:
    """Return the string value of a Constant node, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def audit_file(path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single Python file. Returns a list of
    (line, method, literal) tuples for unwrapped
    user-facing strings."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []
    results: List[Tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method_name = None
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            method_name = node.func.id
        if method_name not in USER_FACING_METHODS:
            continue
        if not node.args:
            continue
        if _is_already_wrapped(node):
            continue
        first = node.args[0]
        lit = _literal_value(first)
        if lit is None:
            continue
        if not lit.strip():
            continue
        if any(pat in lit for pat in SKIP_PATTERNS):
            continue
        # Skip pure-identifier short labels (CSS class, key)
        if (
            len(lit) <= 20
            and lit.replace("_", "").replace("-", "").isalnum()
            and not any(c in lit for c in " ,.!?")
        ):
            continue
        results.append((node.lineno, method_name, lit))
    return results


def audit_tree(root: Path) -> List[dict]:
    """Scan all .py files under `root`. Returns a list of
    dicts suitable for JSON serialization."""
    results: List[dict] = []
    for py in sorted(root.rglob("*.py")):
        if "/tests/" in str(py) or "/test_" in str(py):
            continue
        for line, method, lit in audit_file(py):
            results.append({
                "file": str(py),
                "line": line,
                "method": method,
                "text": lit[:120],
            })
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--path",
        type=Path,
        default=Path("rayforge"),
        help="Root to scan (default: ./rayforge)",
    )
    ap.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    args = ap.parse_args()
    results = audit_tree(args.path)
    if args.format == "json":
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No candidates found.")
            return 0
        by_file: dict = {}
        for r in results:
            by_file.setdefault(r["file"], []).append(r)
        total = sum(len(v) for v in by_file.values())
        print(f"Found {total} candidate string(s) across "
              f"{len(by_file)} file(s):\n")
        for f in sorted(by_file):
            print(f"  {f}")
            for r in by_file[f]:
                text = r["text"].replace("\n", " ")[:80]
                print(f"    L{r['line']:>4}  {r['method']:<24} {text}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
