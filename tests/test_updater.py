from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from rayforge.updater import AppUpdateChecker


class _DummyResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload


class _DummySession:
    def __init__(self, items):
        self._items = list(items)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def checker():
    mock_task_mgr = MagicMock()
    mock_context = MagicMock()
    mock_context.config.check_for_app_updates = True
    return AppUpdateChecker(mock_task_mgr, mock_context)


class TestCheckOnStartup:
    def test_disabled_does_not_schedule(self, checker):
        checker._context.config.check_for_app_updates = False
        checker.check_on_startup()
        checker._task_mgr.add_coroutine.assert_not_called()

    def test_enabled_schedules_check(self, checker):
        checker.check_on_startup()
        checker._task_mgr.add_coroutine.assert_called_once()


@pytest.mark.asyncio
class TestCheckWorker:
    async def test_no_notification_when_up_to_date(self, checker):
        ctx = MagicMock()
        with (
            patch.object(
                checker,
                "_fetch_latest_release",
                return_value={"tag_name": "0.0.1"},
            ),
            patch("rayforge.updater.__version__", "0.0.1"),
        ):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_not_called()
        ctx.set_message.assert_called()

    async def test_notification_when_new_version_available(self, checker):
        ctx = MagicMock()
        with (
            patch.object(
                checker,
                "_fetch_latest_release",
                return_value={"tag_name": "99.0.0"},
            ),
            patch("rayforge.updater.__version__", "1.0.0"),
        ):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_called_once()
        kwargs = checker._task_mgr.schedule_on_main_thread.call_args[1]
        assert "99.0.0" in kwargs["message"]

    async def test_no_notification_on_fetch_failure(self, checker):
        ctx = MagicMock()
        with patch.object(checker, "_fetch_latest_release", return_value=None):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_not_called()
        ctx.set_message.assert_called()

    async def test_no_notification_on_exception(self, checker):
        ctx = MagicMock()
        with patch.object(
            checker,
            "_fetch_latest_release",
            side_effect=Exception("network error"),
        ):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_not_called()
        ctx.set_message.assert_called()

    async def test_git_describe_version_treated_as_equal(self, checker):
        ctx = MagicMock()
        with (
            patch.object(
                checker,
                "_fetch_latest_release",
                return_value={"tag_name": "1.5.2"},
            ),
            patch("rayforge.updater.__version__", "1.5.2-3-gabcdef1"),
        ):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_not_called()

    async def test_prerelease_notified_when_release_exists(self, checker):
        ctx = MagicMock()
        with (
            patch.object(
                checker,
                "_fetch_latest_release",
                return_value={"tag_name": "1.0.0"},
            ),
            patch("rayforge.updater.__version__", "1.0.0-beta1"),
        ):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_called_once()

    async def test_pep440_post_git_not_newer_than_older_release(self, checker):
        ctx = MagicMock()
        with (
            patch.object(
                checker,
                "_fetch_latest_release",
                return_value={"tag_name": "1.5.2"},
            ),
            patch(
                "rayforge.updater.__version__",
                "1.6.0b2.post6+git.7f927a18",
            ),
        ):
            await checker._check_worker(ctx)

        checker._task_mgr.schedule_on_main_thread.assert_not_called()


@pytest.mark.asyncio
class TestFetchLatestRelease:
    async def test_retries_on_transient_status(self, checker):
        checker.FETCH_BACKOFF_SECONDS = 0
        sessions = [
            _DummySession([_DummyResponse(503)]),
            _DummySession([
                _DummyResponse(200, {"tag_name": "1.2.3"})
            ]),
        ]
        with patch(
            "rayforge.updater.aiohttp.ClientSession",
            side_effect=sessions,
        ):
            result = await checker._fetch_latest_release()

        assert result == {"tag_name": "1.2.3"}

    async def test_retries_on_client_error_then_succeeds(self, checker):
        checker.FETCH_BACKOFF_SECONDS = 0
        sessions = [
            _DummySession([aiohttp.ClientError("boom")]),
            _DummySession([
                _DummyResponse(200, {"tag_name": "2.0.0"})
            ]),
        ]
        with patch(
            "rayforge.updater.aiohttp.ClientSession",
            side_effect=sessions,
        ):
            result = await checker._fetch_latest_release()

        assert result == {"tag_name": "2.0.0"}

    async def test_non_retryable_status_returns_none(self, checker):
        sessions = [_DummySession([_DummyResponse(404)])]
        with patch(
            "rayforge.updater.aiohttp.ClientSession",
            side_effect=sessions,
        ):
            result = await checker._fetch_latest_release()

        assert result is None
