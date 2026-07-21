from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FundingStage(str, Enum):
    SEED = "Seed"
    SERIES_A = "Series A"
    SERIES_B = "Series B"
    SERIES_C = "Series C"
    GROWTH = "Growth"


class FinancingCategory(str, Enum):
    ALL = "All Deals"
    DEBT = "Debt Financing"
    EQUITY = "Equity Financing"


class FinancingMetric(str, Enum):
    SUM_AMOUNT = "sum_amount"
    AVERAGE_AMOUNT = "average_amount"
    LATEST_RAISED_TO_DATE = "latest_raised_to_date"
    MIN_RAISED_TO_DATE = "min_raised_to_date"
    MAX_RAISED_TO_DATE = "max_raised_to_date"
    AVERAGE_RAISED_TO_DATE = "average_raised_to_date"


class RunStatus(str, Enum):
    COMPLETE = "complete"
    NEEDS_HUMAN = "needs_human"
    NEEDS_CONFIGURATION = "needs_configuration"
    FAILED = "failed"


class CompanyScreen(BaseModel):
    """A site-independent company screen. Bounds are inclusive except raised capital."""

    model_config = ConfigDict(extra="forbid")

    platform: Literal["toy", "pitchbook"] = "toy"
    countries: list[str] = Field(default_factory=list, max_length=20)
    industries: list[str] = Field(default_factory=list, max_length=20)
    founded_year_min: int | None = Field(default=None, ge=1800, le=2100)
    funding_stages: list[FundingStage] = Field(default_factory=list, max_length=10)
    total_raised_usd_lt: int | None = Field(default=None, gt=0)
    limit: int = Field(default=25, ge=1, le=50)

    @field_validator("countries", "industries")
    @classmethod
    def clean_values(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))

    @field_validator("funding_stages")
    @classmethod
    def unique_stages(cls, values: list[FundingStage]) -> list[FundingStage]:
        return list(dict.fromkeys(values))


class FinancingAnalysisRequest(BaseModel):
    """A deterministic aggregate over one company's financing table."""

    model_config = ConfigDict(extra="forbid")

    platform: Literal["toy", "pitchbook"] = "pitchbook"
    company_name: str = Field(min_length=1, max_length=200)
    category: FinancingCategory
    metric: FinancingMetric
    deal_types: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("company_name", mode="before")
    @classmethod
    def clean_financing_company_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("deal_types")
    @classmethod
    def clean_deal_types(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))


class Company(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    country: str
    industry: str
    founded_year: int
    funding_stage: FundingStage
    total_raised_usd: int = Field(ge=0)
    source_url: str


class FinancingTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    company_name: str
    category: FinancingCategory
    deal_type: str
    announced_date: date | None = None
    amount_usd: int | None = Field(default=None, gt=0)
    raised_to_date_usd: int | None = Field(default=None, gt=0)
    source_url: str


class LegacyDebtRefinancingRequest(BaseModel):
    """Read-only schema retained so historical evidence remains loadable."""

    platform: str
    company_name: str


class LegacyRecordedTransaction(BaseModel):
    transaction_id: str
    company_name: str
    announced_date: date
    transaction_type: str
    amount_usd: int | None = None
    source_url: str


class ScreenResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["screen_companies"] = "screen_companies"
    run_id: str
    status: RunStatus
    platform: str
    applied_filters: CompanyScreen
    companies: list[Company] = Field(default_factory=list)
    result_count: int = Field(default=0, ge=0)
    evidence_path: str | None = None
    message: str | None = None


class FinancingAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["analyze_financing_transactions"] = "analyze_financing_transactions"
    run_id: str
    status: RunStatus
    platform: str
    request: FinancingAnalysisRequest
    transactions: list[FinancingTransaction] = Field(default_factory=list)
    matched_transaction_count: int = Field(default=0, ge=0)
    disclosed_value_count: int = Field(default=0, ge=0)
    missing_value_count: int = Field(default=0, ge=0)
    value_usd: int | None = Field(default=None, ge=0)
    exact_numerator_usd: int = Field(default=0, ge=0)
    exact_denominator: int = Field(default=0, ge=0)
    value_is_rounded: bool = False
    currency: Literal["USD"] = "USD"
    is_exhaustive: bool = False
    is_synthetic: bool = False
    evidence_path: str | None = None
    message: str | None = None


class LegacyDebtRefinancingResult(BaseModel):
    """Historical result only; new callers use FinancingAnalysisResult."""

    operation: Literal["sum_debt_refinancing_transactions"]
    run_id: str
    status: RunStatus
    platform: str
    request: LegacyDebtRefinancingRequest
    transactions: list[LegacyRecordedTransaction] = Field(default_factory=list)
    matched_transaction_count: int = 0
    summed_transaction_count: int = 0
    missing_amount_count: int = 0
    total_amount_usd: int = 0
    currency: Literal["USD"] = "USD"
    is_exhaustive: bool = False
    is_synthetic: bool = False
    evidence_path: str | None = None
    message: str | None = None


RunResult = Annotated[
    ScreenResult | FinancingAnalysisResult | LegacyDebtRefinancingResult,
    Field(discriminator="operation"),
]


class BrowserSessionStatus(BaseModel):
    platform: str
    state: Literal["not_started", "signed_out", "signed_in", "unknown"]
    current_url: str | None = None
    message: str | None = None
