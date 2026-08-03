"""
Tests for rayforge.usage UsageTracker.

The analytics POST is wrapped in resilient_post; these tests verify
the wrapping behaviour, including:
- Successful POST updates the cache token
- Failure (resilient_post returns None) is silent (no exception)
- Headers are passed through correctly
"""

import json
import threading
import time
from unittest.mock import patch

import pytest

from rayforge.usage import UsageTracker


def _wait_for_threads(timeout: float = 1.0) -> None:
    """Drain the daemon thread pool used by UsageTracker._send_event."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        alive = [t for t in threading.enumerate()
                 if t is not threading.current_thread() and t.is_alive()]
        if not alive:
            return
        time.sleep(0.01)


@pytest.fixture
def tracker():
    """A fresh UsageTracker instance, bypassing the singleton."""
    t = UsageTracker.__new__(UsageTracker)
    t._initialized = True
    t._enabled = True
    t._cache_token = None
    t._screen = "1920x1080"
    t._language = "en_US"
    t._os = "linux/5.0"
    t._version = "1.0.0+dev1"
    t._session_id = "test-session-id"
    return t


class TestSendEventSuccess:
    def test_sends_to_umami_url(self, tracker):
        with patch("rayforge.usage.resilient_post", return_value=None) as m:
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        assert m.called
        # First positional arg is the URL
        assert m.call_args.args[0].startswith("http")

    def test_passes_correct_headers(self, tracker):
        with patch("rayforge.usage.resilient_post", return_value=None) as m:
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        headers = m.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers
        # No cache token yet
        assert "x-umami-cache" not in headers

    def test_includes_cache_token_when_set(self, tracker):
        tracker._cache_token = "abc123"
        with patch("rayforge.usage.resilient_post", return_value=None) as m:
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        headers = m.call_args.kwargs["headers"]
        assert headers["x-umami-cache"] == "abc123"

    def test_payload_is_event_type_wrapped(self, tracker):
        with patch("rayforge.usage.resilient_post", return_value=None) as m:
            tracker._send_event({"event": "/click", "url": "/x"})
        _wait_for_threads()
        sent_data = m.call_args.kwargs["data"]
        parsed = json.loads(sent_data)
        assert parsed["type"] == "event"
        assert parsed["payload"] == {"event": "/click", "url": "/x"}


class TestSendEventFailure:
    def test_silent_on_network_failure(self, tracker):
        # resilient_post returns None on failure (and never raises)
        with patch("rayforge.usage.resilient_post", return_value=None):
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        # If we got here without exception, the test passes

    def test_silent_on_unexpected_exception(self, tracker):
        # Defensive: if anything in _send raises, we log and move on
        with patch(
            "rayforge.usage.resilient_post",
            side_effect=Exception("unexpected"),
        ):
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        # No exception propagated to caller


class TestCacheTokenUpdate:
    def test_updates_cache_token_from_response(self, tracker):
        with patch(
            "rayforge.usage.resilient_post",
            return_value=json.dumps({"cache": "new-token-xyz"}).encode(),
        ):
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        assert tracker._cache_token == "new-token-xyz"

    def test_no_update_on_missing_cache_field(self, tracker):
        with patch(
            "rayforge.usage.resilient_post",
            return_value=json.dumps({"other": "field"}).encode(),
        ):
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        # No exception, cache_token unchanged (still None)
        assert tracker._cache_token is None

    def test_no_update_on_invalid_json(self, tracker):
        with patch(
            "rayforge.usage.resilient_post",
            return_value=b"not json {{{",
        ):
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        # No exception, cache_token unchanged
        assert tracker._cache_token is None

    def test_no_update_on_empty_response(self, tracker):
        with patch(
            "rayforge.usage.resilient_post",
            return_value=b"",
        ):
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        assert tracker._cache_token is None


class TestResilienceConfig:
    def test_uses_max_attempts_2(self, tracker):
        """Usage analytics should retry at most once to bound duplicates."""
        with patch("rayforge.usage.resilient_post", return_value=None) as m:
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        assert m.call_args.kwargs["max_attempts"] == 2

    def test_uses_short_timeout(self, tracker):
        """Analytics should not block the user for long."""
        with patch("rayforge.usage.resilient_post", return_value=None) as m:
            tracker._send_event({"event": "/test", "url": "/x"})
        _wait_for_threads()
        assert m.call_args.kwargs["timeout"] == 5
