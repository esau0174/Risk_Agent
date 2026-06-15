from __future__ import annotations

import importlib

import pytest


WRAPPER_EXPORTS = (
    ("src.agent", "src.reporting.agent", "generate_risk_commentary"),
    (
        "src.counterparty_risk",
        "src.credit_risk.counterparty_risk",
        "calculate_pfe_metrics",
    ),
    ("src.market_data", "src.data.market_data", "download_price_data"),
    ("src.portfolio", "src.data.portfolio", "validate_weights"),
    (
        "src.portfolio_loader",
        "src.data.portfolio_loader",
        "load_portfolio_file",
    ),
    (
        "src.portfolio_parser",
        "src.data.portfolio_parser",
        "parse_portfolio_text",
    ),
    ("src.rag", "src.knowledge.rag", "load_methodology_docs"),
    ("src.risk_config", "src.core.risk_config", "RiskConfig"),
    (
        "src.risk_metrics",
        "src.market_risk.risk_metrics",
        "historical_var",
    ),
    (
        "src.risk_report",
        "src.market_risk.risk_report",
        "generate_portfolio_risk_report",
    ),
    (
        "src.stress_testing",
        "src.market_risk.stress_testing",
        "run_stress_test",
    ),
    ("src.tool_executor", "src.core.tool_executor", "ToolExecutor"),
    ("src.tool_registry", "src.core.tool_registry", "RiskTool"),
)


@pytest.mark.parametrize(("wrapper_name", "canonical_name", "export_name"), WRAPPER_EXPORTS)
def test_wrapper_reexports_canonical_api(wrapper_name, canonical_name, export_name):
    wrapper = importlib.import_module(wrapper_name)
    canonical = importlib.import_module(canonical_name)

    assert getattr(wrapper, export_name) is getattr(canonical, export_name)


def test_report_generator_wrapper_and_canonical_module_are_importable():
    wrapper = importlib.import_module("src.report_generator")
    canonical = importlib.import_module("src.reporting.report_generator")

    assert wrapper.__doc__
    assert canonical.__name__ == "src.reporting.report_generator"
