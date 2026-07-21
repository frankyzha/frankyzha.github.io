from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from collarai.credentials import StoredCredentials
from collarai.errors import AuthenticationRequired, WorkflowError
from collarai.stagehand_browser import StagehandPage

_MORNINGSTAR_LOGIN_HOST = "login-prod.morningstar.com"
_DUKE_LOGIN_HOST = "shib.oit.duke.edu"
_PITCHBOOK_HOST = "my.pitchbook.com"
_SECURITY_CHALLENGE = re.compile(
    r"just a moment|performing security verification|verify you are human",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class AuthenticationOutcome:
    signed_in: bool
    message: str


class PitchBookAuthenticator:
    """Perform a narrowly allowlisted SAML login through Stagehand v3."""

    async def authenticate(
        self,
        page: StagehandPage,
        credentials: StoredCredentials,
    ) -> AuthenticationOutcome:
        if await self._is_pitchbook_app(page):
            return AuthenticationOutcome(True, "PitchBook is already signed in.")
        if await self._has_security_challenge(page):
            return AuthenticationOutcome(
                False,
                "Complete PitchBook's security verification in the open Chrome window.",
            )

        host = urlparse(await page.current_url()).hostname
        if host == _PITCHBOOK_HOST:
            if await self._is_pitchbook_app(page):
                return AuthenticationOutcome(True, "PitchBook is signed in.")
            host = urlparse(await page.current_url()).hostname

        if host == _MORNINGSTAR_LOGIN_HOST:
            await self._start_sso(page, credentials.duke_email)
            host = await self._wait_for_host_change(page, _MORNINGSTAR_LOGIN_HOST)

        if host == _DUKE_LOGIN_HOST:
            await self._submit_duke_login(page, credentials)

        if await self._wait_for_pitchbook(page):
            return AuthenticationOutcome(True, "PitchBook SSO completed.")

        host = urlparse(await page.current_url()).hostname or "unknown host"
        return AuthenticationOutcome(
            False,
            f"Authentication needs attention in Chrome at {host}; credentials were not retried.",
        )

    async def _start_sso(self, page: StagehandPage, duke_email: str) -> None:
        if not await page.visible("#email"):
            await page.act(
                selector="xpath=//button[normalize-space()='Sign in with SSO']",
                method="click",
                arguments=[],
                intent="open PitchBook SSO",
                recover=False,
            )
        await page.wait_visible("#email")
        await page.act(
            selector="xpath=//*[@id='email']",
            method="fill",
            arguments=[duke_email],
            intent="fill the PitchBook SSO email field",
            recover=False,
        )
        await page.act(
            selector="xpath=//button[normalize-space()='Continue']",
            method="click",
            arguments=[],
            intent="continue to Duke SSO",
            recover=False,
        )

    async def _submit_duke_login(
        self,
        page: StagehandPage,
        credentials: StoredCredentials,
    ) -> None:
        if urlparse(await page.current_url()).hostname != _DUKE_LOGIN_HOST:
            raise AuthenticationRequired(
                "Refusing to enter a Duke password outside shib.oit.duke.edu"
            )

        username = await self._first_visible(
            page,
            (
                'input[name="j_username"]',
                'input[name="username"]',
                "#j_username",
                "#username",
                'input[autocomplete="username"]',
            ),
        )
        password = await self._first_visible(
            page,
            (
                'input[name="j_password"]',
                'input[name="password"]',
                "#j_password",
                "#password",
                'input[autocomplete="current-password"]',
            ),
        )
        if username is None or password is None:
            return

        await page.act(
            selector=f"xpath=//{username}",
            method="fill",
            arguments=[credentials.netid],
            intent="fill the Duke NetID field",
            recover=False,
        )
        await page.act(
            selector=f"xpath=//{password}",
            method="fill",
            arguments=[credentials.password],
            intent="fill the Duke password field",
            recover=False,
            sensitive=True,
        )
        selector = (
            "xpath=(//button[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign in') "
            "or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'log in') or normalize-space()='Continue']"
            " | //input[@type='submit'])[1]"
        )
        await page.act(
            selector=selector,
            method="click",
            arguments=[],
            intent="submit Duke SSO",
            recover=False,
        )

    @staticmethod
    async def _first_visible(page: StagehandPage, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            if await page.visible(selector):
                if selector.startswith("#"):
                    return f"*[@id='{selector[1:]}']"
                if selector.startswith("input"):
                    return selector
        return None

    @staticmethod
    async def _wait_for_host_change(page: StagehandPage, prior_host: str) -> str | None:
        deadline = asyncio.get_running_loop().time() + 30
        while asyncio.get_running_loop().time() < deadline:
            host = urlparse(await page.current_url()).hostname
            if host != prior_host:
                return host
            await asyncio.sleep(0.1)
        raise WorkflowError("PitchBook did not redirect to Duke SSO")

    async def _wait_for_pitchbook(self, page: StagehandPage) -> bool:
        deadline = asyncio.get_running_loop().time() + 60
        while asyncio.get_running_loop().time() < deadline:
            if await self._is_pitchbook_app(page):
                return True
            if await self._has_security_challenge(page):
                return False
            await asyncio.sleep(0.25)
        return False

    @staticmethod
    async def _is_pitchbook_app(page: StagehandPage) -> bool:
        return urlparse(
            await page.current_url()
        ).hostname == _PITCHBOOK_HOST and await page.visible("#general-search-input")

    @staticmethod
    async def _has_security_challenge(page: StagehandPage) -> bool:
        return bool(
            _SECURITY_CHALLENGE.search(await page.title())
            or _SECURITY_CHALLENGE.search(await page.body_text())
        )
