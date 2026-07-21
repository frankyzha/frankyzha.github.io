import pytest
from httpx import ASGITransport, AsyncClient

from collarai.toy.app import create_app

QUERY = {
    "platform": "toy",
    "countries": ["United States"],
    "industries": ["Enterprise Software"],
    "founded_year_min": 2021,
    "funding_stages": ["Series A", "Series B"],
    "total_raised_usd_lt": 50_000_000,
    "limit": 25,
}


@pytest.mark.asyncio
async def test_search_requires_login_and_applies_every_filter() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/search", json=QUERY)).status_code == 401
        login = await client.post(
            "/api/login", json={"email": "demo@collarai.local", "password": "demo"}
        )
        assert login.status_code == 200
        response = await client.post("/api/search", json=QUERY)
        assert response.status_code == 200
        companies = response.json()["companies"]
        assert [company["name"] for company in companies] == [
            "Northstar Systems",
            "Juniper Grid",
            "Relay Harbor",
        ]
