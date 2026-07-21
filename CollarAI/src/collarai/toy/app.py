from __future__ import annotations

import os
import secrets
from importlib.resources import files
from pathlib import Path

import uvicorn
from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from collarai.models import (
    Company,
    CompanyScreen,
    FundingStage,
)

ROOT = Path(
    os.getenv(
        "COLLAR_TOY_ASSET_DIR",
        str(files("collarai.toy").joinpath("static")),
    )
).resolve()
COOKIE = "collarai_toy_session"

COMPANIES = [
    Company(
        name="Northstar Systems",
        country="United States",
        industry="Enterprise Software",
        founded_year=2022,
        funding_stage=FundingStage.SERIES_A,
        total_raised_usd=24_000_000,
        source_url="https://example.com/companies/northstar-systems",
    ),
    Company(
        name="Juniper Grid",
        country="United States",
        industry="Enterprise Software",
        founded_year=2023,
        funding_stage=FundingStage.SERIES_B,
        total_raised_usd=47_000_000,
        source_url="https://example.com/companies/juniper-grid",
    ),
    Company(
        name="Relay Harbor",
        country="United States",
        industry="Enterprise Software",
        founded_year=2021,
        funding_stage=FundingStage.SERIES_A,
        total_raised_usd=18_500_000,
        source_url="https://example.com/companies/relay-harbor",
    ),
    Company(
        name="Atlas Compute",
        country="United States",
        industry="Enterprise Software",
        founded_year=2023,
        funding_stage=FundingStage.SERIES_B,
        total_raised_usd=126_000_000,
        source_url="https://example.com/companies/atlas-compute",
    ),
    Company(
        name="Cedar Ledger",
        country="United States",
        industry="Fintech",
        founded_year=2022,
        funding_stage=FundingStage.SERIES_A,
        total_raised_usd=32_000_000,
        source_url="https://example.com/companies/cedar-ledger",
    ),
    Company(
        name="Mercury Desk",
        country="United States",
        industry="Enterprise Software",
        founded_year=2019,
        funding_stage=FundingStage.SERIES_B,
        total_raised_usd=41_000_000,
        source_url="https://example.com/companies/mercury-desk",
    ),
    Company(
        name="Maple Runtime",
        country="Canada",
        industry="Enterprise Software",
        founded_year=2022,
        funding_stage=FundingStage.SERIES_A,
        total_raised_usd=29_000_000,
        source_url="https://example.com/companies/maple-runtime",
    ),
    Company(
        name="Willow Cloud",
        country="United States",
        industry="Enterprise Software",
        founded_year=2024,
        funding_stage=FundingStage.SEED,
        total_raised_usd=8_000_000,
        source_url="https://example.com/companies/willow-cloud",
    ),
]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: str


class SessionStore:
    def __init__(self) -> None:
        self.tokens: set[str] = set()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        self.tokens.add(token)
        return token

    def valid(self, token: str | None) -> bool:
        return token is not None and token in self.tokens


def create_app(
    username: str = "demo@collarai.local",
    password: str = "demo",
) -> FastAPI:
    app = FastAPI(title="CollarAI Synthetic Market", docs_url=None, redoc_url=None)
    sessions = SessionStore()

    def require_session(token: str | None) -> None:
        if not sessions.valid(token):
            raise HTTPException(status_code=401, detail="Sign in first")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(ROOT / "index.html")

    @app.get("/styles.css", include_in_schema=False)
    async def styles() -> FileResponse:
        return FileResponse(ROOT / "styles.css", media_type="text/css")

    @app.get("/script.js", include_in_schema=False)
    async def script() -> FileResponse:
        return FileResponse(ROOT / "script.js", media_type="application/javascript")

    @app.get("/api/session")
    async def session(token: str | None = Cookie(default=None, alias=COOKIE)) -> dict[str, bool]:
        return {"authenticated": sessions.valid(token)}

    @app.post("/api/login")
    async def login(payload: LoginRequest, response: Response) -> dict[str, bool]:
        valid_user = secrets.compare_digest(payload.email, username)
        valid_password = secrets.compare_digest(payload.password, password)
        if not (valid_user and valid_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        response.set_cookie(
            COOKIE,
            sessions.create(),
            httponly=True,
            samesite="strict",
            max_age=8 * 60 * 60,
        )
        return {"authenticated": True}

    @app.post("/api/search")
    async def search(
        query: CompanyScreen,
        token: str | None = Cookie(default=None, alias=COOKIE),
    ) -> dict[str, object]:
        require_session(token)
        if query.platform != "toy":
            raise HTTPException(status_code=400, detail="This demo only supports the toy platform")
        matches = [company for company in COMPANIES if _matches(company, query)][: query.limit]
        return {
            "companies": [company.model_dump(mode="json") for company in matches],
            "filters": query.model_dump(mode="json"),
        }

    return app


def _matches(company: Company, query: CompanyScreen) -> bool:
    return all(
        (
            not query.countries or company.country in query.countries,
            not query.industries or company.industry in query.industries,
            query.founded_year_min is None or company.founded_year >= query.founded_year_min,
            not query.funding_stages or company.funding_stage in query.funding_stages,
            query.total_raised_usd_lt is None
            or company.total_raised_usd < query.total_raised_usd_lt,
        )
    )


app = create_app(
    username=os.getenv("COLLAR_TOY_USERNAME", "demo@collarai.local"),
    password=os.getenv("COLLAR_TOY_PASSWORD", "demo"),
)


def main() -> None:
    uvicorn.run(
        "collarai.toy.app:app",
        host="127.0.0.1",
        port=int(os.getenv("COLLAR_TOY_PORT", "8765")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
