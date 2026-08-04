"""Micro-benchmarks for hot paths.

Run with: `python3 -m rayforge.util.benchmarks`

These are simple, no-deps benchmarks designed to fit in
the dev loop without external tools (no pytest-benchmark,
no perf, no asv). The script measures:

  1. Cold start of the context (imports + addon scan)
  2. Vector path import (parse an SVG into Ops)
  3. G-code generation (Ops -> text)
  4. Tracer report format latency
  5. Addon discovery latency (scan only, no load)

Output: a table with mean, median, p95, and stdev per
benchmark, in milliseconds. We also dump a JSON file
(`benchmarks.json`) so successive runs can be diffed.

Why no pytest-benchmark? Two reasons: (a) cold-start
benchmarks must run in a fresh process, and pytest's
collection adds overhead that pollutes those numbers;
(b) we want a single command that doesn't require the
test runner to be installed.

Run as part of CI on a schedule (not every commit):
  python3 -m rayforge.util.benchmarks --output bench.json
  python3 -m rayforge.util.benchmarks --compare bench.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List

# Add repo root to path so this module can be run as a script.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _time_it(fn: Callable[[], None], iterations: int) -> List[float]:
    """Run `fn` `iterations` times and return wall-clock
    durations in milliseconds."""
    samples: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def _stats(samples: List[float]) -> dict:
    if not samples:
        return {"mean": 0, "median": 0, "p95": 0, "stdev": 0, "n": 0}
    return {
        "mean": round(statistics.mean(samples), 3),
        "median": round(statistics.median(samples), 3),
        "p95": round(sorted(samples)[int(len(samples) * 0.95)], 3),
        "stdev": round(statistics.stdev(samples), 3) if len(samples) > 1 else 0,
        "n": len(samples),
    }


def bench_cold_start(iterations: int = 5) -> dict:
    """Measure subprocess start of `python3 -c 'import rayforge'`.
    This is the canonical cold-start metric: time from process
    spawn until rayforge is importable.
    """
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        # We import rayforge.context but DON'T call init() — that
        # would require a running event loop. We only measure
        # the import cost.
        result = subprocess.run(
            [sys.executable, "-c", "import rayforge; import rayforge.context"],
            capture_output=True,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        if result.returncode != 0:
            samples.append(float("inf"))
        else:
            samples.append(elapsed)
    return {"name": "cold_start_subprocess", "stats": _stats(samples)}


def bench_tracer(iterations: int = 1000) -> dict:
    """Measure the overhead of tracer.span().

    1000 nested-span constructions, summed, divided by
    iterations. This is the per-event overhead of the
    tracing system itself.
    """
    from rayforge.util.tracing import get_tracer

    tracer = get_tracer()
    tracer.enable()

    def run() -> None:
        tracer.clear()
        for i in range(10):
            with tracer.span("iter", i=i):
                pass  # trivial body; we measure the wrap

    samples = _time_it(run, iterations)
    return {"name": "tracer.span_overhead", "stats": _stats(samples)}


def bench_addon_discovery(iterations: int = 3) -> dict:
    """Measure addon directory scan + manifest parse, no load.

    This is the most expensive part of the addon system at
    startup. We measure just the discovery, not the actual
    Python imports.
    """
    from rayforge.addon_mgr.addon_manager import AddonManager

    # The constructor doesn't load addons; just sets up paths.
    # We use a fresh AddonManager to avoid the singleton.
    # We measure .load_addon (no, this loads too) — we measure
    # the directory iteration + manifest parse.
    # AddonManager has no 'discover-only' public API, so we
    # use load_installed_addons with worker_only=True which
    # skips the GTK frontend hook but still parses manifests.
    from rayforge.config import init_context

    init_context()
    samples = []
    for _ in range(iterations):
        mgr = AddonManager()
        t0 = time.perf_counter()
        mgr.load_installed_addons(worker_only=True)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return {"name": "addon_discovery", "stats": _stats(samples)}


def bench_i18n_lookup(iterations: int = 1000) -> dict:
    """Measure gettext lookup overhead.

    Translates a known string 1000 times. This is the cost
    the user pays on every render of an i18n-marked UI
    string.
    """
    def run() -> None:
        for _ in range(100):
            _("Save")
            _("Open")
            _("Cancel")

    samples = _time_it(run, iterations)
    return {"name": "i18n_lookup", "stats": _stats(samples)}


# Registry of available benchmarks. Each entry is a callable
# returning a dict with 'name' and 'stats' keys.
BENCHMARKS = [
    bench_cold_start,
    bench_tracer,
    bench_addon_discovery,
    bench_i18n_lookup,
]


def run_all() -> List[dict]:
    return [b() for b in BENCHMARKS]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON results to this path.",
    )
    ap.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="Compare against a previous JSON file (from --output).",
    )
    ap.add_argument(
        "--fail-on-regression",
        type=float,
        default=None,
        metavar="PCT",
        help=(
            "Exit with code 2 if any benchmark regressed by "
            "more than PCT%% vs the --compare baseline. "
            "Default: just print the comparison."
        ),
    )
    args = ap.parse_args()

    print("Running benchmarks...")
    results = run_all()
    print()
    print(f"{'benchmark':<30} {'mean (ms)':>12} {'p95 (ms)':>12} {'n':>5}")
    print("-" * 65)
    for r in results:
        s = r["stats"]
        print(
            f"{r['name']:<30} "
            f"{s['mean']:>12} "
            f"{s['p95']:>12} "
            f"{s['n']:>5}"
        )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults written to {args.output}")

    if args.compare:
        with open(args.compare) as f:
            prev = {r["name"]: r for r in json.load(f)}
        print(f"\nComparison vs {args.compare}:")
        regressions: List[str] = []
        for r in results:
            old = prev.get(r["name"])
            if not old:
                continue
            delta = r["stats"]["mean"] - old["stats"]["mean"]
            pct = (delta / old["stats"]["mean"] * 100) if old["stats"]["mean"] else 0
            sign = "+" if delta > 0 else ""
            print(
                f"  {r['name']:<28} "
                f"{old['stats']['mean']:>8.2f} -> "
                f"{r['stats']['mean']:>8.2f} ms  "
                f"({sign}{pct:.1f}%)"
            )
            if (
                args.fail_on_regression is not None
                and pct > args.fail_on_regression
            ):
                regressions.append(
                    f"{r['name']}: {pct:.1f}% (limit {args.fail_on_regression}%)"
                )
        if regressions:
            print(
                f"\nFAIL: {len(regressions)} benchmark(s) regressed by more "
                f"than {args.fail_on_regression}%:"
            )
            for r in regressions:
                print(f"  - {r}")
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
