from __future__ import annotations

from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from collarai.inference import InferenceUnavailable, ToolCall
from collarai.models import (
    FinancingAnalysisResult,
    FinancingCategory,
    FinancingMetric,
    RunStatus,
)
from collarai.query import QueryRejected, QueryRouter, RejectionCode
from collarai.web_api import create_app


@dataclass
class StubToolClient:
    call: ToolCall

    async def call_tool(self, **_) -> ToolCall:
        return self.call


def router_call(name: str, **arguments) -> QueryRouter:
    return QueryRouter(StubToolClient(ToolCall(name=name, arguments=arguments)))


@pytest.mark.parametrize(
    ("tool_name", "category", "metric", "deal_types"),
    [
        (
            "total_transaction_amount",
            FinancingCategory.DEBT,
            FinancingMetric.SUM_AMOUNT,
            ["Debt Refinancing"],
        ),
        (
            "average_transaction_amount",
            FinancingCategory.EQUITY,
            FinancingMetric.AVERAGE_AMOUNT,
            [],
        ),
        (
            "latest_raised_to_date",
            FinancingCategory.DEBT,
            FinancingMetric.LATEST_RAISED_TO_DATE,
            [],
        ),
        (
            "minimum_raised_to_date",
            FinancingCategory.DEBT,
            FinancingMetric.MIN_RAISED_TO_DATE,
            [],
        ),
        (
            "maximum_raised_to_date",
            FinancingCategory.DEBT,
            FinancingMetric.MAX_RAISED_TO_DATE,
            [],
        ),
        (
            "average_raised_to_date",
            FinancingCategory.DEBT,
            FinancingMetric.AVERAGE_RAISED_TO_DATE,
            [],
        ),
    ],
)
@pytest.mark.asyncio
async def test_router_validates_model_tool_calls(
    tool_name: str,
    category: FinancingCategory,
    metric: FinancingMetric,
    deal_types: list[str],
) -> None:
    arguments = {"company_name": "Nvidia", "category": category.value}
    if tool_name in {"total_transaction_amount", "average_transaction_amount"}:
        arguments["deal_types"] = deal_types
    routed = await router_call(tool_name, **arguments).parse("A semantically valid query")
    assert routed.request.company_name == "Nvidia"
    assert routed.request.category is category
    assert routed.request.metric is metric
    assert routed.request.deal_types == deal_types


@pytest.mark.asyncio
async def test_router_supports_grants_without_keyword_rules() -> None:
    routed = await router_call(
        "total_transaction_amount",
        company_name="OpenAI",
        category="All Deals",
        deal_types=["Grant"],
    ).parse("What is OpenAI total grant?")
    assert routed.request.company_name == "OpenAI"
    assert routed.request.category is FinancingCategory.ALL
    assert routed.request.metric is FinancingMetric.SUM_AMOUNT
    assert routed.request.deal_types == ["Grant"]


@pytest.mark.parametrize(
    ("call", "code"),
    [
        (ToolCall("reject_irrelevant", {}), RejectionCode.IRRELEVANT),
        (
            ToolCall("request_clarification", {"missing": "calculation"}),
            RejectionCode.INCOMPLETE,
        ),
        (ToolCall("reject_unsupported", {}), RejectionCode.UNSUPPORTED),
    ],
)
@pytest.mark.asyncio
async def test_router_uses_explicit_rejection_capabilities(
    call: ToolCall, code: RejectionCode
) -> None:
    with pytest.raises(QueryRejected) as raised:
        await QueryRouter(StubToolClient(call)).parse("Any natural-language wording")
    assert raised.value.code is code


@pytest.mark.asyncio
async def test_router_fails_closed_on_invalid_model_arguments() -> None:
    router = router_call(
        "total_transaction_amount",
        company_name="OpenAI",
        category="Imaginary category",
        deal_types=["Grant"],
    )
    with pytest.raises(InferenceUnavailable):
        await router.parse("What is OpenAI total grant?")


class FakeBrowserService:
    calls = 0

    async def analyze_financing_transactions(self, request):
        self.calls += 1
        return FinancingAnalysisResult(
            run_id="11111111-1111-1111-1111-111111111111",
            status=RunStatus.COMPLETE,
            platform="pitchbook",
            request=request,
            matched_transaction_count=1,
            disclosed_value_count=1,
            value_usd=42_000_000,
            exact_numerator_usd=42_000_000,
            exact_denominator=1,
            is_exhaustive=True,
        )

    async def close(self) -> None:
        return None


class FailedBrowserService(FakeBrowserService):
    async def analyze_financing_transactions(self, request):
        return FinancingAnalysisResult(
            run_id="22222222-2222-2222-2222-222222222222",
            status=RunStatus.FAILED,
            platform="pitchbook",
            request=request,
            message="ConnectionClosedError: private internal detail",
        )


def ipo_router() -> QueryRouter:
    return router_call(
        "total_transaction_amount",
        company_name="Nvidia",
        category="Equity Financing",
        deal_types=["IPO"],
    )


@pytest.mark.asyncio
async def test_web_api_returns_markdown_and_structured_interpretation() -> None:
    app = create_app(
        service_factory=FakeBrowserService,
        access_token=None,
        router=ipo_router(),
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "What is Nvidia's IPO amount?"},
            )
    assert response.status_code == 200
    payload = response.json()
    assert payload["value_usd"] == 42_000_000
    assert payload["interpretation"]["deal_types"] == ["IPO"]
    assert "| Measure | Result |" in payload["markdown"]


@pytest.mark.asyncio
async def test_web_api_rejects_bad_queries_before_browser_work() -> None:
    service = FakeBrowserService()
    app = create_app(
        service_factory=lambda: service,
        access_token=None,
        router=QueryRouter(StubToolClient(ToolCall("reject_irrelevant", {}))),
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/query", json={"query": "Tell me a joke."})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "irrelevant"
    assert service.calls == 0


@pytest.mark.asyncio
async def test_web_api_requires_the_configured_bearer_token() -> None:
    app = create_app(
        service_factory=FakeBrowserService,
        access_token="private-demo-key",
        router=ipo_router(),
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            denied = await client.post(
                "/api/query",
                json={"query": "What is Nvidia's IPO amount?"},
            )
            allowed = await client.post(
                "/api/query",
                json={"query": "What is Nvidia's IPO amount?"},
                headers={"Authorization": "Bearer private-demo-key"},
            )

    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_web_api_hides_internal_browser_failures() -> None:
    app = create_app(
        service_factory=FailedBrowserService,
        access_token=None,
        router=ipo_router(),
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "What is Nvidia's IPO amount?"},
            )

    assert response.status_code == 502
    assert response.json()["error"]["message"] == (
        "The browser session could not complete the query. Please retry."
    )
