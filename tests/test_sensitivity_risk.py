from __future__ import annotations

import pandas as pd
import pytest

from src.sensitivity_risk import (
    SensitivityRecord,
    aggregate_greeks,
    load_sensitivity_file,
    validate_sensitivity_file,
)


def test_load_sensitivity_csv(tmp_path):
    path = _write_sensitivity_csv(tmp_path)

    records = load_sensitivity_file(path)

    assert len(records) == 3
    assert records[0].portfolio_id == "RF-SENS-001"
    assert records[0].trade_id == "TRD-001"
    assert records[0].delta == 100.0
    assert records[0].currency == "USD"


def test_sensitivity_schema_validation(tmp_path):
    path = tmp_path / "bad_sensitivities.csv"
    pd.DataFrame({"trade_id": ["TRD-001"], "delta": [1.0]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        load_sensitivity_file(path)


def test_validate_sensitivity_file_rejects_duplicate_trade_ids():
    records = [
        _record("TRD-001", "SPY", 100.0, 10.0),
        _record("TRD-001", "QQQ", 50.0, 5.0),
    ]

    with pytest.raises(ValueError, match="Duplicate trade_id"):
        validate_sensitivity_file(records)


def test_aggregate_greeks_calculates_totals_and_concentrations():
    records = [
        _record("TRD-001", "SPY", 100.0, 10.0, risk_class="Equity", bucket="US Equity"),
        _record("TRD-002", "NVDA", -250.0, 80.0, risk_class="Equity", bucket="US Single Name"),
        _record("TRD-003", "USD 10Y", 50.0, 20.0, risk_class="Rates", bucket="USD Rates"),
    ]

    result = aggregate_greeks(records)

    assert result["total_delta"] == -100.0
    assert result["total_gamma"] == 6.0
    assert result["total_vega"] == 110.0
    assert result["total_theta"] == -3.0
    assert result["absolute_delta_by_risk_class"] == {
        "Equity": 350.0,
        "Rates": 50.0,
    }
    assert result["absolute_vega_by_bucket"]["US Single Name"] == 80.0
    assert result["largest_delta_risk_factor"] == {
        "risk_factor": "NVDA",
        "absolute_value": 250.0,
    }
    assert result["largest_vega_risk_factor"] == {
        "risk_factor": "NVDA",
        "absolute_value": 80.0,
    }
    assert result["warnings"] == []


def test_aggregate_greeks_warns_on_multiple_currencies():
    records = [
        _record("TRD-001", "SPY", 100.0, 10.0, currency="USD"),
        _record("TRD-002", "SX5E", 50.0, 20.0, currency="EUR"),
    ]

    result = aggregate_greeks(records)

    assert result["currencies"] == ["EUR", "USD"]
    assert "Multiple currencies" in result["warnings"][0]


def _write_sensitivity_csv(tmp_path):
    path = tmp_path / "sensitivities.csv"
    pd.DataFrame(
        [
            _record("TRD-001", "SPY", 100.0, 10.0).__dict__,
            _record("TRD-002", "NVDA", -250.0, 80.0).__dict__,
            _record("TRD-003", "USD 10Y", 50.0, 20.0, risk_class="Rates").__dict__,
        ]
    ).to_csv(path, index=False)
    return path


def _record(
    trade_id: str,
    risk_factor: str,
    delta: float,
    vega: float,
    risk_class: str = "Equity",
    bucket: str = "US Equity",
    currency: str = "USD",
) -> SensitivityRecord:
    return SensitivityRecord(
        portfolio_id="RF-SENS-001",
        book="Derivatives",
        trade_id=trade_id,
        instrument_type="Option",
        risk_class=risk_class,
        risk_factor=risk_factor,
        bucket=bucket,
        delta=delta,
        gamma=2.0,
        vega=vega,
        theta=-1.0,
        currency=currency,
    )
