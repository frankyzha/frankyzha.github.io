import pytest

from collarai.mcp_server import mcp


@pytest.mark.asyncio
async def test_mcp_exposes_only_typed_tools() -> None:
    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == {
        "screen_companies",
        "analyze_financing_transactions",
        "get_browser_session_status",
        "get_browser_run",
    }
    screen = next(tool for tool in tools if tool.name == "screen_companies")
    assert "screen" in screen.inputSchema["properties"]
    analysis = next(tool for tool in tools if tool.name == "analyze_financing_transactions")
    assert "request" in analysis.inputSchema["properties"]
