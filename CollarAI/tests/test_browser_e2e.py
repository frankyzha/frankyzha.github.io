from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from collarai.config import Settings
from collarai.models import CompanyScreen, FundingStage, RunStatus
from collarai.service import build_service
from collarai.toy.app import create_app


@pytest.fixture
def toy_server() -> Iterator[str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    if not server.started:
        raise RuntimeError("Toy server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_real_browser_login_screen_and_evidence(tmp_path, toy_server: str) -> None:
    settings = Settings(state_dir=tmp_path, toy_base_url=toy_server, headless=True)
    service = build_service(settings)
    try:
        result = await service.screen_companies(
            CompanyScreen(
                countries=["United States"],
                industries=["Enterprise Software"],
                founded_year_min=2021,
                funding_stages=[FundingStage.SERIES_A, FundingStage.SERIES_B],
                total_raised_usd_lt=50_000_000,
            )
        )
        assert result.status is RunStatus.COMPLETE, result.message
        assert [company.name for company in result.companies] == [
            "Northstar Systems",
            "Juniper Grid",
            "Relay Harbor",
        ]
        run_dir = tmp_path / "runs" / result.run_id
        assert (run_dir / "result.json").is_file()
        assert (run_dir / "final.png").stat().st_size > 0
        assert (run_dir / "stagehand.json").stat().st_size > 0
        assert service.get_run(result.run_id) == result
    finally:
        await service.close()
