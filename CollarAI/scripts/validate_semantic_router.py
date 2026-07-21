from __future__ import annotations

import asyncio
from dataclasses import dataclass

from collarai.models import FinancingCategory, FinancingMetric
from collarai.query import QueryRejected, QueryRouter, RejectionCode


@dataclass(frozen=True, slots=True)
class ExpectedRoute:
    query: str
    company: str
    category: FinancingCategory
    metric: FinancingMetric
    deal_types: tuple[str, ...] = ()


CASES = (
    ExpectedRoute(
        "For Apple, what is the total sum of all recorded debt refinancing transaction amounts?",
        "Apple",
        FinancingCategory.DEBT,
        FinancingMetric.SUM_AMOUNT,
        ("Debt Refinancing",),
    ),
    ExpectedRoute(
        "What is Nvidia's total debt raised to date?",
        "Nvidia",
        FinancingCategory.DEBT,
        FinancingMetric.LATEST_RAISED_TO_DATE,
    ),
    ExpectedRoute(
        "What's Apple's total debt raised to date?",
        "Apple",
        FinancingCategory.DEBT,
        FinancingMetric.LATEST_RAISED_TO_DATE,
    ),
    ExpectedRoute(
        "What is Nvidia's minimum debt raised to date?",
        "Nvidia",
        FinancingCategory.DEBT,
        FinancingMetric.MIN_RAISED_TO_DATE,
    ),
    ExpectedRoute(
        "What is Nvidia's maximum debt raised to date?",
        "Nvidia",
        FinancingCategory.DEBT,
        FinancingMetric.MAX_RAISED_TO_DATE,
    ),
    ExpectedRoute(
        "What is Nvidia's average debt raised to date?",
        "Nvidia",
        FinancingCategory.DEBT,
        FinancingMetric.AVERAGE_RAISED_TO_DATE,
    ),
    ExpectedRoute(
        "What is Nvidia's average recorded debt refinancing transaction amounts?",
        "Nvidia",
        FinancingCategory.DEBT,
        FinancingMetric.AVERAGE_AMOUNT,
        ("Debt Refinancing",),
    ),
    ExpectedRoute(
        "What is Nvidia's total equity financing transaction amounts?",
        "Nvidia",
        FinancingCategory.EQUITY,
        FinancingMetric.SUM_AMOUNT,
    ),
    ExpectedRoute(
        "What is Nvidia's average equity financing transaction amounts?",
        "Nvidia",
        FinancingCategory.EQUITY,
        FinancingMetric.AVERAGE_AMOUNT,
    ),
    ExpectedRoute(
        "What is Nvidia's IPO amount?",
        "Nvidia",
        FinancingCategory.EQUITY,
        FinancingMetric.SUM_AMOUNT,
        ("IPO",),
    ),
    ExpectedRoute(
        "What is OpenAI total grant?",
        "OpenAI",
        FinancingCategory.ALL,
        FinancingMetric.SUM_AMOUNT,
        ("Grant",),
    ),
)


async def main() -> None:
    router = QueryRouter()
    failures: list[str] = []
    for index, case in enumerate(CASES, 1):
        request = (await router.parse(case.query)).request
        actual = (
            request.company_name,
            request.category,
            request.metric,
            tuple(request.deal_types),
        )
        expected = (case.company, case.category, case.metric, case.deal_types)
        status = "ok" if actual == expected else "FAIL"
        print(f"{index:>2}. {status}  {case.query}")
        if actual != expected:
            failures.append(f"{case.query!r}: expected {expected!r}, got {actual!r}")

    rejection_cases = (
        ("Tell me a joke.", RejectionCode.IRRELEVANT),
        ("What is Nvidia's financing?", RejectionCode.INCOMPLETE),
    )
    for query, expected_code in rejection_cases:
        try:
            await router.parse(query)
        except QueryRejected as error:
            if error.code is expected_code:
                print(f"ok  rejected {query!r} as {error.code.value}")
            else:
                failures.append(
                    f"{query!r}: expected rejection {expected_code.value}, got {error.code.value}"
                )
        else:
            failures.append(f"{query!r}: expected rejection {expected_code.value}")

    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    asyncio.run(main())
