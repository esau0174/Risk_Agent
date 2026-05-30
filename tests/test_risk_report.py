from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src import risk_report


def test_generate_portfolio_risk_report_uses_synthetic_price_data(monkeypatch):
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 110.0, 99.0, 108.9],
            "QQQ": [200.0, 190.0, 199.5, 209.475],
        },
        index=pd.date_range("2023-01-01", periods=4),
    )

    def fake_download_price_data(tickers, start_date, end_date=None):
        assert tickers == ["SPY", "QQQ"]
        assert start_date == "2023-01-01"
        assert end_date == "2023-01-04"
        return prices

    monkeypatch.setattr(risk_report, "download_price_data", fake_download_price_data)

    report = risk_report.generate_portfolio_risk_report(
        ["SPY", "QQQ"],
        [0.6, 0.4],
        "2023-01-01",
        end_date="2023-01-04",
        confidence_level=0.95,
    )

    assert report["metadata"] == {
        "tickers": ["SPY", "QQQ"],
        "weights": [0.6, 0.4],
        "start_date": "2023-01-01",
        "end_date": "2023-01-04",
        "confidence_level": 0.95,
    }
    assert report["number_of_observations"] == 3
    expected_portfolio_returns = pd.Series([0.04, -0.04, 0.08])

    assert report["latest_cumulative_return"] == pytest.approx(0.078272)
    assert report["risk_metrics"]["annualized_volatility"] == pytest.approx(
        expected_portfolio_returns.std() * (252**0.5)
    )
    assert report["risk_metrics"]["historical_var"] > 0
    assert report["risk_metrics"]["expected_shortfall"] > 0
    assert report["risk_metrics"]["max_drawdown"] > 0
    assert set(report["correlation_matrix"]) == {"SPY", "QQQ"}
    assert set(report["correlation_matrix"]["SPY"]) == {"SPY", "QQQ"}
    assert datetime.fromisoformat(report["analysis_timestamp"])


def test_generate_portfolio_risk_report_does_not_call_yfinance_directly(monkeypatch):
    called = False

    def fake_download_price_data(tickers, start_date, end_date=None):
        nonlocal called
        called = True
        return pd.DataFrame({"SPY": [100.0, 101.0], "QQQ": [100.0, 102.0]})

    monkeypatch.setattr(risk_report, "download_price_data", fake_download_price_data)

    report = risk_report.generate_portfolio_risk_report(
        ["SPY", "QQQ"],
        [0.5, 0.5],
        "2023-01-01",
    )

    assert called is True
    assert report["number_of_observations"] == 1
