from __future__ import annotations

import pytest

from src.report_validator import validate_generated_report


def _valid_parsed_portfolio() -> dict:
    return {"tickers": ["SPY", "QQQ"], "weights": [0.4, 0.6]}


def _valid_risk_report() -> dict:
    return {
        "risk_metrics": {
            "annualized_volatility": 0.20,
            "historical_var": 0.02,
            "expected_shortfall": 0.03,
            "max_drawdown": 0.15,
        }
    }


def _valid_methodology_notes() -> list[dict]:
    return [
        {"title": "Historical VaR"},
        {"title": "Expected Shortfall"},
        {"title": "Model Limitations"},
    ]


def _safe_commentary() -> str:
    return (
        "The report discusses downside risk using VaR and Expected Shortfall. "
        "Assumptions and limitations: this uses historical data only and is not "
        "investment advice. Methodology references: Historical VaR, Expected Shortfall."
    )


def _stress_results() -> list[dict]:
    return [
        {
            "scenario_name": "Combined selloff",
            "base_portfolio_value": 100.0,
            "stressed_portfolio_value": 82.5,
            "portfolio_loss_pct": 0.175,
            "per_ticker_contributions": {
                "SPY": {"portfolio_loss_contribution_pct": 0.04},
                "QQQ": {"portfolio_loss_contribution_pct": 0.06},
            },
        }
    ]


def test_valid_numerical_report_and_safe_commentary_pass():
    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        _safe_commentary(),
    )

    assert result.passed is True
    assert not result.errors
    assert all(check.passed for check in result.checks)


def test_negative_var_fails():
    report = _valid_risk_report()
    report["risk_metrics"]["historical_var"] = -0.02

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        report,
        _valid_methodology_notes(),
        _safe_commentary(),
    )

    assert result.passed is False
    assert any("Historical VaR must be a positive" in error for error in result.errors)


def test_expected_shortfall_lower_than_var_fails():
    report = _valid_risk_report()
    report["risk_metrics"]["historical_var"] = 0.04
    report["risk_metrics"]["expected_shortfall"] = 0.03

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        report,
        _valid_methodology_notes(),
        _safe_commentary(),
    )

    assert result.passed is False
    assert any(
        "Expected Shortfall must be greater than or equal" in error
        for error in result.errors
    )


def test_negative_max_drawdown_fails():
    report = _valid_risk_report()
    report["risk_metrics"]["max_drawdown"] = -0.15

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        report,
        _valid_methodology_notes(),
        _safe_commentary(),
    )

    assert result.passed is False
    assert any("Maximum drawdown must be a positive" in error for error in result.errors)


