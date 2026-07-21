from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from collarai.models import FinancingMetric, FinancingTransaction


@dataclass(frozen=True, slots=True)
class FinancingAggregation:
    value_usd: int | None
    numerator_usd: int
    denominator: int
    disclosed_count: int
    missing_count: int
    is_rounded: bool


def aggregate_financing(
    metric: FinancingMetric,
    transactions: list[FinancingTransaction],
) -> FinancingAggregation:
    field = "amount_usd" if metric in _AMOUNT_METRICS else "raised_to_date_usd"
    values = [getattr(item, field) for item in transactions]
    disclosed = [value for value in values if value is not None]
    missing = len(values) - len(disclosed)
    if not disclosed:
        if metric is FinancingMetric.SUM_AMOUNT:
            return FinancingAggregation(0, 0, 1, 0, missing, False)
        return FinancingAggregation(None, 0, 0, 0, missing, False)

    if metric is FinancingMetric.SUM_AMOUNT:
        numerator, denominator = sum(disclosed), 1
    elif metric in {FinancingMetric.AVERAGE_AMOUNT, FinancingMetric.AVERAGE_RAISED_TO_DATE}:
        numerator, denominator = sum(disclosed), len(disclosed)
    elif metric is FinancingMetric.MIN_RAISED_TO_DATE:
        numerator, denominator = min(disclosed), 1
    elif metric is FinancingMetric.MAX_RAISED_TO_DATE:
        numerator, denominator = max(disclosed), 1
    elif metric is FinancingMetric.LATEST_RAISED_TO_DATE:
        dated = [
            item
            for item in transactions
            if item.announced_date is not None and item.raised_to_date_usd is not None
        ]
        selected = max(dated, key=lambda item: item.announced_date) if dated else None
        value = selected.raised_to_date_usd if selected else disclosed[0]
        numerator, denominator = value, 1
    else:  # Enum exhaustiveness guard.
        raise ValueError(f"Unsupported financing metric: {metric}")

    value = int(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )
    return FinancingAggregation(
        value_usd=value,
        numerator_usd=numerator,
        denominator=denominator,
        disclosed_count=len(disclosed),
        missing_count=missing,
        is_rounded=numerator % denominator != 0,
    )


_AMOUNT_METRICS = {
    FinancingMetric.SUM_AMOUNT,
    FinancingMetric.AVERAGE_AMOUNT,
}
