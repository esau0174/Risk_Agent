from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.reporting.agent import (
    generate_risk_commentary,
    regenerate_risk_commentary_with_validation_errors,
)
from src.credit_risk.counterparty_risk import calculate_pfe_metrics
from src.data.portfolio import validate_weights
from src.data.portfolio_loader import load_portfolio_file
from src.data.portfolio_parser import parse_portfolio_text
from src.market_risk.risk_report import generate_portfolio_risk_report
from src.market_risk.stress_testing import run_stress_test
from src.knowledge.rag import retrieve_relevant_methodology
from src.report_validator import validate_generated_report
from src.core.risk_config import load_risk_config


@dataclass(frozen=True)
class RiskTool:
    name: str
    module: str
    description: str
    callable_name: str
    handler: Callable[..., Any]


_REGISTERED_TOOLS: tuple[RiskTool, ...] = (
    RiskTool(
        name="parse_portfolio",
        module="shared",
        description="Extract tickers and weights from a natural-language portfolio query.",
        callable_name="src.portfolio_parser.parse_portfolio_text",
        handler=parse_portfolio_text,
    ),
    RiskTool(
        name="load_portfolio_file",
        module="shared",
        description="Load and validate market holdings or exposure profiles from CSV, XLSX, or JSON.",
        callable_name="src.portfolio_loader.load_portfolio_file",
        handler=load_portfolio_file,
    ),
    RiskTool(
        name="calculate_pfe_metrics",
        module="credit_risk",
        description="Calculate peak PFE and expected exposure profile metrics.",
        callable_name="src.counterparty_risk.calculate_pfe_metrics",
        handler=calculate_pfe_metrics,
    ),
    RiskTool(
        name="validate_portfolio",
        module="market_risk",
        description="Validate ticker and weight consistency before risk calculations.",
        callable_name="src.portfolio.validate_weights",
        handler=validate_weights,
    ),
    RiskTool(
        name="load_risk_config",
        module="shared",
        description="Load and validate risk calculation and reporting configuration.",
        callable_name="src.risk_config.load_risk_config",
        handler=load_risk_config,
    ),
    RiskTool(
        name="calculate_risk_metrics",
        module="market_risk",
        description="Compute portfolio returns and historical risk metrics.",
        callable_name="src.risk_report.generate_portfolio_risk_report",
        handler=generate_portfolio_risk_report,
    ),
    RiskTool(
        name="run_stress_test",
        module="market_risk",
        description="Apply deterministic equity, technology, and rates stress scenarios.",
        callable_name="src.stress_testing.run_stress_test",
        handler=run_stress_test,
    ),
    RiskTool(
        name="retrieve_methodology",
        module="shared",
        description="Retrieve local methodology notes relevant to the risk analysis.",
        callable_name="src.rag.retrieve_relevant_methodology",
        handler=retrieve_relevant_methodology,
    ),
    RiskTool(
        name="generate_commentary",
        module="shared",
        description="Generate analyst-style commentary from calculated risk facts and methodology notes.",
        callable_name="src.agent.generate_risk_commentary",
        handler=generate_risk_commentary,
    ),
    RiskTool(
        name="regenerate_commentary_with_validation_errors",
        module="shared",
        description="Regenerate risk commentary once using report validation errors and warnings.",
        callable_name="src.agent.regenerate_risk_commentary_with_validation_errors",
        handler=regenerate_risk_commentary_with_validation_errors,
    ),
    RiskTool(
        name="validate_report",
        module="shared",
        description="Validate numerical risk outputs, methodology grounding, and generated commentary guardrails.",
        callable_name="src.report_validator.validate_generated_report",
        handler=validate_generated_report,
    ),
)

_TOOL_BY_NAME = {tool.name: tool for tool in _REGISTERED_TOOLS}


def list_registered_tools() -> list[RiskTool]:
    """Return the deterministic set of risk tools exposed to the workflow."""
    return list(_REGISTERED_TOOLS)


def list_tools_by_module(module: str) -> list[RiskTool]:
    """Return registered tools belonging to a supported risk module."""
    supported_modules = {"shared", "market_risk", "credit_risk"}
    if module not in supported_modules:
        supported = ", ".join(sorted(supported_modules))
        raise ValueError(
            f"Unknown tool module '{module}'. Supported modules: {supported}."
        )
    return [tool for tool in _REGISTERED_TOOLS if tool.module == module]


def get_tool(name: str) -> RiskTool:
    """Return a registered risk tool by name."""
    try:
        return _TOOL_BY_NAME[name]
    except KeyError as exc:
        available_tools = ", ".join(_TOOL_BY_NAME)
        raise KeyError(
            f"Unknown risk tool '{name}'. Available tools: {available_tools}."
        ) from exc
