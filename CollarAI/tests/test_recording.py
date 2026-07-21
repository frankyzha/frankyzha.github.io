from __future__ import annotations

import asyncio
import json

import pytest

from collarai.browser import BrowserSessionManager
from collarai.config import Settings
from collarai.recording import InteractionRecorder


@pytest.mark.asyncio
async def test_recorder_observes_actions_and_redacts_passwords(tmp_path) -> None:
    sessions = BrowserSessionManager(Settings(state_dir=tmp_path, headless=True))
    try:
        async with sessions.acquire("recorder-test") as session:
            page = session.page
            await page.set_content(
                """
                <label>Company <input name="company"></label>
                <label>Password <input name="password" type="password"></label>
                <label>Type
                  <select name="type">
                    <option>Seed</option>
                    <option>Debt Refinancing</option>
                  </select>
                </label>
                <button type="button">Load transactions</button>
                """
            )
            recorder = InteractionRecorder(tmp_path / "captures")
            await recorder.attach(page)
            await page.act(
                selector="xpath=//input[@name='company']",
                method="fill",
                arguments=["Nvidia"],
                intent="fill company",
            )
            await page.act(
                selector="xpath=//input[@name='password']",
                method="fill",
                arguments=["not-stored"],
                intent="fill password",
                sensitive=True,
                recover=False,
            )
            await page.act(
                selector="xpath=//select[@name='type']",
                method="selectOption",
                arguments=["Debt Refinancing"],
                intent="select transaction type",
            )
            await page.act(
                selector="xpath=//button",
                method="click",
                arguments=[],
                intent="load transactions",
            )
            await asyncio.sleep(0.1)
            output = await recorder.save(page)
    finally:
        await sessions.close()

    data = json.loads(output.read_text(encoding="utf-8"))
    assert output.stat().st_mode & 0o777 == 0o600
    assert {event["type"] for event in data["events"]} >= {"change", "click"}
    values = [event.get("element", {}).get("value") for event in data["events"]]
    assert "Nvidia" in values
    assert "[REDACTED]" in values
    assert "not-stored" not in output.read_text(encoding="utf-8")
    assert data["aria_snapshot"]
    assert data["screenshot"]
    assert data["driver"] == "stagehand-v3"
