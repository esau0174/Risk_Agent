"""Deterministic prototype stress testing for portfolio holdings."""

from __future__ import annotations

from collections.abc import Sequence

from src.portfolio import validate_weights
from src.risk_config import RiskConfig, StressScenario, parse_stress_scenarios


BASE_PORTFOLIO_VALUE = 100.0
NVDA_TECH_BETA = 1.5
TLT_DURATION_PROXY = 15.0


def run_stress_test(
    tickers: Sequence[str],
    weights: Sequence[float],
    risk_config: RiskConfig | None = None,
    stress_scenarios: Sequence[StressScenario | dict] | None = None,
) -> list[dict]:
    """Apply deterministic ticker-level shocks and return structured results."""
    ticker_list = [str(ticker).strip().upper() for ticker in tickers]
    validated_weights = validate_weights(ticker_list, weights).tolist()

    if risk_config is not None and stress_scenarios is not None:
        raise ValueError("Provide risk_config or stress_scenarios, not both.")
    scenarios = (
        risk_config.stress_scenarios
        if risk_config is not None
        else parse_stress_scenarios(tuple(stress_scenarios or ()))
    )
    if not scenarios:
        return []

    results = []
    for scenario in scenarios:
        contributions = {}
        stressed_value = 0.0
        for ticker, weight in zip(ticker_list, validated_weights, strict=True):
            applied_return, sensitivity = _ticker_stress_return(ticker, scenario)
            position_value = BASE_PORTFOLIO_VALUE * weight
            stressed_position_value = position_value * (1.0 + applied_return)
            stressed_value += stressed_position_value
            contributions[ticker] = {
                "weight": float(weight),
                "sensitivity": sensitivity,
                "applied_return_pct": float(applied_return),
                "portfolio_loss_contribution_pct": float(-weight * applied_return),
            }

        results.append(
            {
                "scenario_name": scenario.name,
                "base_portfolio_value": BASE_PORTFOLIO_VALUE,
                "stressed_portfolio_value": float(stressed_value),
                "portfolio_loss_pct": float(
                    (BASE_PORTFOLIO_VALUE - stressed_value) / BASE_PORTFOLIO_VALUE
                ),
                "per_ticker_contributions": contributions,
                "assumptions": [
                    "SPY and unclassified tickers use the broad equity selloff shock.",
                    "QQQ uses the technology selloff shock.",
                    "NVDA uses 1.5 times the technology selloff shock as a high-beta proxy.",
                    "TLT uses a 15-year duration proxy against the parallel rates shock.",
                    "The calculation is deterministic and excludes correlations and nonlinear effects.",
                ],
            }
        )

    return results


def _ticker_stress_return(
    ticker: str,
    scenario: StressScenario,
) -> tuple[float, str]:
    if ticker == "QQQ":
        return -scenario.tech_selloff_pct, "technology"
    if ticker == "NVDA":
        return -NVDA_TECH_BETA * scenario.tech_selloff_pct, "high_beta_technology"
    if ticker == "TLT":
        return (
            -TLT_DURATION_PROXY * scenario.rates_shock_bps / 10_000,
            "rates_duration",
        )
    return -scenario.equity_selloff_pct, "broad_equity"


def apply_shock_to_returns(*args, **kwargs):
    """Placeholder for Phase 2+ stress shock analysis."""
    raise NotImplementedError("Stress testing is planned for a later phase.")


def run_historical_stress_scenario(*args, **kwargs):
    """Placeholder for Phase 2+ historical stress analysis."""
    raise NotImplementedError("Stress testing is planned for a later phase.")
