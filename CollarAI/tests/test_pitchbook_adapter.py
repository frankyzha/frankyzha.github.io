from __future__ import annotations

import pytest

from collarai.adapters.pitchbook import PitchBookAdapter
from collarai.browser import BrowserSessionManager
from collarai.config import Settings
from collarai.models import FinancingCategory


def test_pitchbook_value_parsing_and_company_matching() -> None:
    assert PitchBookAdapter._parse_usd_amount("$25.00B") == 25_000_000_000
    assert PitchBookAdapter._parse_usd_amount("$1.25M E") == 1_250_000
    assert PitchBookAdapter._parse_usd_amount("Undisclosed") is None
    assert PitchBookAdapter._matches_company_result("Nvidia (NAS: NVDA) Public Company", "Nvidia")
    assert not PitchBookAdapter._matches_company_result("Nvidia Supplier", "Nvidia")


@pytest.mark.asyncio
async def test_pitchbook_extracts_semantic_transaction_table(tmp_path) -> None:
    sessions = BrowserSessionManager(Settings(state_dir=tmp_path, headless=True))
    try:
        async with sessions.acquire("adapter-test") as session:
            await session.page.set_content(
                """
                <table>
                  <thead><tr>
                    <th></th><th>#</th><th></th><th>Deal Type</th><th>Date</th><th>Amount</th>
                    <th>Raised to Date</th><th>Pre-Val</th><th>Post-Val</th>
                    <th>Investor</th><th>Stage</th>
                  </tr></thead>
                  <tbody>
                    <tr><td></td><td>13</td><td></td><td>Debt Refinancing</td>
                      <td>15-Jun-2026</td><td>$25.00B</td><td>$41.06B</td><td></td><td></td><td></td><td></td></tr>
                    <tr><td colspan="11"><table><tbody><tr>
                      <td>Debt Amount (M)</td><td>Not a top-level transaction</td>
                    </tr></tbody></table></td></tr>
                    <tr><td></td><td>10</td><td></td><td>Debt Refinancing</td>
                      <td>14-Jun-2021</td><td>$5.00B</td><td>$16.06B</td><td></td><td></td><td></td><td></td></tr>
                    <tr><td></td><td>8</td><td></td><td>Senior Notes</td>
                      <td>01-Jan-2019</td><td>$1.00B</td><td>$11.06B</td><td></td><td></td><td></td><td></td></tr>
                  </tbody>
                </table>
                """
            )
            adapter = PitchBookAdapter("https://my.pitchbook.com")
            transactions, signature = await adapter._extract_current_page(
                session.page,
                "Nvidia",
                FinancingCategory.DEBT,
            )
    finally:
        await sessions.close()

    assert len(transactions) == 3
    assert sum(item.amount_usd or 0 for item in transactions) == 31_000_000_000
    assert transactions[0].raised_to_date_usd == 41_060_000_000
    assert transactions[0].announced_date.isoformat() == "2026-06-15"
    assert signature != "empty"
