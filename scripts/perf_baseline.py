"""
Performance baseline for the rayforge package.

Measures:
  1. **Import time** — how long it takes to import the main
     sub-modules of rayforge (cold-cache, after a fresh Python
     process). This is the same metric the CI `Import Time Gate`
     job measures.
  2. **Per-module import time** — drill-down for each major
     sub-module, useful for spotting regressions in a specific
     area.
  3. **App startup time** — full `rayforge.shared.util.versioning
     .is_newer_version` calls and other pure-Python operations
     that the auto-update checker uses on every check.

Run with:
    pixi run python scripts/perf_baseline.py

The numbers are printed to stdout in a stable, machine-parseable
format that the CI can read in a follow-up PR. For now this
script is informational only — it does not fail the build.

Performance budgets (rayforge 1.9.0+resilience.4, 2026-07-30):

  - Cold import of `rayforge`           : < 30s (CI budget)
  - Per-submodule import                : < 5s each
  - `is_newer_version` (1000 iterations) : < 100ms

If a future PR exceeds a budget, the import-time gate in
`security-perf.yml` will catch it.
"""
import json
import subprocess
import sys
import time
from typing import Dict, List

# Budgets (seconds). Exceeding one is a regression.
BUDGETS = {
    "import_rayforge": 30.0,
    "import_svg": 5.0,
    "import_dxf": 5.0,
    "import_lightburn": 5.0,
    "import_grbl": 5.0,
    "is_newer_version_1000": 0.1,
}

# Sub-modules to measure individually.
SUBMODULES = [
    "rayforge.image.svg",
    "rayforge.image.dxf",
    "rayforge.image.lightburn",
    "rayforge.machine.driver.grbl",
    "rayforge.shared.util.http",
    "rayforge.shared.util.versioning",
]


def measure_subprocess_import(module: str) -> float:
    """Measure the import time of a module in a fresh Python process.

    Uses a subprocess to ensure no module-cache contamination.
    """
    script = (
        "import time, sys\n"
        f"t0 = time.monotonic()\n"
        f"import {module}\n"
        f"t1 = time.monotonic()\n"
        f"print(t1 - t0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to import {module} in subprocess:\n{result.stderr}"
        )
    return float(result.stdout.strip())


def measure_in_process_call(callable_name: str, iterations: int) -> float:
    """Measure the total time of N calls in the same process.

    Returns the total time in seconds.
    """
    if callable_name == "is_newer_version":
        from rayforge.shared.util.versioning import is_newer_version

        test_pairs = [
            ("1.9.0+resilience.4", "1.9.0"),
            ("1.9.0+resilience.4", "1.9.0+resilience.3"),
            ("1.9.1", "1.9.0+resilience.4"),
            ("2.0.0", "1.9.0+resilience.4"),
        ]
        t0 = time.monotonic()
        for _ in range(iterations):
            for r, l in test_pairs:
                is_newer_version(r, l)
        return time.monotonic() - t0
    raise ValueError(f"Unknown callable: {callable_name}")


def main() -> int:
    print("=== rayforge performance baseline ===\n")

    results: Dict[str, float] = {}
    regressions: List[str] = []

    # 1. Per-submodule import times
    print("--- per-submodule import time (cold cache) ---")
    for submod in SUBMODULES:
        try:
            t = measure_subprocess_import(submod)
        except Exception as e:
            print(f"  {submod}: ERROR ({e})")
            continue
        results[f"import_{submod.split('.')[-1]}"] = t
        budget = BUDGETS.get(f"import_{submod.split('.')[-1]}", 5.0)
        status = "OK" if t <= budget else "OVER BUDGET"
        if t > budget:
            regressions.append(
                f"  {submod}: {t:.2f}s > {budget:.1f}s"
            )
        print(f"  {submod:40} {t:6.2f}s  budget={budget:.1f}s  {status}")

    # 2. is_newer_version perf (in-process, so cached)
    print("\n--- in-process call timing ---")
    t = measure_in_process_call("is_newer_version", 1000)
    results["is_newer_version_1000"] = t
    budget = BUDGETS["is_newer_version_1000"]
    status = "OK" if t <= budget else "OVER BUDGET"
    if t > budget:
        regressions.append(
            f"  is_newer_version (1000 calls): {t:.3f}s > {budget:.2f}s"
        )
    print(f"  is_newer_version (1000 calls)         "
          f"{t:6.3f}s  budget={budget:.2f}s  {status}")

    # 3. Summary
    print("\n=== summary ===")
    print(json.dumps(results, indent=2))
    if regressions:
        print("\nREGRESSIONS:")
        for r in regressions:
            print(r)
        return 1
    print("\nAll within budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
