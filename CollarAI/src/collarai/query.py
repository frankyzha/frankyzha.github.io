from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from collarai.models import (
    FinancingAnalysisRequest,
    FinancingAnalysisResult,
    FinancingCategory,
    FinancingMetric,
)

_SPACE = re.compile(r"\s+")
_DOMAIN = re.compile(r"\b(debt|equity|financ(?:e|ing)|refinanc\w*|ipo|raised)\b", re.I)
_AGGREGATE = re.compile(r"\b(total|sum|average|mean|minimum|min|max|maximum|latest)\b", re.I)
_AMOUNT = re.compile(r"\b(amount|amounts|size|raised|raise)\b", re.I)
_AVERAGE = re.compile(r"\b(average|mean)\b", re.I)
_MINIMUM = re.compile(r"\b(minimum|min|smallest|least)\b", re.I)
_MAXIMUM = re.compile(r"\b(maximum|max|largest|highest)\b", re.I)
_TOTAL = re.compile(r"\b(total|sum|combined|altogether)\b", re.I)
_LATEST = re.compile(r"\b(latest|current|to date)\b", re.I)
_COMPANY = r"[A-Za-z0-9][A-Za-z0-9&.()\- ]{0,79}?"
_COMPANY_PATTERNS = (
    re.compile(rf"\bfor\s+(?P<company>{_COMPANY})\s*,", re.I),
    re.compile(rf"\bwhat(?:'s|’s|\s+is|\s+was|\s+are)\s+(?P<company>{_COMPANY})['’]s\s+", re.I),
    re.compile(rf"^(?P<company>{_COMPANY})['’]s\s+", re.I),
    re.compile(
        rf"^(?:what\s+is|what's|what’s|calculate|find|show)\s+"
        rf"(?P<company>{_COMPANY})\s+(?:total|average|minimum|min|max|maximum|ipo|debt|equity)",
        re.I,
    ),
    re.compile(rf"\bhow\s+much\s+did\s+(?P<company>{_COMPANY})\s+raise\b", re.I),
)


class RejectionCode(str, Enum):
    IRRELEVANT = "irrelevant"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "unsupported"


class QueryRejected(ValueError):
    def __init__(self, code: RejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class RoutedQuery:
    request: FinancingAnalysisRequest


class QueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=500)


class QueryInterpretation(BaseModel):
    company_name: str
    category: FinancingCategory
    metric: FinancingMetric
    deal_types: list[str]


class QueryAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    interpretation: QueryInterpretation
    markdown: str
    value_usd: int | None
    matched_transaction_count: int
    disclosed_value_count: int
    missing_value_count: int
    run_id: str
    elapsed_ms: int = Field(ge=0)


