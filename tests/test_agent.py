from src.agent import _build_commentary_facts, generate_risk_commentary


def test_build_commentary_facts_includes_largest_weight_and_composition_notes():
    risk_report = {
        "metadata": {
            "tickers": ["SPY", "QQQ", "NVDA", "TLT"],
            "weights": [0.4, 0.3, 0.2, 0.1],
            "start_date": "2023-01-01",
            "end_date": None,
            "confidence_level": 0.95,
        },
        "risk_metrics": {
            "annualized_volatility": 0.25,
            "historical_var": 0.02,
            "expected_shortfall": 0.03,
            "max_drawdown": 0.2,
        },
        "latest_cumulative_return": 0.5,
        "number_of_observations": 100,
    }

    methodology = [
        {
            "title": "Historical VaR",
            "path": "docs/historical_var.md",
            "content": "VaR methodology.",
            "score": 10,
        }
    ]

    facts = _build_commentary_facts(risk_report, methodology)
    notes = " ".join(facts["composition_notes"])

    assert facts["largest_weight_concentration"] == {"ticker": "SPY", "weight": 0.4}
    assert "QQQ and NVDA" in notes
    assert "growth, technology, and AI-related exposure" in notes
    assert "TLT may provide diversification" in notes
    assert "formal factor model" in notes
    assert facts["retrieved_methodology"][0]["title"] == "Historical VaR"
    assert facts["risk_metrics_display"]["historical_var"] == "2.00%"


def test_fallback_commentary_includes_formatted_metrics_and_stress_results():
    risk_report = {
        "metadata": {
            "tickers": ["SPY", "QQQ", "NVDA", "TLT"],
            "weights": [0.4, 0.3, 0.2, 0.1],
            "start_date": "2023-01-01",
            "end_date": None,
            "confidence_level": 0.95,
        },
        "risk_metrics": {
            "annualized_volatility": 0.2662,
            "historical_var": 0.0232,
            "expected_shortfall": 0.0347,
            "max_drawdown": 0.2377,
        },
        "latest_cumulative_return": 0.5,
        "number_of_observations": 100,
    }
    stress_results = [
        {
            "scenario_name": "Combined selloff",
            "base_portfolio_value": 100.0,
            "stressed_portfolio_value": 82.5,
            "portfolio_loss_pct": 0.175,
            "per_ticker_contributions": {
                "SPY": {"portfolio_loss_contribution_pct": 0.04},
                "QQQ": {"portfolio_loss_contribution_pct": 0.06},
                "NVDA": {"portfolio_loss_contribution_pct": 0.06},
                "TLT": {"portfolio_loss_contribution_pct": 0.015},
            },
            "assumptions": [],
        }
    ]

    commentary = generate_risk_commentary(
        "Analyze the portfolio.",
        risk_report,
        [],
        use_llm=False,
        stress_results=stress_results,
    )

    assert "95% historical VaR is 2.32%" in commentary
    assert "Expected Shortfall is 3.47%" in commentary
    assert "Maximum drawdown is 23.77%" in commentary
    assert "Stress Scenario Analysis" in commentary
    assert "Combined selloff" in commentary
    assert "portfolio loss 17.50%" in commentary
    assert "stressed portfolio value 82.50" in commentary
    assert "NVDA (6.00%)" in commentary
    assert "deterministic proxy stress test, not a full factor model" in commentary
