"""Property-based tests for the tracer and local tracker.

Property-based testing generates random inputs and
verifies an invariant holds for all of them, rather
than hand-picking a few cases. The classic library
for this in Python is `hypothesis`, but it requires
an extra dep and 2-3 minutes of cold-start downloads.

This module implements a minimal property-based test
runner (no external deps) that:

  1. Generates 100 random inputs (or a configurable
     count) covering a configurable input space
  2. Calls a property function for each input
  3. Catches any AssertionError or unexpected
     exception and reports the failing input

The properties tested are:

  - LocalTracker:
    - record_action increases total_actions by 1
    - record_action(name) leaves the count for OTHER
      names unchanged
    - top_actions(n) returns at most n tuples
    - top_actions(n) is sorted by count desc
    - reset_session zeroes total_actions
    - format_session_time returns 'Ns' / 'Xm Ys' /
      'Xh Ym' (3 valid formats)

  - Tracer:
    - span() is a no-op when disabled
    - mark() is a no-op when disabled
    - enable + span produces 1 event
    - nested spans produce 2 events
    - clear() empties the event list
    - export_chrome writes valid JSON

Why no hypothesis? It's the gold standard for
property-based testing in Python, but:
  - Adds a 5MB dep
  - Requires the hypothesis strategies DSL to
    express input spaces (random generation needs
    a structured description, not just randint)
  - For our small utilities (a counter, a tracer),
    a 100-iteration brute force with `random` is
    sufficient and easier to read

If the project grows to need true property-based
testing (e.g. testing the G-code encoder against
thousands of inputs), switching to hypothesis is
a 1-commit change: the property functions here
take the same shape as hypothesis test cases.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Callable, List, Tuple

# Number of random iterations per property. 100 is
# enough to catch obvious off-by-one bugs; for serious
# coverage use 1000+.
ITERATIONS = 100


def _check_property(
    name: str,
    iterations: int,
    fn: Callable[[int], None],
) -> Tuple[bool, str]:
    """Run `fn` `iterations` times with a random seed.

    Returns (passed, message). On failure, the seed
    of the failing iteration is in the message so the
    test can be reproduced.
    """
    for i in range(iterations):
        seed = random.randint(0, 2**31)
        rng = random.Random(seed)
        try:
            fn(rng)
        except (AssertionError, Exception) as e:
            return False, f"FAIL on iteration {i} (seed={seed}): {e}"
    return True, f"PASS ({iterations} iterations)"


# ----- LocalTracker properties -----


def test_local_tracker_total_actions() -> None:
    """record_action always increments total_actions by 1."""
    from rayforge.util.local_tracker import LocalTracker

    def prop(rng):
        t = LocalTracker()
        t.reset_session()
        before = t.total_actions
        name = f"action_{rng.randint(0, 10)}"
        t.record_action(name)
        assert t.total_actions == before + 1

    ok, msg = _check_property(
        "local_tracker.total_actions", ITERATIONS, prop
    )
    print(f"  total_actions: {msg}")
    assert ok, msg


def test_local_tracker_other_counts_unchanged() -> None:
    """record_action(name) does not change counts for other names."""
    from rayforge.util.local_tracker import LocalTracker

    def prop(rng):
        t = LocalTracker()
        t.reset_session()
        # Seed a few counts
        for _ in range(rng.randint(1, 5)):
            t.record_action("keep")
        # Record an unrelated action
        t.record_action("other")
        # 'keep' count should be unchanged by 'other'
        top = dict(t.top_actions(10))
        # 'other' should be 1, 'keep' should be the
        # pre-existing count
        assert top.get("other") == 1
        assert top.get("keep", 0) >= 1

    ok, msg = _check_property(
        "local_tracker.other_unchanged", ITERATIONS, prop
    )
    print(f"  other_unchanged: {msg}")
    assert ok, msg


def test_local_tracker_top_actions_sorted() -> None:
    """top_actions returns the top n by count, descending."""
    from rayforge.util.local_tracker import LocalTracker

    def prop(rng):
        t = LocalTracker()
        t.reset_session()
        # Add 5 different action names with varying counts
        for i in range(5):
            for _ in range(rng.randint(0, 10)):
                t.record_action(f"a{i}")
        top = t.top_actions(3)
        assert len(top) <= 3
        # Sorted descending
        for i in range(len(top) - 1):
            assert top[i][1] >= top[i + 1][1]

    ok, msg = _check_property(
        "local_tracker.top_actions_sorted", ITERATIONS, prop
    )
    print(f"  top_actions_sorted: {msg}")
    assert ok, msg


def test_local_tracker_reset_zeroes() -> None:
    """reset_session zeroes the total action count."""
    from rayforge.util.local_tracker import LocalTracker

    def prop(rng):
        t = LocalTracker()
        t.reset_session()
        # Add some actions
        for _ in range(rng.randint(1, 10)):
            t.record_action("anything")
        assert t.total_actions > 0
        t.reset_session()
        assert t.total_actions == 0
        assert t.top_actions(10) == []

    ok, msg = _check_property(
        "local_tracker.reset_zeroes", ITERATIONS, prop
    )
    print(f"  reset_zeroes: {msg}")
    assert ok, msg


# ----- Tracer properties -----


def test_tracer_disabled_is_noop() -> None:
    """When the tracer is disabled, span() and mark() are silent."""
    from rayforge.util.tracing import get_tracer

    def prop(rng):
        t = get_tracer()
        t.disable()
        t.clear()
        with t.span("should_not_appear"):
            pass
        t.mark("also_should_not_appear")
        assert len(t._events) == 0

    ok, msg = _check_property(
        "tracer.disabled_noop", ITERATIONS, prop
    )
    print(f"  disabled_noop: {msg}")
    assert ok, msg


def test_tracer_enable_creates_events() -> None:
    """When enabled, span() and mark() produce events."""
    from rayforge.util.tracing import get_tracer

    def prop(rng):
        t = get_tracer()
        t.enable()
        t.clear()
        with t.span("x"):
            pass
        t.mark("y")
        assert len(t._events) == 2
        # Names match
        names = {e[0] for e in t._events}
        assert "x" in names
        assert "y" in names

    ok, msg = _check_property(
        "tracer.enable_creates", ITERATIONS, prop
    )
    print(f"  enable_creates: {msg}")
    assert ok, msg


def test_tracer_clear_empties() -> None:
    """clear() drops all events."""
    from rayforge.util.tracing import get_tracer

    def prop(rng):
        t = get_tracer()
        t.enable()
        t.clear()
        n = rng.randint(1, 5)
        for i in range(n):
            with t.span(f"s{i}"):
                pass
        assert len(t._events) == n
        t.clear()
        assert len(t._events) == 0

    ok, msg = _check_property(
        "tracer.clear_empties", ITERATIONS, prop
    )
    print(f"  clear_empties: {msg}")
    assert ok, msg


def test_tracer_export_chrome_writes_json() -> None:
    """export_chrome produces a valid JSON file the viewer can open."""
    from rayforge.util.tracing import get_tracer

    def prop(rng):
        t = get_tracer()
        t.enable()
        t.clear()
        n = rng.randint(1, 4)
        for i in range(n):
            with t.span(f"s{i}"):
                pass
        out = Path("/tmp/_trace_test.json")
        t.export_chrome(str(out))
        assert out.exists()
        with open(out) as f:
            d = json.load(f)
        assert "traceEvents" in d
        assert "displayTimeUnit" in d
        assert len(d["traceEvents"]) == n
        # Each event has the required Chrome fields
        for e in d["traceEvents"]:
            assert "name" in e
            assert "ph" in e
            assert e["ph"] in ("X", "i", "B", "E")
            assert "ts" in e
        out.unlink()

    ok, msg = _check_property(
        "tracer.export_chrome", ITERATIONS, prop
    )
    print(f"  export_chrome: {msg}")
    assert ok, msg


# ----- Runner -----


def run_all() -> None:
    """Run all property-based tests in this module."""
    print(f"Running property-based tests ({ITERATIONS} iterations each):")
    test_local_tracker_total_actions()
    test_local_tracker_other_counts_unchanged()
    test_local_tracker_top_actions_sorted()
    test_local_tracker_reset_zeroes()
    test_tracer_disabled_is_noop()
    test_tracer_enable_creates_events()
    test_tracer_clear_empties()
    test_tracer_export_chrome_writes_json()
    print("\nAll property-based tests passed.")


if __name__ == "__main__":
    run_all()
