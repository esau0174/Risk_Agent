from __future__ import annotations

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
