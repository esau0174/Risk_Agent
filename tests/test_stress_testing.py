from __future__ import annotations

import pytest

from src.risk_config import RiskConfig, StressScenario
from src.stress_testing import run_stress_test
from src.tool_executor import ToolExecutor


def _stress_config() -> RiskConfig:
    return RiskConfig(
        stress_scenarios=(
            StressScenario(
                name="Combined selloff",
                equity_selloff_pct=0.10,
                tech_selloff_pct=0.20,
                rates_shock_bps=100,
            ),
        )
    )


def test_run_stress_test_calculates_deterministic_portfolio_loss():
    results = run_stress_test(
        ["SPY", "QQQ", "NVDA", "TLT"],
        [0.4, 0.3, 0.2, 0.1],
        risk_config=_stress_config(),
    )

    assert len(results) == 1
    result = results[0]
    assert result["scenario_name"] == "Combined selloff"
    assert result["base_portfolio_value"] == 100.0
    assert result["stressed_portfolio_value"] == pytest.approx(82.5)
    assert result["portfolio_loss_pct"] == pytest.approx(0.175)
    assert result["per_ticker_contributions"]["SPY"][
        "portfolio_loss_contribution_pct"
    ] == pytest.approx(0.04)
    assert result["per_ticker_contributions"]["QQQ"][
        "portfolio_loss_contribution_pct"
    ] == pytest.approx(0.06)
    assert result["per_ticker_contributions"]["NVDA"][
        "portfolio_loss_contribution_pct"
    ] == pytest.approx(0.06)
    assert result["per_ticker_contributions"]["TLT"][
        "portfolio_loss_contribution_pct"
    ] == pytest.approx(0.015)
    assert result["assumptions"]


def test_run_stress_test_is_executable_through_tool_executor():
    result = ToolExecutor().execute(
        "run_stress_test",
        ["SPY", "QQQ"],
        [0.5, 0.5],
        risk_config=_stress_config(),
    )

    assert result.status == "success"
    assert len(result.output) == 1
    assert result.metadata["callable_name"] == "src.stress_testing.run_stress_test"


def test_run_stress_test_accepts_scenario_dictionaries():
    results = run_stress_test(
        ["SPY"],
        [1.0],
        stress_scenarios=[
            {
                "name": "Equity selloff",
                "equity_selloff_pct": 0.12,
                "tech_selloff_pct": 0.20,
                "rates_shock_bps": 50,
            }
        ],
    )

    assert results[0]["portfolio_loss_pct"] == pytest.approx(0.12)
