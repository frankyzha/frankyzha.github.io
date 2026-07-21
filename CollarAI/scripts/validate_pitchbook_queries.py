"""Run the ten user-defined PitchBook questions through the generic browser tools."""

from __future__ import annotations

import asyncio
import json
from time import perf_counter

from collarai.models import (
    FinancingAnalysisRequest,
    FinancingCategory,
    FinancingMetric,
)
from collarai.service import build_service


def requests() -> list[tuple[str, FinancingAnalysisRequest]]:
    debt = FinancingCategory.DEBT
    equity = FinancingCategory.EQUITY
    return [
        (
            "Apple debt-refinancing total",
            FinancingAnalysisRequest(
                company_name="Apple",
                category=debt,
                metric=FinancingMetric.SUM_AMOUNT,
                deal_types=["Debt Refinancing"],
            ),
        ),
        (
            "Nvidia latest debt raised-to-date",
            FinancingAnalysisRequest(
                company_name="Nvidia", category=debt, metric=FinancingMetric.LATEST_RAISED_TO_DATE
            ),
        ),
        (
            "Apple latest debt raised-to-date",
            FinancingAnalysisRequest(
                company_name="Apple", category=debt, metric=FinancingMetric.LATEST_RAISED_TO_DATE
            ),
        ),
        (
            "Nvidia minimum debt raised-to-date",
            FinancingAnalysisRequest(
                company_name="Nvidia", category=debt, metric=FinancingMetric.MIN_RAISED_TO_DATE
            ),
        ),
        (
            "Nvidia maximum debt raised-to-date",
            FinancingAnalysisRequest(
                company_name="Nvidia", category=debt, metric=FinancingMetric.MAX_RAISED_TO_DATE
            ),
        ),
        (
            "Nvidia average debt raised-to-date",
            FinancingAnalysisRequest(
                company_name="Nvidia", category=debt, metric=FinancingMetric.AVERAGE_RAISED_TO_DATE
            ),
        ),
        (
            "Nvidia average debt-refinancing amount",
            FinancingAnalysisRequest(
                company_name="Nvidia",
                category=debt,
                metric=FinancingMetric.AVERAGE_AMOUNT,
                deal_types=["Debt Refinancing"],
            ),
        ),
        (
            "Nvidia total equity-financing amount",
            FinancingAnalysisRequest(
                company_name="Nvidia", category=equity, metric=FinancingMetric.SUM_AMOUNT
            ),
        ),
        (
            "Nvidia average equity-financing amount",
            FinancingAnalysisRequest(
                company_name="Nvidia", category=equity, metric=FinancingMetric.AVERAGE_AMOUNT
            ),
        ),
        (
            "Nvidia IPO amount",
            FinancingAnalysisRequest(
                company_name="Nvidia",
                category=equity,
                metric=FinancingMetric.SUM_AMOUNT,
                deal_types=["IPO"],
            ),
        ),
    ]


async def main() -> None:
    service = build_service()
    total_started = perf_counter()
    try:
        for index, (label, request) in enumerate(requests(), 1):
            started = perf_counter()
            result = await service.analyze_financing_transactions(request)
            print(
                json.dumps(
                    {
                        "query": index,
                        "label": label,
                        "status": result.status.value,
                        "value_usd": result.value_usd,
                        "matched": result.matched_transaction_count,
                        "disclosed": result.disclosed_value_count,
                        "missing": result.missing_value_count,
                        "seconds": round(perf_counter() - started, 3),
                        "run_id": result.run_id,
                        "message": result.message,
                    }
                ),
                flush=True,
            )
    finally:
        await service.close()
    print(json.dumps({"total_seconds": round(perf_counter() - total_started, 3)}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
