from __future__ import annotations

from collarai.analytics import aggregate_financing
from collarai.models import FinancingCategory, FinancingMetric, FinancingTransaction


def transaction(
    identifier: str,
    date: str | None,
    amount: int | None,
    raised: int | None,
) -> FinancingTransaction:
    return FinancingTransaction(
        transaction_id=identifier,
        company_name="Example",
        category=FinancingCategory.DEBT,
        deal_type="Debt Refinancing",
        announced_date=date,
        amount_usd=amount,
        raised_to_date_usd=raised,
        source_url="https://example.com",
    )


def test_financing_aggregations_have_explicit_missing_and_rounding_semantics() -> None:
    rows = [
        transaction("new", "2024-01-01", 10, 30),
        transaction("old", "2020-01-01", 5, 20),
        transaction("missing", None, None, None),
    ]

    total = aggregate_financing(FinancingMetric.SUM_AMOUNT, rows)
    assert total.value_usd == 15
    assert total.disclosed_count == 2
    assert total.missing_count == 1

    average = aggregate_financing(FinancingMetric.AVERAGE_AMOUNT, rows)
    assert average.value_usd == 8
    assert average.numerator_usd == 15
    assert average.denominator == 2
    assert average.is_rounded is True

    latest = aggregate_financing(FinancingMetric.LATEST_RAISED_TO_DATE, rows)
    assert latest.value_usd == 30
    assert aggregate_financing(FinancingMetric.MIN_RAISED_TO_DATE, rows).value_usd == 20
    assert aggregate_financing(FinancingMetric.MAX_RAISED_TO_DATE, rows).value_usd == 30
    assert aggregate_financing(FinancingMetric.AVERAGE_RAISED_TO_DATE, rows).value_usd == 25


def test_empty_sum_is_zero_but_empty_average_is_undefined() -> None:
    assert aggregate_financing(FinancingMetric.SUM_AMOUNT, []).value_usd == 0
    assert aggregate_financing(FinancingMetric.AVERAGE_AMOUNT, []).value_usd is None
