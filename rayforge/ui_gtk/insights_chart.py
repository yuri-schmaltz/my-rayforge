"""Sparkline chart for the Insights dialog.

A small, self-contained sparkline widget that draws a
time series of action counts. The x-axis is a window
of the last N events (default 60); the y-axis scales
to the max value in the window. No axes, no grid, no
labels — just a sparkline. Designed to fit in the
Insights dialog as a glance.

Implementation: a Gtk.DrawingArea with a custom draw
function. We use Cairo (via PyGObject) to draw a
single polyline. The widget is ~80 lines because the
data source is simple (a deque of recent event
counts) and the rendering is one path stroke.

The data source is the LocalTracker; we sample the
total action count every 1s and store the (count,
timestamp) pair. The chart renders the most recent
60 samples (1 minute of activity).

Why a custom widget and not matplotlib? The chart is
80px tall and 240px wide — matplotlib would add 30MB
to the install for a single line. Cairo is already
loaded by GTK 4 + the canvas. ~80 lines of custom
code is the right trade-off.

Why a sparkline and not a bar chart? A bar chart
reads as 'how much'; a sparkline reads as 'how is
it changing'. For a 1-minute window of action
counts, the latter is more useful. The Insights
dialog already shows the absolute count (the
'top 10 actions' list); the sparkline adds the
temporal context.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Optional

from gi.repository import Gtk, GLib

logger = logging.getLogger(__name__)


class InsightsChart(Gtk.DrawingArea):
    """A sparkline of recent action counts.

    The widget updates itself every UPDATE_INTERVAL_MS
    (default 1000) by sampling LocalTracker.total_actions
    and appending to a bounded deque. The draw function
    renders the deque as a single polyline.

    Usage:

        chart = InsightsChart(tracker=local_tracker)
        chart.set_size_request(240, 80)
    """

    UPDATE_INTERVAL_MS = 1000
    WINDOW_SECONDS = 60  # 1 minute of data

    def __init__(self, tracker, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tracker = tracker
        self._samples: deque = deque(maxlen=self.WINDOW_SECONDS)
        self._last_count = 0
        self.set_size_request(240, 80)
        self.set_draw_func(self._draw)
        # Update every 1s. Returns False to keep the
        # timeout active (GLib convention: returning
        # False removes the source).
        GLib.timeout_add(
            self.UPDATE_INTERVAL_MS, self._on_tick
        )

    def _on_tick(self) -> bool:
        """Sample the tracker and queue a redraw."""
        now = time.monotonic()
        current = self._tracker.total_actions
        self._samples.append((now, current))
        self.queue_draw()
        return True  # keep the timeout

    def _draw(self, area, cr, width, height):
        """Render the samples as a sparkline."""
        # Background
        cr.set_source_rgb(0.98, 0.98, 0.99)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if not self._samples:
            return

        # Find the max in the window for y-scaling
        max_count = max(s[1] for s in self._samples)
        if max_count == 0:
            return

        # Compute the time window. We use the LAST sample
        # as the right edge; the LEFT edge is WINDOW_SECONDS
        # ago. Anything older is clipped.
        t_now = self._samples[-1][0]
        t_min = t_now - self.WINDOW_SECONDS

        # Build the polyline
        cr.set_source_rgb(0.10, 0.45, 0.91)
        cr.set_line_width(1.5)
        cr.set_line_cap(1)  # round caps
        cr.set_line_join(1)  # round joins

        started = False
        for t, count in self._samples:
            if t < t_min:
                continue
            x = (t - t_min) / self.WINDOW_SECONDS * width
            # y: top of the chart is the max, bottom is 0
            y = height - (count / max_count * (height - 4)) - 2
            if not started:
                cr.move_to(x, y)
                started = True
            else:
                cr.line_to(x, y)
        cr.stroke()

        # Last point: a small dot, so the user can see
        # 'where we are right now'.
        if self._samples:
            t_last, c_last = self._samples[-1]
            x = (t_last - t_min) / self.WINDOW_SECONDS * width
            y = height - (c_last / max_count * (height - 4)) - 2
            cr.set_source_rgb(0.10, 0.30, 0.65)
            cr.arc(x, y, 3, 0, 2 * 3.14159)
            cr.fill()
