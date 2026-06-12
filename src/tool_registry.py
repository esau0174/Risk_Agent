from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.agent import generate_risk_commentary
from src.portfolio import validate_weights
from src.portfolio_parser import parse_portfolio_text
from src.rag import retrieve_relevant_methodology
from src.report_validator import validate_generated_report
from src.risk_report import generate_portfolio_risk_report


@dataclass(frozen=True)
class RiskTool:
    name: str
    description: str
    callable_name: str
    callable: Callable[..., Any]


_REGISTERED_TOOLS: tuple[RiskTool, ...] = (
    RiskTool(
        name="parse_portfolio",
        description="Extract tickers and weights from a natural-language portfolio query.",
        callable_name="src.portfolio_parser.parse_portfolio_text",
        callable=parse_portfolio_text,
    ),
    RiskTool(
        name="validate_portfolio",
        description="Validate ticker and weight consistency before risk calculations.",
        callable_name="src.portfolio.validate_weights",
        callable=validate_weights,
    ),
    RiskTool(
        name="calculate_risk_metrics",
        description="Compute portfolio returns and historical risk metrics.",
        callable_name="src.risk_report.generate_portfolio_risk_report",
        callable=generate_portfolio_risk_report,
    ),
    RiskTool(
        name="retrieve_methodology",
        description="Retrieve local methodology notes relevant to the risk analysis.",
        callable_name="src.rag.retrieve_relevant_methodology",
        callable=retrieve_relevant_methodology,
    ),
    RiskTool(
        name="generate_commentary",
        description="Generate analyst-style commentary from calculated risk facts and methodology notes.",
        callable_name="src.agent.generate_risk_commentary",
        callable=generate_risk_commentary,
    ),
    RiskTool(
        name="validate_report",
        description="Validate numerical risk outputs, methodology grounding, and generated commentary guardrails.",
        callable_name="src.report_validator.validate_generated_report",
        callable=validate_generated_report,
    ),
)

_TOOL_BY_NAME = {tool.name: tool for tool in _REGISTERED_TOOLS}


def list_registered_tools() -> list[RiskTool]:
    """Return the deterministic set of risk tools exposed to the workflow."""
    return list(_REGISTERED_TOOLS)


def get_tool(name: str) -> RiskTool:
    """Return a registered risk tool by name."""
    try:
        return _TOOL_BY_NAME[name]
    except KeyError as exc:
        available_tools = ", ".join(_TOOL_BY_NAME)
        raise KeyError(
            f"Unknown risk tool '{name}'. Available tools: {available_tools}."
        ) from exc
