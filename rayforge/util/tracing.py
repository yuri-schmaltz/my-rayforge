"""Lightweight, in-process tracing for performance instrumentation.

The `Tracer` class is a minimal, no-deps tracing utility built on
`time.perf_counter_ns`. It records `(name, duration_ns)` pairs and
exposes a small API:

  with tracer.span("canvas.render"):
      surface.draw()

  tracer.mark("gcode.start", layer=3)
  tracer.mark("gcode.end", layer=3)

Spans nest; on `__exit__` the duration is appended to a flat list
of events. The `report()` method formats the list as a sorted
table by total time.

Why not OpenTelemetry? This is a desktop app, not a service. We
don't need distributed tracing, span exporters, or sampling. A
flat event list dumped via `tracer.report()` to a log line is
enough to find hot spots, and adds <1µs per event.

The tracer is opt-in: nothing is traced unless you wrap a code
path with `span()` or call `mark()`. The cost of having the
tracer instantiated at startup is one dict + one list. There
is no background thread, no file IO, and no GLib timer running.

Usage from code:

  from rayforge.util.tracing import get_tracer
  tracer = get_tracer()

  def expensive_thing():
      with tracer.span("exp.do"):
          ...

  # Later, dump a report
  logger.info(tracer.report(top_n=20))

Configuration via env var `RAYFORGE_TRACE=1` enables startup
tracing of major phases (init, addon load, window show). When
unset, the tracer is silent.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class _Span:
    """A single traced span. Created by `Tracer.span()`."""

    __slots__ = ("name", "start_ns", "end_ns", "parent", "attrs")

    def __init__(self, name: str, parent: Optional["_Span"]) -> None:
        self.name = name
        self.start_ns = time.perf_counter_ns()
        self.end_ns = 0
        self.parent = parent
        self.attrs: dict = {}


class Tracer:
    """In-process event recorder.

    All times are nanoseconds from `time.perf_counter_ns`. The
    event list is a flat list of `(name, duration_ns)` tuples;
    nesting is recovered by comparing start times on report.
    """

    def __init__(self) -> None:
        self._events: List[Tuple[str, int, dict]] = []
        self._current: Optional[_Span] = None
        self._enabled = bool(os.environ.get("RAYFORGE_TRACE"))

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @contextmanager
    def span(self, name: str, **attrs) -> Iterator[None]:
        """Wrap a code block as a named span.

        The span is recorded on `__exit__`. Nested spans are
        supported: each `span()` call pushes a new span onto
        an internal stack; on exit, the duration is computed
        and the span is popped.

        Args:
            name: A short identifier (e.g. 'canvas.render').
            **attrs: Optional key-value pairs attached to
                the span. Recorded but not used for sorting
                or filtering (yet).
        """
        if not self._enabled:
            yield
            return
        sp = _Span(name, self._current)
        sp.attrs.update(attrs)
        self._current = sp
        try:
            yield
        finally:
            sp.end_ns = time.perf_counter_ns()
            self._events.append(
                (sp.name, sp.end_ns - sp.start_ns, sp.attrs)
            )
            self._current = sp.parent

    def mark(self, name: str, **attrs) -> None:
        """Record a single instant event (no duration).

        Useful for marking state transitions ('job.started',
        'addon.loaded', 'canvas.first-paint') that don't have
        a meaningful duration but should appear in the report
        for correlation.
        """
        if not self._enabled:
            return
        # Zero-duration events appear in the report but
        # naturally sort to the bottom (since they're zero).
        self._events.append((name, 0, attrs))

    def clear(self) -> None:
        """Drop all recorded events. Useful between benchmark
        iterations so the report shows only the iteration of
        interest."""
        self._events.clear()
        self._current = None

    def report(self, top_n: int = 20) -> str:
        """Format the recorded events as a human-readable table.

        Returns a multi-line string. The table is sorted by
        total time per event name (so repeated spans are
        summed; e.g. 1000 calls to 'canvas.draw' at 50µs
        each is reported as 'canvas.draw: 50ms (n=1000)').
        """
        if not self._events:
            return "(no trace events recorded)"
        # Aggregate by name
        agg: dict = {}
        for name, dur, attrs in self._events:
            if name not in agg:
                agg[name] = [0, 0, attrs]
            agg[name][0] += 1
            agg[name][1] += dur
        # Sort by total time, descending
        rows = sorted(agg.items(), key=lambda kv: -kv[1][1])
        lines = ["trace report (top {}):".format(min(top_n, len(rows)))]
        lines.append(
            f"  {'name':<40} {'count':>6} {'total':>12} {'avg':>12}"
        )
        lines.append("  " + "-" * 72)
        for name, (count, total, _attrs) in rows[:top_n]:
            avg = total // count if count else 0
            lines.append(
                f"  {name:<40} {count:>6} "
                f"{_format_ns(total):>12} {_format_ns(avg):>12}"
            )
        return "\n".join(lines)


def _format_ns(ns: int) -> str:
    """Format a duration in nanoseconds as a human string.

    - < 1µs   :  'NNN ns'
    - < 1ms   :  'NNN.NN µs'
    - < 1s    :  'NNN.NN ms'
    - else    :  'N.NN s'
    """
    if ns < 1_000:
        return f"{ns} ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:.2f} µs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:.2f} ms"
    return f"{ns / 1_000_000_000:.2f} s"


# Module-level singleton. Lazy on first call.
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Return the process-wide tracer. Cheap to call."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
