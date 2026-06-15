import pytest

from src.core.tool_registry import get_tool, list_registered_tools, list_tools_by_module


EXPECTED_TOOL_NAMES = [
    "parse_portfolio",
    "load_portfolio_file",
    "calculate_pfe_metrics",
    "validate_portfolio",
    "load_risk_config",
    "calculate_risk_metrics",
    "run_stress_test",
    "retrieve_methodology",
    "generate_commentary",
    "regenerate_commentary_with_validation_errors",
    "validate_report",
]

EXPECTED_TOOL_MODULES = {
    "parse_portfolio": "shared",
    "load_portfolio_file": "shared",
    "calculate_pfe_metrics": "credit_risk",
    "validate_portfolio": "market_risk",
    "load_risk_config": "shared",
    "calculate_risk_metrics": "market_risk",
    "run_stress_test": "market_risk",
    "retrieve_methodology": "shared",
    "generate_commentary": "shared",
    "regenerate_commentary_with_validation_errors": "shared",
    "validate_report": "shared",
}


def test_legacy_tool_registry_import_remains_compatible():
    from src.tool_registry import RiskTool as LegacyRiskTool
    from src.core.tool_registry import RiskTool

    assert LegacyRiskTool is RiskTool


def test_expected_tools_are_registered():
    tools = list_registered_tools()

    assert [tool.name for tool in tools] == EXPECTED_TOOL_NAMES
    assert {tool.name: tool.module for tool in tools} == EXPECTED_TOOL_MODULES
    assert all(tool.description for tool in tools)
    assert all(tool.callable_name for tool in tools)
    assert all(callable(tool.handler) for tool in tools)


def test_get_tool_returns_parse_portfolio_tool():
    tool = get_tool("parse_portfolio")

    assert tool.name == "parse_portfolio"
    assert tool.module == "shared"
    assert tool.callable_name == "src.portfolio_parser.parse_portfolio_text"
    assert callable(tool.handler)
    assert "tickers and weights" in tool.description


def test_get_tool_rejects_unknown_tool_name():
    with pytest.raises(KeyError, match="Unknown risk tool 'not_a_tool'"):
        get_tool("not_a_tool")


def test_list_tools_by_module_returns_category_tools():
    assert [tool.name for tool in list_tools_by_module("market_risk")] == [
        "validate_portfolio",
        "calculate_risk_metrics",
        "run_stress_test",
    ]
    assert [tool.name for tool in list_tools_by_module("credit_risk")] == [
        "calculate_pfe_metrics"
    ]


def test_list_tools_by_module_rejects_unknown_module():
    with pytest.raises(ValueError, match="Unknown tool module 'operations'"):
        list_tools_by_module("operations")
