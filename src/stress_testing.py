"""Compatibility exports for market risk stress testing."""

from src.market_risk.stress_testing import (
    apply_shock_to_returns,
    run_historical_stress_scenario,
    run_stress_test,
)

__all__ = [
    "apply_shock_to_returns",
    "run_historical_stress_scenario",
    "run_stress_test",
]
