from __future__ import annotations

import json

from collarai.adapters.base import SiteAdapter
from collarai.errors import AuthenticationRequired, WorkflowError
from collarai.models import (
    BrowserSessionStatus,
    Company,
    CompanyScreen,
    FundingStage,
)
from collarai.stagehand_browser import StagehandPage


class ToyMarketAdapter(SiteAdapter):
    platform = "toy"

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    async def inspect_session(self, page: StagehandPage) -> BrowserSessionStatus:
        await self._open(page)
        signed_in = await page.visible("#screen-panel")
        return BrowserSessionStatus(
            platform=self.platform,
            state="signed_in" if signed_in else "signed_out",
            current_url=await page.current_url(),
        )

    async def ensure_authenticated(self, page: StagehandPage) -> None:
        await self._open(page)
        if await page.visible("#screen-panel"):
            return
        if not self.username or not self.password:
            raise AuthenticationRequired("Open the browser and sign in to the toy market site")
        await page.act(
            selector="xpath=//input[@type='email']",
            method="fill",
            arguments=[self.username],
            intent="fill the toy market email field",
        )
        await page.act(
            selector="xpath=//input[@type='password']",
            method="fill",
            arguments=[self.password],
            intent="fill the toy market password field",
            sensitive=True,
            recover=False,
        )
        await self.click(page, "xpath=//*[@id='login-form']//button[@type='submit']", "sign in")
        try:
            await page.wait_visible("#screen-panel")
        except WorkflowError as error:
            message = await page.evaluate(
                "document.querySelector('#login-message')?.textContent || ''"
            )
            raise AuthenticationRequired(str(message) or "Toy site login failed") from error

    async def screen(self, page: StagehandPage, query: CompanyScreen) -> list[Company]:
        await self._set_multiselect(page, "#countries", query.countries)
        await self._set_multiselect(page, "#industries", query.industries)
        await self._fill(page, "#founded-year-min", query.founded_year_min)
        await self._fill(page, "#raised-less-than", query.total_raised_usd_lt)
        await self._fill(page, "#result-limit", query.limit)
        await self._set_stages(page, [stage.value for stage in query.funding_stages])
        await self.click(
            page,
            "xpath=//*[@id='screen-form']//button[@type='submit']",
            "run the company screen",
        )
        await page.wait_until(
            lambda: self._results_complete(page, "#results"),
            "The toy company screen did not complete",
        )
        await self._verify_filters(page, query)
        return await self._extract_companies(page)

    async def _open(self, page: StagehandPage) -> None:
        if not (await page.current_url()).startswith(self.base_url):
            await page.goto(self.base_url)
        await page.wait_until(
            lambda: self._body_ready(page),
            "The toy site did not become ready",
        )

    @staticmethod
    async def _body_ready(page: StagehandPage) -> bool:
        return await page.attribute("body", "data-ready") == "true"

    @staticmethod
    async def _results_complete(page: StagehandPage, selector: str) -> bool:
        return await page.attribute(selector, "data-state") == "complete"

    @staticmethod
    async def _fill(page: StagehandPage, selector: str, value: int | None) -> None:
        await page.act(
            selector=f"xpath=//*[@id={json.dumps(selector.removeprefix('#'))}]",
            method="fill",
            arguments=[str(value) if value is not None else ""],
            intent=f"set the toy field {selector}",
        )

    @staticmethod
    async def _set_multiselect(page: StagehandPage, selector: str, values: list[str]) -> None:
        await page.evaluate(
            "(() => { const select = document.querySelector("
            + json.dumps(selector)
            + "); const wanted = new Set("
            + json.dumps(values)
            + "); for (const option of select.options) option.selected = "
            "wanted.has(option.value) || wanted.has(option.textContent.trim()); "
            "select.dispatchEvent(new Event('change', {bubbles: true})); })()"
        )

    @staticmethod
    async def _set_stages(page: StagehandPage, values: list[str]) -> None:
        await page.evaluate(
            "(() => { const wanted = new Set("
            + json.dumps(values)
            + "); for (const input of document.querySelectorAll('input[name=funding-stage]')) { "
            "input.checked = wanted.has(input.value); input.dispatchEvent(new Event('change', "
            "{bubbles: true})); } })()"
        )

    async def _verify_filters(self, page: StagehandPage, query: CompanyScreen) -> None:
        actual = str(
            await page.evaluate(
                "document.querySelector('[data-testid=active-filters]')?.textContent || ''"
            )
        )
        expected = [*query.countries, *query.industries]
        expected.extend(stage.value for stage in query.funding_stages)
        if query.founded_year_min:
            expected.append(str(query.founded_year_min))
        if query.total_raised_usd_lt:
            expected.append(f"${query.total_raised_usd_lt:,}")
        missing = [value for value in expected if value not in actual]
        if missing:
            raise WorkflowError(f"The site did not apply these filters: {', '.join(missing)}")

    async def _extract_companies(self, page: StagehandPage) -> list[Company]:
        rows = await page.evaluate(
            """
            Array.from(document.querySelectorAll('#company-rows tr[data-company]'), row => ({
              name: row.querySelector('.company-name')?.textContent?.trim(),
              country: row.querySelector('.company-country')?.textContent?.trim(),
              industry: row.querySelector('.company-industry')?.textContent?.trim(),
              foundedYear: Number(row.dataset.foundedYear),
              fundingStage: row.querySelector('.company-stage')?.textContent?.trim(),
              totalRaisedUsd: Number(row.dataset.totalRaisedUsd),
              sourceUrl: row.dataset.sourceUrl,
            }))
            """
        )
        source_url = await page.current_url()
        return [
            Company(
                name=row["name"],
                country=row["country"],
                industry=row["industry"],
                founded_year=row["foundedYear"],
                funding_stage=FundingStage(row["fundingStage"]),
                total_raised_usd=row["totalRaisedUsd"],
                source_url=row.get("sourceUrl") or source_url,
            )
            for row in rows or []
        ]
