from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from urllib.parse import urlparse

from stagehand import AsyncSession, AsyncStagehand

from collarai.chrome import ChromeSession
from collarai.config import Settings, profile_path
from collarai.stagehand_browser import ActionCache, StagehandPage, browser_websocket_url


@dataclass(slots=True)
class BrowserSession:
    stagehand: AsyncSession
    page: StagehandPage
    lock: asyncio.Lock


class BrowserSessionManager:
    """Own one native Stagehand v3 session per platform and keep it warm."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: AsyncStagehand | None = None
        self._sessions: dict[str, BrowserSession] = {}
        self._manager_lock = asyncio.Lock()
        self._cache = ActionCache(settings.state_dir / "stagehand-actions.json")

    @asynccontextmanager
    async def acquire(self, session_key: str) -> AsyncIterator[BrowserSession]:
        session = await self._get_or_create(session_key)
        async with session.lock:
            if await session.page.is_healthy():
                yield session
                return

            await self.invalidate(session_key, expected=session)
            replacement = await self._get_or_create(session_key)
            async with replacement.lock:
                yield replacement

    def has_session(self, session_key: str) -> bool:
        return session_key in self._sessions

    async def close(self) -> None:
        for session in list(self._sessions.values()):
            try:
                await session.page.close()
            finally:
                with suppress(Exception):
                    await session.stagehand.end(timeout=10)
        self._sessions.clear()
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def invalidate(
        self,
        session_key: str,
        *,
        expected: BrowserSession | None = None,
    ) -> None:
        async with self._manager_lock:
            session = self._sessions.get(session_key)
            if session is None or (expected is not None and session is not expected):
                return
            self._sessions.pop(session_key)
        with suppress(Exception):
            await session.page.close()
        with suppress(Exception):
            await session.stagehand.end(timeout=10)

    async def _get_or_create(self, session_key: str) -> BrowserSession:
        if session_key in self._sessions:
            return self._sessions[session_key]
        async with self._manager_lock:
            if session_key in self._sessions:
                return self._sessions[session_key]
            client = self._client or self._new_client()
            self._client = client
            browser, preferred_host, direct_cdp_url = await self._browser_config(session_key)
            stagehand = await client.sessions.start(
                model_name=self.settings.stagehand_model,
                browser=browser,
                self_heal=False,
                verbose=0,
                act_timeout_ms=self.settings.browser_timeout_ms,
                dom_settle_timeout_ms=500,
                timeout=30,
            )
            cdp_url = stagehand.data.cdp_url
            if not cdp_url:
                await stagehand.end(timeout=10)
                raise RuntimeError("Stagehand did not return a CDP endpoint")
            model = {
                "model_name": self.settings.stagehand_model,
                "api_key": self.settings.stagehand_model_api_key,
                "base_url": self.settings.stagehand_model_base_url,
            }
            page = await StagehandPage.open(
                stagehand,
                direct_cdp_url or cdp_url,
                self._cache,
                model,
                self.settings.browser_timeout_ms,
                preferred_host,
            )
            session = BrowserSession(stagehand=stagehand, page=page, lock=asyncio.Lock())
            self._sessions[session_key] = session
            return session

    def _new_client(self) -> AsyncStagehand:
        return AsyncStagehand(
            server="local",
            model_api_key=self.settings.stagehand_model_api_key,
            local_headless=self.settings.headless,
            local_shutdown_on_close=True,
            timeout=30,
            max_retries=1,
        )

    async def _browser_config(
        self,
        session_key: str,
    ) -> tuple[dict, str | None, str | None]:
        if session_key == "pitchbook":
            chrome = ChromeSession(self.settings)
            await asyncio.to_thread(chrome.ensure_running, self.settings.pitchbook_url)
            websocket = await asyncio.to_thread(
                browser_websocket_url,
                self.settings.pitchbook_cdp_url,
            )
            return (
                {"type": "local", "cdp_url": websocket},
                urlparse(self.settings.pitchbook_url).hostname,
                websocket,
            )

        profile = profile_path(self.settings, session_key)
        profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        profile.chmod(0o700)
        return (
            {
                "type": "local",
                "launch_options": {
                    "headless": self.settings.headless,
                    "user_data_dir": str(profile),
                    "preserve_user_data_dir": True,
                    "viewport": {"width": 1440, "height": 1000},
                    "accept_downloads": False,
                },
            },
            None,
            None,
        )
