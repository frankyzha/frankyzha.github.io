from __future__ import annotations

from urllib.parse import urlparse

from collarai.errors import PolicyViolation
from collarai.models import (
    Company,
    CompanyScreen,
    FinancingAnalysisRequest,
    FinancingTransaction,
)


class BrowserPolicy:
    """Small, explicit guardrail around browser targets and returned data."""

    def __init__(self, allowed_hosts: set[str], max_results: int = 50) -> None:
        self.allowed_hosts = allowed_hosts
        self.max_results = max_results

    def check_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in self.allowed_hosts:
            raise PolicyViolation(f"Browser target is not allowed: {url}")

    def check_screen(self, screen: CompanyScreen) -> None:
        if screen.limit > self.max_results:
            raise PolicyViolation(f"Result limit cannot exceed {self.max_results}")

    def check_companies(self, screen: CompanyScreen, companies: list[Company]) -> None:
        if len(companies) > screen.limit:
            raise PolicyViolation("The adapter returned more rows than requested")
        for company in companies:
            if screen.countries and company.country not in screen.countries:
                raise PolicyViolation(f"Unexpected country in result: {company.name}")
            if screen.industries and company.industry not in screen.industries:
                raise PolicyViolation(f"Unexpected industry in result: {company.name}")
            if screen.founded_year_min and company.founded_year < screen.founded_year_min:
                raise PolicyViolation(f"Unexpected founding year in result: {company.name}")
            if screen.funding_stages and company.funding_stage not in screen.funding_stages:
                raise PolicyViolation(f"Unexpected funding stage in result: {company.name}")
            if (
                screen.total_raised_usd_lt is not None
                and company.total_raised_usd >= screen.total_raised_usd_lt
            ):
                raise PolicyViolation(f"Unexpected funding total in result: {company.name}")

    def check_financing_transactions(
        self,
        request: FinancingAnalysisRequest,
        transactions: list[FinancingTransaction],
    ) -> None:
        seen: set[str] = set()
        for transaction in transactions:
            if transaction.transaction_id in seen:
                raise PolicyViolation(f"Duplicate transaction: {transaction.transaction_id}")
            seen.add(transaction.transaction_id)
            if transaction.company_name.casefold() != request.company_name.casefold():
                raise PolicyViolation(
                    f"Unexpected company in transaction: {transaction.transaction_id}"
                )
            if transaction.category is not request.category:
                raise PolicyViolation(
                    f"Unexpected financing category: {transaction.transaction_id}"
                )
