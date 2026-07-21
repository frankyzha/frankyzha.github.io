from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

from collarai.adapters import AdapterRegistry, PitchBookAdapter, SiteAdapter, ToyMarketAdapter
from collarai.analytics import aggregate_financing
from collarai.browser import BrowserSessionManager
from collarai.config import Settings
from collarai.credentials import CredentialStore
from collarai.errors import AuthenticationRequired, ConfigurationRequired
from collarai.evidence import EvidenceStore
from collarai.models import (
    BrowserSessionStatus,
    CompanyScreen,
    FinancingAnalysisRequest,
    FinancingAnalysisResult,
    RunResult,
    RunStatus,
    ScreenResult,
)
from collarai.policy import BrowserPolicy
from collarai.stagehand_browser import StagehandPage


class BrowserService:
    def __init__(
        self,
        sessions: BrowserSessionManager,
        adapters: AdapterRegistry,
        evidence: EvidenceStore,
        policy: BrowserPolicy,
    ) -> None:
        self.sessions = sessions
        self.adapters = adapters
        self.evidence = evidence
        self.policy = policy

    async def screen_companies(self, query: CompanyScreen) -> ScreenResult:
        self.policy.check_screen(query)
        result = ScreenResult(
            run_id=str(uuid4()),
            status=RunStatus.FAILED,
            platform=query.platform,
            applied_filters=query,
        )

        async def work(adapter: SiteAdapter, page: StagehandPage) -> None:
            companies = await adapter.screen(page, query)
            self.policy.check_companies(query, companies)
            result.companies = companies
            result.result_count = len(companies)
            result.status = RunStatus.COMPLETE

        return cast(ScreenResult, await self._execute(query.platform, result, work))

    async def analyze_financing_transactions(
        self,
        request: FinancingAnalysisRequest,
    ) -> FinancingAnalysisResult:
        result = FinancingAnalysisResult(
            run_id=str(uuid4()),
            status=RunStatus.FAILED,
            platform=request.platform,
            request=request,
            is_synthetic=request.platform == "toy",
        )

        async def work(adapter: SiteAdapter, page: StagehandPage) -> None:
            transactions = await adapter.list_financing_transactions(
                page,
                request.company_name,
                request.category,
            )
            self.policy.check_financing_transactions(request, transactions)
            requested_types = {value.casefold() for value in request.deal_types}
            if requested_types:
                transactions = [
                    item for item in transactions if item.deal_type.casefold() in requested_types
                ]
            aggregation = aggregate_financing(request.metric, transactions)
            result.transactions = transactions
            result.matched_transaction_count = len(transactions)
            result.disclosed_value_count = aggregation.disclosed_count
            result.missing_value_count = aggregation.missing_count
            result.value_usd = aggregation.value_usd
            result.exact_numerator_usd = aggregation.numerator_usd
            result.exact_denominator = aggregation.denominator
            result.value_is_rounded = aggregation.is_rounded
            result.is_exhaustive = True
            result.status = RunStatus.COMPLETE

        return cast(
            FinancingAnalysisResult,
            await self._execute(request.platform, result, work),
        )

    async def get_session_status(self, platform: str) -> BrowserSessionStatus:
        adapter = self.adapters.get(platform)
        if not self.sessions.has_session(platform):
            return BrowserSessionStatus(platform=platform, state="not_started")
        async with self.sessions.acquire(platform) as session:
            return await adapter.inspect_session(session.page)

    def get_run(self, run_id: str) -> RunResult:
        return self.evidence.load_result(run_id)

    async def close(self) -> None:
        await self.sessions.close()

    async def _execute(
        self,
        platform: str,
        result: RunResult,
        work: Callable[[SiteAdapter, StagehandPage], Awaitable[None]],
    ) -> RunResult:
        adapter = self.adapters.get(platform)
        self.policy.check_url(adapter.base_url)
        run_dir = self.evidence.create_run(result.run_id)
        result.evidence_path = str(run_dir)
        try:
            async with self.sessions.acquire(platform) as session:
                session.page.begin_run()
                try:
                    await adapter.ensure_authenticated(session.page)
                    await work(adapter, session.page)
                except AuthenticationRequired as error:
                    result.status = RunStatus.NEEDS_HUMAN
                    result.message = str(error)
                except ConfigurationRequired as error:
                    result.status = RunStatus.NEEDS_CONFIGURATION
                    result.message = str(error)
                except Exception as error:  # Preserve evidence and return a typed failure.
                    result.message = f"{type(error).__name__}: {str(error)[:500]}"
                finally:
                    if result.status is not RunStatus.NEEDS_HUMAN:
                        await self._capture(session.page, run_dir / "final.png")
                    self._save_stagehand_log(session.page, run_dir / "stagehand.json")
        except Exception as error:
            result.message = f"{type(error).__name__}: {str(error)[:500]}"
        self.evidence.save_result(result)
        return result

    @staticmethod
    async def _capture(page: StagehandPage, path: Path) -> None:
        try:
            await page.screenshot(path)
        except Exception:
            return

    @staticmethod
    def _save_stagehand_log(page: StagehandPage, path: Path) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "actions": page.action_log}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
        path.chmod(0o600)


def build_service(
    settings: Settings | None = None,
) -> BrowserService:
    settings = settings or Settings.from_env()
    sessions = BrowserSessionManager(settings)
    adapters = AdapterRegistry(
        [
            ToyMarketAdapter(
                settings.toy_base_url,
                settings.toy_username,
                settings.toy_password,
            ),
            PitchBookAdapter(
                settings.pitchbook_url,
                credentials=CredentialStore(),
            ),
        ]
    )
    hosts = {
        host
        for url in (settings.toy_base_url, settings.pitchbook_url)
        if (host := urlparse(url).hostname)
    }
    return BrowserService(
        sessions=sessions,
        adapters=adapters,
        evidence=EvidenceStore(settings.evidence_dir),
        policy=BrowserPolicy(hosts),
    )
