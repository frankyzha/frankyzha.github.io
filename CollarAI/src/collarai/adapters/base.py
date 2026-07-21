from __future__ import annotations

from abc import ABC, abstractmethod

from collarai.errors import ConfigurationRequired
from collarai.models import (
    BrowserSessionStatus,
    Company,
    CompanyScreen,
    FinancingCategory,
    FinancingTransaction,
)
from collarai.stagehand_browser import StagehandPage


class SiteAdapter(ABC):
    platform: str
    base_url: str

    @abstractmethod
    async def inspect_session(self, page: StagehandPage) -> BrowserSessionStatus: ...

    @abstractmethod
    async def ensure_authenticated(self, page: StagehandPage) -> None: ...

    @abstractmethod
    async def screen(self, page: StagehandPage, query: CompanyScreen) -> list[Company]: ...

    async def list_financing_transactions(
        self,
        page: StagehandPage,
        company_name: str,
        category: FinancingCategory,
    ) -> list[FinancingTransaction]:
        raise ConfigurationRequired(
            f"{self.platform} does not implement generalized financing transactions"
        )

    async def click(self, page: StagehandPage, selector: str, intent: str) -> None:
        await page.act(
            selector=selector,
            method="click",
            arguments=[],
            intent=intent,
        )


class AdapterRegistry:
    def __init__(self, adapters: list[SiteAdapter]) -> None:
        self._adapters = {adapter.platform: adapter for adapter in adapters}

    def get(self, platform: str) -> SiteAdapter:
        try:
            return self._adapters[platform]
        except KeyError as error:
            raise ValueError(f"Unsupported platform: {platform}") from error
