"""Compatibility wrapper for src.reporting.agent. New code should import from src.reporting.agent."""

from src.reporting.agent import (
    _build_commentary_facts,
    _build_methodology_query,
    analyze_portfolio_query_with_llm,
    generate_risk_commentary,
    regenerate_risk_commentary_with_validation_errors,
)

__all__ = [
    "_build_commentary_facts",
    "_build_methodology_query",
    "analyze_portfolio_query_with_llm",
    "generate_risk_commentary",
    "regenerate_risk_commentary_with_validation_errors",
]
