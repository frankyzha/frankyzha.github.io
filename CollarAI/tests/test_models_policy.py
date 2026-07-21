import pytest
from pydantic import ValidationError

from collarai.errors import PolicyViolation
from collarai.models import (
    Company,
    CompanyScreen,
    FinancingAnalysisRequest,
    FinancingCategory,
    FinancingMetric,
    FinancingTransaction,
    FundingStage,
)
from collarai.policy import BrowserPolicy


def test_screen_normalizes_values_and_rejects_unknown_fields() -> None:
    screen = CompanyScreen(countries=[" United States ", "United States"])
    assert screen.countries == ["United States"]
    with pytest.raises(ValidationError):
        CompanyScreen(unknown=True)

    request = FinancingAnalysisRequest(
        company_name=" Nvidia ",
        category=FinancingCategory.DEBT,
        metric=FinancingMetric.SUM_AMOUNT,
    )
    assert request.company_name == "Nvidia"
    with pytest.raises(ValidationError):
        FinancingAnalysisRequest(
            company_name="   ",
            category=FinancingCategory.DEBT,
            metric=FinancingMetric.SUM_AMOUNT,
        )


def test_policy_rejects_a_result_outside_the_screen() -> None:
    screen = CompanyScreen(
        countries=["United States"],
        funding_stages=[FundingStage.SERIES_A],
        total_raised_usd_lt=50_000_000,
    )
    invalid = Company(
        name="Too Large",
        country="United States",
        industry="Enterprise Software",
        founded_year=2022,
        funding_stage=FundingStage.SERIES_A,
        total_raised_usd=50_000_000,
        source_url="https://example.com/too-large",
    )
    with pytest.raises(PolicyViolation):
        BrowserPolicy({"example.com"}).check_companies(screen, [invalid])


def test_policy_rejects_unapproved_hosts() -> None:
    with pytest.raises(PolicyViolation):
        BrowserPolicy({"example.com"}).check_url("https://unapproved.example/search")


def test_policy_rejects_duplicate_transactions() -> None:
    request = FinancingAnalysisRequest(
        company_name="Nvidia",
        category=FinancingCategory.DEBT,
        metric=FinancingMetric.SUM_AMOUNT,
    )
    transaction = FinancingTransaction(
        transaction_id="duplicate",
        company_name="Nvidia",
        category=FinancingCategory.DEBT,
        deal_type="Debt Refinancing",
        announced_date="2024-01-01",
        amount_usd=10,
        source_url="https://example.com/duplicate",
    )
    with pytest.raises(PolicyViolation):
        BrowserPolicy({"example.com"}).check_financing_transactions(
            request,
            [transaction, transaction],
        )
