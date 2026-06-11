import asyncio
import logging
import webbrowser
from gettext import gettext as _
from typing import TYPE_CHECKING, Optional

import aiohttp
from blinker import Signal

from . import __version__
from .const import DOWNLOAD_URL, GITHUB_RELEASES_API
from .shared.util.versioning import is_newer_version

if TYPE_CHECKING:
    from .context import RayforgeContext
    from .shared.tasker import TaskManager

logger = logging.getLogger(__name__)


class AppUpdateChecker:
    """
    Checks for new Rayforge versions via the GitHub Releases API.
    Runs checks in the background and notifies the UI via signals.
    """

    notification_requested = Signal()
    RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
    MAX_FETCH_ATTEMPTS = 3
    FETCH_BACKOFF_SECONDS = 0.75

    def __init__(self, task_mgr: "TaskManager", context: "RayforgeContext"):
        self._task_mgr = task_mgr
        self._context = context

    def check_on_startup(self):
        config = self._context.config
        if not config.check_for_app_updates:
            logger.info("App update check disabled by user.")
            return
        logger.info("Scheduling app version update check.")
        self._task_mgr.add_coroutine(
            self._check_worker, key="app-update-check"
        )

    async def _check_worker(self, ctx):
        ctx.set_message(_("Checking for Rayforge updates..."))
        try:
            release = await self._fetch_latest_release()
        except Exception as e:
            logger.error(f"Failed to check for app updates: {e}")
            ctx.set_message(_("Update check failed."))
            return

        if release is None:
            ctx.set_message(_("Update check failed."))
            return

        latest_tag = release.get("tag_name", "")

        if is_newer_version(latest_tag, __version__ or "0.0.0"):
            logger.info(
                f"New version available: {latest_tag} (current: {__version__})"
            )
            msg = _("Rayforge {version} is available.").format(
                version=latest_tag
            )

            def _open_download():
                webbrowser.open(DOWNLOAD_URL)

            self._task_mgr.schedule_on_main_thread(
                self.notification_requested.send,
                self,
                message=msg,
                persistent=True,
                action_label=_("Download"),
                action_callback=_open_download,
            )
            ctx.set_message(_("New version available."))
        else:
            logger.info("Rayforge is up to date.")
            ctx.set_message(_("Rayforge is up to date."))

    async def _fetch_latest_release(self) -> Optional[dict]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "rayforge-updater",
        }
        timeout = aiohttp.ClientTimeout(total=15)

        for attempt in range(1, self.MAX_FETCH_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        GITHUB_RELEASES_API,
                        timeout=timeout,
                    ) as response:
                        if response.status == 200:
                            payload = await response.json(
                                content_type=None
                            )
                            if isinstance(payload, dict):
                                return payload
                            logger.warning(
                                "GitHub API payload is not an object"
                            )
                            return None

                        should_retry = (
                            response.status in self.RETRYABLE_HTTP_STATUSES
                            and attempt < self.MAX_FETCH_ATTEMPTS
                        )
                        if should_retry:
                            logger.warning(
                                "GitHub API returned status %s "
                                "(attempt %s/%s)",
                                response.status,
                                attempt,
                                self.MAX_FETCH_ATTEMPTS,
                            )
                            await asyncio.sleep(self.FETCH_BACKOFF_SECONDS)
                            continue

                        logger.warning(
                            f"GitHub API returned status {response.status}"
                        )
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < self.MAX_FETCH_ATTEMPTS:
                    logger.warning(
                        "Error fetching release info (attempt %s/%s): %s",
                        attempt,
                        self.MAX_FETCH_ATTEMPTS,
                        e,
                    )
                    await asyncio.sleep(self.FETCH_BACKOFF_SECONDS)
                    continue
                logger.error(f"Error fetching release info: {e}")
                return None

        return None
