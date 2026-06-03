from src.agent import _build_commentary_facts


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
