"""Coverage gate: enforce a minimum line coverage on new code.

The CI workflow runs pytest with --cov and feeds the
output to this script. The script compares the
coverage percentage against a threshold (default 70%)
and exits non-zero if the gate fails.

This is a wrapper around `coverage report` output. The
threshold is configurable via --threshold (default 70)
or via the env var PIRES_FORGE_MIN_COVERAGE.

Run with:

  pytest --cov=rayforge --cov-report=json -q tests/ \
    > /dev/null && python3 -m rayforge.util.coverage_gate

The script reads coverage.json (pytest-cov's default
output format). If the file is missing, it fails with
a clear error message.

Why a separate script and not a pytest plugin? The
gate is a policy decision (which file paths count
toward the threshold, what % is acceptable, what
fails vs warns). Keeping it as a stand-alone script
makes the policy easy to change without rebuilding
the test image.

Why 70%? It's the typical "good enough" line coverage
target for a mature desktop app. Higher (80-90%) is
better but requires significant test investment;
lower (50-60%) lets too many bugs through. 70% is
the balance. The threshold is adjustable per-repo
via PIRES_FORGE_MIN_COVERAGE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--coverage-file",
        type=Path,
        default=Path("coverage.json"),
        help="Path to the coverage.json file (default: coverage.json)",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "Minimum coverage %% (default: from "
            "PIRES_FORGE_MIN_COVERAGE env var, or 70)"
        ),
    )
    ap.add_argument(
        "--per-file",
        action="store_true",
        help="Show per-file coverage for files below threshold",
    )
    args = ap.parse_args()

    threshold = (
        args.threshold
        if args.threshold is not None
        else float(os.environ.get("PIRES_FORGE_MIN_COVERAGE", "70"))
    )

    if not args.coverage_file.exists():
        print(f"FAIL: {args.coverage_file} not found")
        print(
            "  Run pytest with --cov=rayforge --cov-report=json first."
        )
        return 1

    with open(args.coverage_file) as f:
        cov = json.load(f)

    total = cov["totals"]
    pct = total["percent_covered"]
    print(
        f"Total coverage: {pct:.2f}% "
        f"({total['covered_lines']}/{total['num_statements']} lines)"
    )
    print(f"Threshold: {threshold:.1f}%")

    if pct < threshold:
        print(
            f"\nFAIL: coverage {pct:.2f}% is below threshold "
            f"{threshold:.1f}%"
        )
        if args.per_file:
            print("\nFiles below threshold:")
            for path, data in sorted(cov["files"].items()):
                file_pct = data["summary"]["percent_covered"]
                if file_pct < threshold:
                    print(f"  {path}: {file_pct:.1f}%")
        return 1

    print(f"\nOK: coverage {pct:.2f}% >= threshold {threshold:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
