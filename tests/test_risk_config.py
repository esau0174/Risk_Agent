from __future__ import annotations

import json

import pytest

from src.risk_config import load_risk_config


def test_load_default_risk_config():
    config = load_risk_config()

    assert config.market_data.start_date == "2023-01-01"
    assert config.market_data.end_date is None
    assert config.returns.frequency == "daily"
    assert config.returns.annualization_factor == 252
    assert config.var.confidence_level == 0.95
    assert config.var.method == "historical"
    assert "historical_var" in config.risk_metrics.enabled
    assert config.reporting.validate_commentary is True


def test_load_json_risk_config(tmp_path):
    path = tmp_path / "risk_config.json"
    path.write_text(
        json.dumps(
            {
                "market_data": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
                "returns": {"frequency": "daily", "annualization_factor": 250},
                "var": {"confidence_level": 0.99, "method": "historical"},
                "risk_metrics": {
                    "enabled": {
                        "annualized_volatility": True,
                        "historical_var": True,
                        "expected_shortfall": False,
                        "max_drawdown": True,
                        "concentration": False,
                    }
                },
                "reporting": {
                    "include_methodology_notes": False,
                    "include_llm_commentary": False,
                    "validate_commentary": False,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_risk_config(str(path))

    assert config.market_data.start_date == "2024-01-01"
    assert config.market_data.end_date == "2024-12-31"
    assert config.returns.annualization_factor == 250
    assert config.var.confidence_level == 0.99
    assert config.risk_metrics.enabled == (
        "annualized_volatility",
        "historical_var",
        "max_drawdown",
    )
    assert config.reporting.include_methodology_notes is False


def test_invalid_confidence_level_is_rejected(tmp_path):
    path = tmp_path / "risk_config.json"
    path.write_text('{"var": {"confidence_level": 1.2}}', encoding="utf-8")

    with pytest.raises(ValueError, match="confidence_level must be between 0 and 1"):
        load_risk_config(str(path))


def test_unsupported_var_method_is_rejected(tmp_path):
    path = tmp_path / "risk_config.json"
    path.write_text('{"var": {"method": "parametric"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported VaR method 'parametric'"):
        load_risk_config(str(path))


def test_unsupported_frequency_and_metric_are_rejected(tmp_path):
    frequency_path = tmp_path / "frequency.json"
    frequency_path.write_text('{"returns": {"frequency": "weekly"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported returns frequency 'weekly'"):
        load_risk_config(str(frequency_path))

    metric_path = tmp_path / "metric.json"
    metric_path.write_text(
        '{"risk_metrics": {"enabled": ["historical_var", "beta"]}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsupported enabled risk metrics: beta"):
        load_risk_config(str(metric_path))


def test_direct_boolean_metric_flags_are_supported(tmp_path):
    path = tmp_path / "risk_config.json"
    path.write_text(
        json.dumps(
            {
                "risk_metrics": {
                    "annualized_volatility": True,
                    "historical_var": True,
                    "expected_shortfall": False,
                    "max_drawdown": False,
                    "concentration": True,
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_risk_config(str(path))

    assert config.risk_metrics.enabled == (
        "annualized_volatility",
        "historical_var",
        "concentration",
    )
