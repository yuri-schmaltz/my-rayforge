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


# Event tuple: (name, start_ns, end_ns, attrs).
# For instant events (mark()), start_ns == end_ns and the
# exporter renders them as "i" (instant) events.
Event = Tuple[str, int, int, dict]


class Tracer:
    """In-process event recorder.

    All times are nanoseconds from `time.perf_counter_ns`. The
    event list is a flat list of `(name, duration_ns)` tuples;
    nesting is recovered by comparing start times on report.
    """

    def __init__(self) -> None:
        self._events: List[Event] = []
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
                (sp.name, sp.start_ns, sp.end_ns, dict(sp.attrs))
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
        now = time.perf_counter_ns()
        self._events.append((name, now, now, dict(attrs)))

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
        for name, start_ns, end_ns, attrs in self._events:
            if name not in agg:
                agg[name] = [0, 0, attrs]
            agg[name][0] += 1
            agg[name][1] += end_ns - start_ns
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

    def export_chrome(self, path: str, process_name: str = "pires-forge") -> None:
        """Export events in Chrome Trace Event Format.

        The output JSON can be opened in `chrome://tracing`
        (Chrome DevTools), Perfetto UI
        (https://ui.perfetto.dev), or any other tool that
        understands the format. The result is a flame
        graph: each span is a horizontal bar whose width
        is its duration, nested according to start/end
        ordering.

        Format reference:
        https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU

        The output is:
          {
            "traceEvents": [
              {"name": "span_name", "ph": "X", "ts": 0, "dur": 1234,
               "pid": 0, "tid": 0, "args": {...}},
              ...
            ],
            "displayTimeUnit": "ms"
          }

        The `ph` field is "X" for a complete event (with
        start + duration), "i" for an instant event (mark()).
        `ts` is in microseconds (Chrome format); we convert
        from our nanoseconds.

        Nesting recovery: events are sorted by start_ns.
        We assign each event a thread id (tid) based on
        depth-in-stack: a span that starts while another is
        in flight gets a higher tid. This produces a
        readable flame graph on the visualizer side. For
        true per-thread tracing, plug a real tracer
        (perfetto ftrace, eBPF, OTel) — this is a heuristic.
        """
        if not self._events:
            with open(path, "w") as f:
                f.write('{"traceEvents": [], "displayTimeUnit": "ms"}')
            return

        # Sort by start time. The original insertion order
        # is reverse-close (innermost closes first, gets
        # appended first), which is wrong for the timeline
        # view. Re-sort by start_ns to recover the true order.
        sorted_events = sorted(self._events, key=lambda e: e[1])

        # Compute a relative time origin (the first event's
        # start time becomes 0). This keeps ts values small
        # (Chrome's UI displays microseconds).
        t0 = sorted_events[0][1]

        # Walk events in time order. Track an active stack
        # of (end_ns, tid) so we can assign a new tid to
        # any event that starts while an outer one is in
        # flight.
        events_out = []
        active: List = []  # stack of (end_ns, tid)
        next_tid = 0
        for name, start_ns, end_ns, attrs in sorted_events:
            # Pop finished events from the stack
            while active and active[-1][0] <= start_ns:
                active.pop()

            # Pick a tid: the next unused below the stack
            # depth, or a fresh one if all in use.
            depth = len(active)
            used_tids = {t for _, t in active}
            tid = None
            for candidate in range(depth + 1):
                if candidate not in used_tids:
                    tid = candidate
                    break
            if tid is None:
                tid = next_tid
                next_tid += 1

            ts_us = (start_ns - t0) // 1000
            dur_ns = end_ns - start_ns
            if dur_ns == 0:
                # Instant event (mark())
                events_out.append({
                    "name": name,
                    "ph": "i",
                    "ts": ts_us,
                    "pid": 0,
                    "tid": tid,
                    "s": "g",
                })
            else:
                dur_us = max(dur_ns // 1000, 1)
                events_out.append({
                    "name": name,
                    "ph": "X",
                    "ts": ts_us,
                    "dur": dur_us,
                    "pid": 0,
                    "tid": tid,
                    "args": dict(attrs) if attrs else {},
                })
            active.append((end_ns, tid))

        import json

        with open(path, "w") as f:
            json.dump(
                {
                    "traceEvents": events_out,
                    "displayTimeUnit": "ms",
                    "process_name": process_name,
                },
                f,
                indent=2,
            )


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
