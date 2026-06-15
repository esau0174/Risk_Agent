from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.market_risk import risk_report
from src.risk_config import (
    MarketDataConfig,
    ReturnsConfig,
    RiskConfig,
    RiskMetricsConfig,
    VarConfig,
)


def test_legacy_risk_report_import_remains_compatible():
    from src.risk_report import generate_portfolio_risk_report as legacy_generate

    assert legacy_generate is risk_report.generate_portfolio_risk_report


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


def test_generate_portfolio_risk_report_uses_risk_config(monkeypatch):
    prices = pd.DataFrame(
        {"SPY": [100.0, 102.0, 101.0], "QQQ": [100.0, 101.0, 103.0]}
    )

    def fake_download_price_data(tickers, start_date, end_date=None):
        assert start_date == "2024-01-01"
        assert end_date == "2024-12-31"
        return prices

    monkeypatch.setattr(risk_report, "download_price_data", fake_download_price_data)
    config = RiskConfig(
        market_data=MarketDataConfig("2024-01-01", "2024-12-31"),
        returns=ReturnsConfig("daily", 250),
        var=VarConfig(0.99, "historical"),
        risk_metrics=RiskMetricsConfig(
            ("annualized_volatility", "historical_var")
        ),
    )

    report = risk_report.generate_portfolio_risk_report(
        ["SPY", "QQQ"],
        [0.5, 0.5],
        "ignored-by-config",
        risk_config=config,
    )

    assert set(report["risk_metrics"]) == {
        "annualized_volatility",
        "historical_var",
    }
    assert report["metadata"]["confidence_level"] == 0.99
    assert report["metadata"]["annualization_factor"] == 250
    assert report["metadata"]["enabled_risk_metrics"] == [
        "annualized_volatility",
        "historical_var",
    ]