class QueryRouter:
    """Translate a narrow natural-language surface into validated browser requests."""

    def parse(self, raw_query: str) -> RoutedQuery:
        query = _SPACE.sub(" ", raw_query).strip()
        company = self._company(query)
        if not _DOMAIN.search(query):
            if company and _AGGREGATE.search(query):
                raise QueryRejected(
                    RejectionCode.INCOMPLETE,
                    "Specify debt raised to date, debt refinancing, equity financing, or IPO.",
                )
            raise QueryRejected(
                RejectionCode.IRRELEVANT,
                "This demo only answers company financing questions supported by "
                "the PitchBook workflow.",
            )
        if company is None:
            raise QueryRejected(
                RejectionCode.INCOMPLETE,
                "Name one company, for example: “What is Nvidia's IPO amount?”",
            )

        lowered = query.casefold()
        if "ipo" in lowered:
            if not (_AMOUNT.search(query) or _TOTAL.search(query)):
                raise self._unsupported()
            return self._route(
                company,
                FinancingCategory.EQUITY,
                FinancingMetric.SUM_AMOUNT,
                ["IPO"],
            )

        if "refinanc" in lowered:
            metric = self._amount_metric(query)
            if metric is None:
                raise QueryRejected(
                    RejectionCode.INCOMPLETE,
                    "Ask for the total or average debt refinancing transaction amount.",
                )
            return self._route(
                company,
                FinancingCategory.DEBT,
                metric,
                ["Debt Refinancing"],
            )

        if "debt" in lowered and "raised" in lowered:
            metric = self._raised_to_date_metric(query)
            if metric is None:
                raise QueryRejected(
                    RejectionCode.INCOMPLETE,
                    "Ask for the latest, minimum, maximum, or average debt raised to date.",
                )
            return self._route(
                company,
                FinancingCategory.DEBT,
                metric,
                [],
            )

        if "equity" in lowered and "financ" in lowered:
            metric = self._amount_metric(query)
            if metric is None:
                raise QueryRejected(
                    RejectionCode.INCOMPLETE,
                    "Ask for the total or average equity financing transaction amount.",
                )
            return self._route(
                company,
                FinancingCategory.EQUITY,
                metric,
                [],
            )

        raise self._unsupported()

    @staticmethod
    def _company(query: str) -> str | None:
        for pattern in _COMPANY_PATTERNS:
            match = pattern.search(query)
            if match:
                company = _SPACE.sub(" ", match.group("company")).strip(" ,.?\"")
                if company.casefold() not in {"the", "a", "an", "company"}:
                    return company
        return None

    @staticmethod
    def _amount_metric(query: str) -> FinancingMetric | None:
        if _AVERAGE.search(query):
            return FinancingMetric.AVERAGE_AMOUNT
        if _TOTAL.search(query):
            return FinancingMetric.SUM_AMOUNT
        return None

    @staticmethod
    def _raised_to_date_metric(query: str) -> FinancingMetric | None:
        if _AVERAGE.search(query):
            return FinancingMetric.AVERAGE_RAISED_TO_DATE
        if _MINIMUM.search(query):
            return FinancingMetric.MIN_RAISED_TO_DATE
        if _MAXIMUM.search(query):
            return FinancingMetric.MAX_RAISED_TO_DATE
        if _TOTAL.search(query) or _LATEST.search(query):
            return FinancingMetric.LATEST_RAISED_TO_DATE
        return None

    @staticmethod
    def _route(
        company: str,
        category: FinancingCategory,
        metric: FinancingMetric,
        deal_types: list[str],
    ) -> RoutedQuery:
        return RoutedQuery(
            request=FinancingAnalysisRequest(
                platform="pitchbook",
                company_name=company,
                category=category,
                metric=metric,
                deal_types=deal_types,
            ),
        )

    @staticmethod
    def _unsupported() -> QueryRejected:
        return QueryRejected(
            RejectionCode.UNSUPPORTED,
            "That financing question is outside the demonstrated workflow. "
            "Try one of the examples below.",
        )


_METRIC_LABELS = {
    FinancingMetric.SUM_AMOUNT: "Total transaction amount",
    FinancingMetric.AVERAGE_AMOUNT: "Average transaction amount",
    FinancingMetric.LATEST_RAISED_TO_DATE: "Latest raised to date",
    FinancingMetric.MIN_RAISED_TO_DATE: "Minimum raised to date",
    FinancingMetric.MAX_RAISED_TO_DATE: "Maximum raised to date",
    FinancingMetric.AVERAGE_RAISED_TO_DATE: "Average raised to date",
}


def format_answer(query: str, result: FinancingAnalysisResult, elapsed_ms: int) -> QueryAnswer:
    request = result.request
    label = _METRIC_LABELS[request.metric]
    if request.deal_types:
        label = f"{request.deal_types[0]} {label.casefold()}"
    value = _format_usd(result.value_usd)
    coverage = f"{result.disclosed_value_count} disclosed"
    if result.missing_value_count:
        coverage += f", {result.missing_value_count} undisclosed"

    lines = [
        f"## {request.company_name}",
        "",
        f"**{label}: {value}.**",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Matching transactions | {result.matched_transaction_count} |",
        f"| Value coverage | {coverage} |",
        f"| Currency | {result.currency} |",
    ]
    if result.exact_denominator > 1:
        lines.extend(
            [
                "",
                "The reported average is computed from disclosed values only:",
                "",
                rf"\(\frac{{{result.exact_numerator_usd:,}}}"
                rf"{{{result.exact_denominator}}} = {result.value_usd:,}\ \text{{USD}}\)",
            ]
        )
    lines.extend(["", f"Run `{result.run_id}` · PitchBook · {elapsed_ms / 1_000:.2f}s"])
    return QueryAnswer(
        query=query,
        interpretation=QueryInterpretation(
            company_name=request.company_name,
            category=request.category,
            metric=request.metric,
            deal_types=request.deal_types,
        ),
        markdown="\n".join(lines),
        value_usd=result.value_usd,
        matched_transaction_count=result.matched_transaction_count,
        disclosed_value_count=result.disclosed_value_count,
        missing_value_count=result.missing_value_count,
        run_id=result.run_id,
        elapsed_ms=elapsed_ms,
    )


def _format_usd(value: int | None) -> str:
    if value is None:
        return "not disclosed"
    return f"${value:,.0f}"