def test_direct_buy_sell_hold_recommendation_fails():
    commentary = (
        "You should buy SPY. Assumptions and limitations: historical data only. "
        "Methodology reference: Historical VaR."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is False
    assert any("buy, sell, or hold" in error for error in result.errors)


@pytest.mark.parametrize(
    "disclaimer",
    [
        "This commentary does not constitute investment advice.",
        "This is not investment advice.",
        "This is not a recommendation to buy, sell, or hold any security.",
    ],
)
def test_negated_recommendation_disclaimers_are_allowed(disclaimer):
    commentary = f"Assumptions and limitations: historical data only. {disclaimer}"

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is True


@pytest.mark.parametrize(
    "recommendation",
    [
        "Buy SPY.",
        "Sell NVDA.",
        "Hold QQQ.",
        "I recommend buying SPY.",
        "Increase exposure to NVDA.",
        "Reduce exposure to QQQ.",
    ],
)
def test_actionable_trade_recommendations_are_forbidden(recommendation):
    commentary = (
        f"{recommendation} Assumptions and limitations: historical data only. "
        "This commentary does not constitute investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is False
    assert any("buy, sell, or hold" in error for error in result.errors)


def test_commentary_without_assumptions_or_limitations_warns():
    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        "Downside risk is discussed. Methodology reference: Historical VaR.",
    )

    assert result.passed is True
    assert result.warnings == ["Commentary should include assumptions or limitations."]
    assert any(
        check.name == "includes_assumptions_or_limitations" and not check.passed
        for check in result.checks
    )


def test_unsupported_methodology_citation_fails():
    commentary = (
        "Assumptions and limitations: historical data only. "
        "Methodology reference: Stress Testing."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is False
    assert any("were not retrieved: Stress Testing" in error for error in result.errors)


def test_negated_guarantee_disclaimer_does_not_fail_certainty_check():
    commentary = (
        "Assumptions and limitations: historical data only, without guaranteed "
        "forecasts. Methodology reference: Historical VaR."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is True


def test_matching_commentary_metric_percentages_pass():
    commentary = (
        "Annualized volatility is 20.00%. Historical VaR is 2.00%. "
        "Expected Shortfall is 3.00%, and maximum drawdown is 15.00%. "
        "Assumptions and limitations: historical data only; not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is True


def test_mismatched_var_percentage_fails():
    commentary = (
        "95% historical VaR is 4.50%. Assumptions and limitations: historical data "
        "only; not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is False
    assert any(
        "Historical VaR percentage mismatch: expected 2.00%, found 4.50%." in error
        for error in result.errors
    )


def test_mismatched_expected_shortfall_percentage_fails():
    commentary = (
        "Expected Shortfall is 5.00%. Assumptions and limitations: historical data "
        "only; not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is False
    assert any(
        "Expected Shortfall percentage mismatch: expected 3.00%, found 5.00%." in error
        for error in result.errors
    )


def test_unrelated_percentages_do_not_fail_metric_consistency():
    commentary = (
        "SPY has a 40% portfolio weight. Assumptions and limitations: historical data "
        "only; not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is True


def test_metric_percentage_within_tolerance_passes():
    commentary = (
        "Historical VaR is 2.08%. Assumptions and limitations: historical data only; "
        "not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
        percentage_tolerance=0.10,
    )

    assert result.passed is True


def test_var_and_expected_shortfall_in_separate_sentences_do_not_cross_match():
    report = _valid_risk_report()
    report["risk_metrics"]["historical_var"] = 0.0232
    report["risk_metrics"]["expected_shortfall"] = 0.0347
    commentary = (
        "Historical VaR, calculated for a 95% confidence level, indicates a potential "
        "loss threshold of approximately 2.32%. "
        "Expected Shortfall, conditional on exceeding the VaR threshold, is "
        "approximately 3.47%. Assumptions and limitations: historical data only; "
        "not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        report,
        _valid_methodology_notes(),
        commentary,
    )

    assert result.passed is True


def test_matching_stress_loss_and_values_pass():
    commentary = (
        "Stress Scenario Analysis\n"
        "Combined selloff: portfolio loss 17.50%, stressed portfolio value 82.50, "
        "with the main contributions from QQQ (6.00%) and SPY (4.00%). "
        "Assumptions and limitations: deterministic proxy stress test only; not "
        "investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
        stress_results=_stress_results(),
    )

    assert result.passed is True
    assert any(
        check.name == "stress_result_consistency" and check.passed
        for check in result.checks
    )


def test_mismatched_stress_loss_fails():
    commentary = (
        "Stress Scenario Analysis: Combined selloff has a portfolio loss of 25.00% "
        "and stressed portfolio value of 82.50. Assumptions and limitations apply; "
        "not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
        stress_results=_stress_results(),
    )

    assert result.passed is False
    assert any(
        "portfolio loss mismatch: expected 17.50%, found 25.00%" in error
        for error in result.errors
    )


def test_mismatched_stressed_portfolio_value_fails():
    commentary = (
        "Under the Combined selloff stress scenario, portfolio loss is 17.50% and "
        "stressed portfolio value is 75.00. Assumptions and limitations apply; not "
        "investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
        stress_results=_stress_results(),
    )

    assert result.passed is False
    assert any(
        "stressed portfolio value mismatch: expected 82.50, found 75.00" in error
        for error in result.errors
    )


def test_mismatched_stress_ticker_contribution_fails():
    commentary = (
        "Stress Scenario Analysis: Combined selloff has a portfolio loss of 17.50%, "
        "stressed portfolio value of 82.50, and contributions from QQQ (9.00%) and "
        "SPY (4.00%). Assumptions and limitations apply; not investment advice."
    )

    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        commentary,
        stress_results=_stress_results(),
    )

    assert result.passed is False
    assert any(
        "QQQ contribution mismatch: expected 6.00%, found 9.00%" in error
        for error in result.errors
    )


def test_no_stress_results_do_not_affect_validation():
    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        _safe_commentary(),
        stress_results=[],
    )

    assert result.passed is True
    assert not result.warnings
    assert any(
        check.name == "stress_result_consistency" and check.passed
        for check in result.checks
    )


def test_stress_results_without_stress_commentary_produce_warning():
    result = validate_generated_report(
        _valid_parsed_portfolio(),
        _valid_risk_report(),
        _valid_methodology_notes(),
        _safe_commentary(),
        stress_results=_stress_results(),
    )

    assert result.passed is True
    assert "Stress results are available, but commentary omits stress analysis." in (
        result.warnings
    )
    assert any(
        check.name == "stress_result_consistency" and not check.passed
        for check in result.checks
    )
