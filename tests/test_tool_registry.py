import pytest

from src.tool_registry import get_tool, list_registered_tools


EXPECTED_TOOL_NAMES = [
    "parse_portfolio",
    "validate_portfolio",
    "calculate_risk_metrics",
    "retrieve_methodology",
    "generate_commentary",
    "regenerate_commentary_with_validation_errors",
    "validate_report",
]


def test_expected_tools_are_registered():
    tools = list_registered_tools()

    assert [tool.name for tool in tools] == EXPECTED_TOOL_NAMES
    assert all(tool.description for tool in tools)
    assert all(tool.callable_name for tool in tools)
    assert all(callable(tool.handler) for tool in tools)


def test_get_tool_returns_parse_portfolio_tool():
    tool = get_tool("parse_portfolio")

    assert tool.name == "parse_portfolio"
    assert tool.callable_name == "src.portfolio_parser.parse_portfolio_text"
    assert callable(tool.handler)
    assert "tickers and weights" in tool.description


def test_get_tool_rejects_unknown_tool_name():
    with pytest.raises(KeyError, match="Unknown risk tool 'not_a_tool'"):
        get_tool("not_a_tool")
