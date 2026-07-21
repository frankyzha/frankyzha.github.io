from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlparse

from collarai.adapters.base import SiteAdapter
from collarai.credentials import CredentialStore
from collarai.errors import AuthenticationRequired, ConfigurationRequired, WorkflowError
from collarai.models import (
    BrowserSessionStatus,
    Company,
    CompanyScreen,
    FinancingCategory,
    FinancingTransaction,
)
from collarai.pitchbook_auth import PitchBookAuthenticator
from collarai.stagehand_browser import StagehandPage

_COMPANY_PROFILE = re.compile(r"/profile/([^/]+)/company(?:/|$)")
_DEALS_PROFILE = re.compile(r"/profile/[^/]+/company/deals(?:[/?#]|$)")
_SECURITY_CHALLENGE = re.compile(
    r"just a moment|performing security verification|verify you are human",
    re.IGNORECASE,
)
_SIGN_IN = re.compile(r"sign in|log in", re.IGNORECASE)
_AMOUNT = re.compile(
    r"^\s*\$?\s*(?P<number>[0-9][0-9,]*(?:\.[0-9]+)?)\s*"
    r"(?P<suffix>[KMBT])?\s*(?:[E\u2020\u2021]*)\s*$",
    re.IGNORECASE,
)
_AMOUNT_MULTIPLIERS = {
    "": Decimal(1),
    "K": Decimal(1_000),
    "M": Decimal(1_000_000),
    "B": Decimal(1_000_000_000),
    "T": Decimal(1_000_000_000_000),
}
_SEARCH = "#general-search-input"
_CATEGORY = '[role="combobox"][aria-label="category"]'
_CURRENCY = '[role="combobox"][aria-label="currency"]'


