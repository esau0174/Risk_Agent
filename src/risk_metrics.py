"""Compatibility wrapper for src.market_risk.risk_metrics. New code should import from src.market_risk.risk_metrics."""

from src.market_risk.risk_metrics import (
    annualized_volatility,
    correlation_matrix,
    expected_shortfall,
    historical_var,
    max_drawdown,
)

__all__ = [
    "annualized_volatility",
    "correlation_matrix",
    "expected_shortfall",
    "historical_var",
    "max_drawdown",
]
