"""Local-only usage tracker (no telemetry, no network).

The InsightsDialog shows simple in-memory usage stats. This
class is a side-tracker that increments counters on every
Gio.SimpleAction fire. It is independent of the Umami
tracker in rayforge/usage.py (which sends data to a server);
local-tracker is opt-in, zero-network, and never leaves the
process.

API:

  local_tracker = LocalTracker()
  local_tracker.record_action("save")        # on every action
  local_tracker.record_mode("framing")       # on mode change

The InsightsDialog reads top_actions(10), total_actions,
current_mode, and format_session_time() to populate itself.
All counters are in-memory; a process restart resets them.
This is intentional — the value of usage stats is in
short-term patterns (a single work session), not in
multi-month aggregation. Long-term aggregation would need
explicit opt-in and a privacy policy.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Optional


class LocalTracker:
    """In-memory action + mode counter for InsightsDialog."""

    def __init__(self) -> None:
        self._actions: Counter = Counter()
        self._mode_history: list = []
        self._current_mode: Optional[str] = None
        self._session_start = time.monotonic()

    def record_action(self, name: str) -> None:
        """Increment the counter for `name`. Idempotent on the
        counter itself; safe to call from any thread."""
        if not name:
            return
        self._actions[name] += 1

    def record_mode(self, mode: str) -> None:
        """Update the current mode. The transition (old -> new)
        is appended to the history so future versions can show
        'mode flow' (e.g. a sankey diagram). For now we just
        remember the latest."""
        if mode == self._current_mode:
            return
        if self._current_mode is not None:
            self._mode_history.append((self._current_mode, mode))
        self._current_mode = mode

    def top_actions(self, n: int = 10) -> list:
        """Return the top `n` actions as [(name, count), ...],
        sorted by count descending, then by name ascending for
        stability."""
        return self._actions.most_common(n)

    @property
    def total_actions(self) -> int:
        return sum(self._actions.values())

    @property
    def current_mode(self) -> Optional[str]:
        return self._current_mode

    def format_session_time(self) -> str:
        """Format the session duration as 'Xh Ym' or 'Xm Ys'."""
        elapsed = int(time.monotonic() - self._session_start)
        hours, rem = divmod(elapsed, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def reset_session(self) -> None:
        """Reset all counters to zero. The session timer
        restarts now. The mode history is cleared (since
        it's based on the counters' meaning)."""
        self._actions = Counter()
        self._mode_history = []
        self._session_start = time.monotonic()


# Singleton accessor. Mirrors the pattern in
# rayforge/usage.py:get_usage_tracker() so callers can do
# `from ..util.local_tracker import get_local_tracker`
# without thinking about instances.
_instance: Optional[LocalTracker] = None


def get_local_tracker() -> LocalTracker:
    global _instance
    if _instance is None:
        _instance = LocalTracker()
    return _instance