class PitchBookAdapter(SiteAdapter):
    """Deterministic PitchBook workflows executed by native Stagehand v3 actions."""

    platform = "pitchbook"

    def __init__(
        self,
        base_url: str,
        credentials: CredentialStore | None = None,
        authenticator: PitchBookAuthenticator | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.hostname = urlparse(self.base_url).hostname
        self.credentials = credentials
        self.authenticator = authenticator or PitchBookAuthenticator()

    async def inspect_session(self, page: StagehandPage) -> BrowserSessionStatus:
        current_url = await page.current_url()
        if current_url == "about:blank":
            return BrowserSessionStatus(platform=self.platform, state="not_started")

        if await self._has_security_challenge(page):
            return BrowserSessionStatus(
                platform=self.platform,
                state="unknown",
                current_url=current_url,
                message="PitchBook security verification is waiting in Chrome.",
            )

        if await page.visible(_SEARCH):
            return BrowserSessionStatus(
                platform=self.platform,
                state="signed_in",
                current_url=current_url,
            )

        if _SIGN_IN.search(await page.body_text()) or _SIGN_IN.search(current_url):
            return BrowserSessionStatus(
                platform=self.platform,
                state="signed_out",
                current_url=current_url,
            )

        return BrowserSessionStatus(
            platform=self.platform,
            state="unknown",
            current_url=current_url,
            message="PitchBook is open, but its authenticated application shell is not ready.",
        )

    async def ensure_authenticated(self, page: StagehandPage) -> None:
        if urlparse(await page.current_url()).hostname != self.hostname:
            await page.goto(self.base_url)

        try:
            await page.wait_visible(_SEARCH)
            await self._save_session(page)
            return
        except WorkflowError:
            pass

        if self.credentials:
            cookies = self.credentials.load_pitchbook_session()
            if cookies:
                await page.add_cookies(cookies)
                await page.goto(self.base_url)
                try:
                    await page.wait_visible(_SEARCH)
                    await self._save_session(page)
                    return
                except WorkflowError:
                    pass

        credentials = self.credentials.load() if self.credentials else None
        if credentials:
            outcome = await self.authenticator.authenticate(page, credentials)
            if outcome.signed_in:
                await self._save_session(page)
                return
            raise AuthenticationRequired(outcome.message)

        status = await self.inspect_session(page)
        if await self._has_security_challenge(page):
            raise AuthenticationRequired(
                "Complete PitchBook's security verification in the open Chrome window, then retry."
            )
        if status.state == "signed_out":
            raise AuthenticationRequired(
                "The saved PitchBook session has expired; sign in once with "
                "collarai-pitchbook auth."
            )
        raise AuthenticationRequired(status.message or "PitchBook authentication is not ready")

    async def _save_session(self, page: StagehandPage) -> None:
        if self.credentials:
            self.credentials.save_pitchbook_session(await page.cookies())

    async def screen(self, page: StagehandPage, query: CompanyScreen) -> list[Company]:
        raise ConfigurationRequired(
            "PitchBook company screening needs a separate company-screener demonstration."
        )

    async def list_financing_transactions(
        self,
        page: StagehandPage,
        company_name: str,
        category: FinancingCategory,
    ) -> list[FinancingTransaction]:
        await self.ensure_authenticated(page)
        await self._open_company(page, company_name)
        await self._open_deals(page)
        await self._apply_category(page, category)
        return await self._extract_all_pages(page, company_name, category)

    async def _open_company(self, page: StagehandPage, company_name: str) -> None:
        if _COMPANY_PROFILE.search(await page.current_url()) and await page.exact_text_visible(
            "main", company_name
        ):
            return

        await page.act(
            selector="xpath=//*[@id='general-search-input']",
            method="fill",
            arguments=[company_name],
            intent="search PitchBook for the requested company",
        )
        matches: list[int] = []

        async def exact_result_ready() -> bool:
            nonlocal matches
            options = await page.texts('[data-testid="dropdown-result-card"]')
            matches = [
                index
                for index, text in enumerate(options)
                if self._matches_company_result(text, company_name)
            ]
            return bool(matches)

        try:
            await page.wait_until(
                exact_result_ready,
                f"PitchBook returned no exact company result for {company_name!r}",
            )
        except WorkflowError as error:
            raise WorkflowError(
                f"PitchBook returned no exact company result for {company_name!r}"
            ) from error
        if not matches:
            raise WorkflowError(f"PitchBook returned no exact company result for {company_name!r}")
        if len(matches) > 1:
            raise WorkflowError(
                f"PitchBook returned multiple exact company results for {company_name!r}"
            )
        result_selector = await page.mark(
            '[data-testid="dropdown-result-card"] [data-testid="dropdown-result-card-title"]',
            matches[0],
        )
        await page.act(
            selector=result_selector,
            method="click",
            arguments=[],
            intent="open the exact requested PitchBook company result",
        )
        await page.wait_for_url(_COMPANY_PROFILE)
        try:
            await page.wait_until(
                lambda: page.exact_text_visible("main", company_name),
                f"The opened PitchBook profile does not identify itself as {company_name!r}",
            )
        except WorkflowError as error:
            raise WorkflowError(
                f"The opened PitchBook profile does not identify itself as {company_name!r}"
            ) from error

    async def _open_deals(self, page: StagehandPage) -> None:
        selector = "xpath=//*[@role='tab' and normalize-space()='Deals']"
        selected = await page.evaluate(
            "document.evaluate(\"//*[@role='tab' and normalize-space()='Deals']\", document, null, "
            "XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue"
            "?.getAttribute('aria-selected')"
        )
        if selected != "true":
            await page.act(
                selector=selector,
                method="click",
                arguments=[],
                intent="open the PitchBook Deals tab",
            )
        await page.wait_for_url(_DEALS_PROFILE)

    async def _apply_category(
        self,
        page: StagehandPage,
        category_value: FinancingCategory,
    ) -> None:
        await page.wait_visible(_CATEGORY)
        if await page.value(_CATEGORY) != category_value.value:
            await page.act(
                selector="xpath=//*[@role='combobox' and @aria-label='category']",
                method="click",
                arguments=[],
                intent="open the PitchBook financing category menu",
            )
            await page.wait_until(
                lambda: self._option_is_ready(page, category_value.value),
                f"PitchBook did not show category {category_value.value!r}",
            )
            option = self._xpath_literal(category_value.value)
            await page.act(
                selector=f"xpath=//*[@role='option' and normalize-space()={option}]",
                method="click",
                arguments=[],
                intent=f"select the PitchBook {category_value.value} category",
            )
        await page.wait_until(
            lambda: self._value_is(page, _CATEGORY, category_value.value),
            f"PitchBook did not apply category {category_value.value!r}",
        )

        await page.wait_visible(_CURRENCY)
        if await page.value(_CURRENCY) != "USD":
            await page.act(
                selector="xpath=//*[@role='combobox' and @aria-label='currency']",
                method="click",
                arguments=[],
                intent="open the PitchBook currency menu",
            )
            await page.wait_until(
                lambda: self._option_is_ready(page, "USD"),
                "PitchBook did not show the USD currency option",
            )
            await page.act(
                selector="xpath=//*[@role='option' and normalize-space()='USD']",
                method="click",
                arguments=[],
                intent="select USD in PitchBook",
            )
        await page.wait_until(
            lambda: self._value_is(page, _CURRENCY, "USD"),
            "PitchBook did not apply USD",
        )
        await page.transaction_table()

    @staticmethod
    async def _value_is(page: StagehandPage, selector: str, value: str) -> bool:
        return await page.value(selector) == value

    @staticmethod
    async def _option_is_ready(page: StagehandPage, value: str) -> bool:
        return bool(
            await page.evaluate(
                "Array.from(document.querySelectorAll('[role=option]')).some(element => "
                "(element.innerText || element.textContent || '').trim() === "
                + json.dumps(value)
                + ")"
            )
        )

    async def _extract_all_pages(
        self,
        page: StagehandPage,
        company_name: str,
        category: FinancingCategory,
    ) -> list[FinancingTransaction]:
        transactions: list[FinancingTransaction] = []
        seen_signatures: set[str] = set()
        while True:
            page_transactions, signature = await self._extract_current_page(
                page,
                company_name,
                category,
            )
            if signature in seen_signatures:
                raise WorkflowError("PitchBook pagination repeated a transaction page")
            seen_signatures.add(signature)
            transactions.extend(page_transactions)

            next_button = await page.next_button()
            if next_button is None or next_button["disabled"]:
                break
            await page.act(
                selector=next_button["selector"],
                method="click",
                arguments=[],
                intent="open the next PitchBook transaction page",
            )
            await self._wait_for_new_page(page, signature, company_name, category)
        return transactions

    async def _extract_current_page(
        self,
        page: StagehandPage,
        company_name: str,
        category: FinancingCategory,
    ) -> tuple[list[FinancingTransaction], str]:
        table = await page.transaction_table()
        headers = [self._clean(value) for value in table["headers"]]
        required = {"#", "Deal Type", "Date", "Amount", "Raised to Date"}
        if not required.issubset(headers):
            missing = ", ".join(sorted(required.difference(headers)))
            raise WorkflowError(f"PitchBook transaction table is missing columns: {missing}")
        indexes = {header: headers.index(header) for header in required}

        current_url = await page.current_url()
        profile_match = _COMPANY_PROFILE.search(current_url)
        profile_id = profile_match.group(1) if profile_match else "unknown-profile"
        transactions: list[FinancingTransaction] = []
        row_signatures: list[str] = []
        for row_index, raw_cells in enumerate(table["rows"]):
            cells = [self._clean(value) for value in raw_cells]
            if len(cells) < len(headers):
                continue
            row_type = cells[indexes["Deal Type"]]
            if not row_type:
                continue
            deal_number = cells[indexes["#"]]
            date_text = cells[indexes["Date"]]
            row_signatures.append(f"{deal_number}:{row_type}:{date_text}")
            transactions.append(
                FinancingTransaction(
                    transaction_id=f"{profile_id}:{deal_number or date_text}:{row_index}",
                    company_name=company_name,
                    category=category,
                    deal_type=row_type,
                    announced_date=self._parse_date(date_text) if date_text else None,
                    amount_usd=self._parse_usd_amount(cells[indexes["Amount"]]),
                    raised_to_date_usd=self._parse_usd_amount(cells[indexes["Raised to Date"]]),
                    source_url=current_url,
                )
            )
        return transactions, "|".join(row_signatures) or "empty"

    async def _wait_for_new_page(
        self,
        page: StagehandPage,
        prior_signature: str,
        company_name: str,
        category: FinancingCategory,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + 15
        while asyncio.get_running_loop().time() < deadline:
            _, signature = await self._extract_current_page(page, company_name, category)
            if signature != prior_signature:
                return
            await asyncio.sleep(0.1)
        raise WorkflowError("PitchBook pagination did not load the next page")

    @staticmethod
    async def _has_security_challenge(page: StagehandPage) -> bool:
        return bool(
            _SECURITY_CHALLENGE.search(await page.title())
            or _SECURITY_CHALLENGE.search(await page.body_text())
        )

    @classmethod
    def _matches_company_result(cls, result_text: str, company_name: str) -> bool:
        result = cls._normalize(result_text)
        company = cls._normalize(company_name)
        if result == company or result.startswith(f"{company} ("):
            return True
        if not result.startswith(f"{company} "):
            return False
        remainder = result[len(company) :].strip()
        return remainder.startswith(
            (
                "public company",
                "private company",
                "acquired company",
                "out of business company",
            )
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()

    @staticmethod
    def _clean(value: str) -> str:
        return " ".join(value.split()).strip()

    @staticmethod
    def _xpath_literal(value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"

    @staticmethod
    def _parse_date(value: str):
        try:
            return datetime.strptime(value, "%d-%b-%Y").date()
        except ValueError as error:
            raise WorkflowError(
                f"PitchBook returned an unsupported transaction date: {value!r}"
            ) from error

    @staticmethod
    def _parse_usd_amount(value: str) -> int | None:
        if not value or value.casefold() in {"-", "—", "n/a", "undisclosed"}:
            return None
        match = _AMOUNT.fullmatch(value)
        if not match:
            raise WorkflowError(f"PitchBook returned an unsupported USD amount: {value!r}")
        try:
            number = Decimal(match.group("number").replace(",", ""))
            multiplier = _AMOUNT_MULTIPLIERS[(match.group("suffix") or "").upper()]
            return int((number * multiplier).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        except (InvalidOperation, KeyError) as error:
            raise WorkflowError(
                f"PitchBook returned an unsupported USD amount: {value!r}"
            ) from error
