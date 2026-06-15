"""Market risk analytics and reporting."""

from src.market_risk.risk_metrics import (
    annualized_volatility,
    correlation_matrix,
    expected_shortfall,
    historical_var,
    max_drawdown,
)
from src.market_risk.risk_report import generate_portfolio_risk_report
from src.market_risk.stress_testing import run_stress_test

__all__ = [
    "annualized_volatility",
    "correlation_matrix",
    "expected_shortfall",
    "generate_portfolio_risk_report",
    "historical_var",
    "max_drawdown",
    "run_stress_test",
]
