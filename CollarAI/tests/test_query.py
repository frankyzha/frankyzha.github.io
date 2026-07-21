from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from collarai.models import (
    FinancingAnalysisResult,
    FinancingCategory,
    FinancingMetric,
    RunStatus,
)
from collarai.query import QueryRejected, QueryRouter, RejectionCode
from collarai.web_api import create_app


@pytest.mark.parametrize(
    ("query", "category", "metric", "deal_types"),
    [
        (
            "For Apple, what is the total sum of all recorded debt refinancing "
            "transaction amounts?",
            FinancingCategory.DEBT,
            FinancingMetric.SUM_AMOUNT,
            ["Debt Refinancing"],
        ),
        (
            "What is Nvidia's total debt raised to date?",
            FinancingCategory.DEBT,
            FinancingMetric.LATEST_RAISED_TO_DATE,
            [],
        ),
        (
            "What's Nvidia's average equity financing transaction amount?",
            FinancingCategory.EQUITY,
            FinancingMetric.AVERAGE_AMOUNT,
            [],
        ),
        (
            "What is Nvidia's IPO amount?",
            FinancingCategory.EQUITY,
            FinancingMetric.SUM_AMOUNT,
            ["IPO"],
        ),
    ],
)
def test_query_router_builds_typed_requests(
    query: str,
    category: FinancingCategory,
    metric: FinancingMetric,
    deal_types: list[str],
) -> None:
    request = QueryRouter().parse(query).request
    assert request.company_name in {"Apple", "Nvidia"}
    assert request.category is category
    assert request.metric is metric
    assert request.deal_types == deal_types


def test_query_router_rejects_irrelevant_incomplete_and_unsupported_queries() -> None:
    router = QueryRouter()
    cases = [
        ("I want to call a cute femboy", RejectionCode.IRRELEVANT),
        ("What is Nvidia's average?", RejectionCode.INCOMPLETE),
        ("What is the average debt raised to date?", RejectionCode.INCOMPLETE),
        ("What is Nvidia's debt maturity schedule?", RejectionCode.UNSUPPORTED),
    ]
    for query, code in cases:
        with pytest.raises(QueryRejected) as raised:
            router.parse(query)
        assert raised.value.code is code


class FakeBrowserService:
    async def analyze_financing_transactions(self, request):
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


@pytest.mark.asyncio
async def test_web_api_returns_markdown_and_structured_interpretation() -> None:
    app = create_app(service_factory=FakeBrowserService, access_token=None)
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
    app = create_app(service_factory=FakeBrowserService, access_token=None)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/query",
                json={"query": "Tell me a joke."},
            )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "irrelevant"


@pytest.mark.asyncio
async def test_web_api_requires_the_configured_bearer_token() -> None:
    app = create_app(service_factory=FakeBrowserService, access_token="private-demo-key")
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
