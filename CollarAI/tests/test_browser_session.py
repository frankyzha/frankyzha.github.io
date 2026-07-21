from __future__ import annotations

import asyncio

import pytest

from collarai.browser import BrowserSession, BrowserSessionManager
from collarai.config import Settings


class FakePage:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy
        self.closed = False

    async def is_healthy(self) -> bool:
        return self.healthy

    async def close(self) -> None:
        self.closed = True


class FakeStagehandSession:
    def __init__(self) -> None:
        self.ended = False

    async def end(self, timeout: int) -> None:
        self.ended = True


@pytest.mark.asyncio
async def test_session_manager_replaces_an_unhealthy_warm_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = BrowserSessionManager(Settings(state_dir=tmp_path))
    stale_page = FakePage(healthy=False)
    stale_stagehand = FakeStagehandSession()
    stale = BrowserSession(stale_stagehand, stale_page, asyncio.Lock())  # type: ignore[arg-type]
    replacement = BrowserSession(  # type: ignore[arg-type]
        FakeStagehandSession(),
        FakePage(healthy=True),
        asyncio.Lock(),
    )
    manager._sessions["pitchbook"] = stale

    async def get_or_create(_: str) -> BrowserSession:
        return manager._sessions.setdefault("pitchbook", replacement)

    monkeypatch.setattr(manager, "_get_or_create", get_or_create)

    async with manager.acquire("pitchbook") as acquired:
        assert acquired is replacement

    assert stale_page.closed
    assert stale_stagehand.ended
