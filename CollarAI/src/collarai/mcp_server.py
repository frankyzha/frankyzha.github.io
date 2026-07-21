from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from collarai.models import (
    BrowserSessionStatus,
    CompanyScreen,
    FinancingAnalysisRequest,
    FinancingAnalysisResult,
    RunResult,
    ScreenResult,
)
from collarai.service import BrowserService, build_service


@dataclass(slots=True)
class AppContext:
    browser: BrowserService


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    browser = build_service()
    try:
        yield AppContext(browser=browser)
    finally:
        await browser.close()


mcp = FastMCP(
    "CollarAI Browser",
    instructions=(
        "Use the narrow structured market-data tool that matches the request. "
        "Do not invent results. "
        "If a run needs_human, ask the user to complete authentication in the persistent browser."
    ),
    lifespan=lifespan,
)

MCPContext = Context[ServerSession, AppContext]


@mcp.tool()
async def screen_companies(screen: CompanyScreen, ctx: MCPContext) -> ScreenResult:
    """Apply structured filters in an authenticated market-data UI and extract verified rows."""
    return await ctx.request_context.lifespan_context.browser.screen_companies(screen)


@mcp.tool()
async def analyze_financing_transactions(
    request: FinancingAnalysisRequest,
    ctx: MCPContext,
) -> FinancingAnalysisResult:
    """Aggregate Amount or Raised to Date over verified company financing rows."""
    return await ctx.request_context.lifespan_context.browser.analyze_financing_transactions(
        request
    )


@mcp.tool()
async def get_browser_session_status(
    platform: Literal["toy", "pitchbook"], ctx: MCPContext
) -> BrowserSessionStatus:
    """Report whether the persistent browser session is started and signed in."""
    return await ctx.request_context.lifespan_context.browser.get_session_status(platform)


@mcp.tool()
async def get_browser_run(run_id: str, ctx: MCPContext) -> RunResult:
    """Load a prior structured result and its evidence location by run ID."""
    return ctx.request_context.lifespan_context.browser.get_run(run_id)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
