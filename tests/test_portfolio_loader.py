from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data.portfolio_loader import (
    ExposureProfile,
    detect_file_schema,
    load_portfolio_file,
)
from src.core.tool_executor import ToolExecutor


EXPECTED_PORTFOLIO = {
    "tickers": ["SPY", "QQQ", "NVDA", "TLT"],
    "weights": [0.4, 0.3, 0.2, 0.1],
}


def test_load_portfolio_from_csv(tmp_path):
    path = tmp_path / "portfolio.csv"
    pd.DataFrame(
        {"ticker": ["spy", "qqq", "nvda", "tlt"], "weight": [0.4, 0.3, 0.2, 0.1]}
    ).to_csv(path, index=False)

    assert load_portfolio_file(path) == EXPECTED_PORTFOLIO


def test_load_portfolio_from_excel(tmp_path):
    path = tmp_path / "portfolio.xlsx"
    pd.DataFrame(
        {"Ticker": ["spy", "qqq", "nvda", "tlt"], "Weight": [40, 30, 20, 10]}
    ).to_excel(path, index=False)

    assert load_portfolio_file(path) == EXPECTED_PORTFOLIO


def test_load_portfolio_from_json(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text(
        json.dumps(
            [
                {"ticker": "spy", "weight": 0.4},
                {"ticker": "qqq", "weight": 0.3},
                {"ticker": "nvda", "weight": 0.2},
                {"ticker": "tlt", "weight": 0.1},
            ]
        ),
        encoding="utf-8",
    )

    assert load_portfolio_file(path) == EXPECTED_PORTFOLIO


def test_percentage_weight_strings_are_normalized(tmp_path):
    path = tmp_path / "portfolio.csv"
    pd.DataFrame(
        {"ticker": ["SPY", "QQQ", "NVDA", "TLT"], "weight": ["40%", "30%", "20%", "10%"]}
    ).to_csv(path, index=False)

    assert load_portfolio_file(path) == EXPECTED_PORTFOLIO


def test_richer_market_portfolio_schema_preserves_metadata(tmp_path):
    path = tmp_path / "institutional_portfolio.csv"
    pd.DataFrame(
        {
            "portfolio_id": ["RF-MKT-001", "RF-MKT-001"],
            "book": ["Global Macro", "Global Macro"],
            "ticker": ["SPY", "QQQ"],
            "asset_class": ["Equity ETF", "Equity ETF"],
            "risk_bucket": ["Broad Equity", "Growth / Technology"],
            "region": ["US", "US"],
            "weight": ["60%", "40%"],
            "notional_usd": [6_000_000, 4_000_000],
        }
    ).to_csv(path, index=False)

    result = load_portfolio_file(path)

    assert result["tickers"] == ["SPY", "QQQ"]
    assert result["weights"] == [0.6, 0.4]
    assert result["metadata"]["portfolio_id"] == "RF-MKT-001"
    assert result["metadata"]["book"] == "Global Macro"
    assert result["metadata"]["asset_classes"] == ["Equity ETF"]
    assert result["metadata"]["risk_buckets"] == [
        "Broad Equity",
        "Growth / Technology",
    ]
    assert result["metadata"]["regions"] == ["US"]
    assert result["metadata"]["total_notional_usd"] == 10_000_000.0
    assert result["metadata"]["holdings"][0]["notional_usd"] == 6_000_000.0


def test_missing_required_columns_raise_clear_error(tmp_path):
    path = tmp_path / "portfolio.csv"
    pd.DataFrame({"ticker": ["SPY"], "allocation": [1.0]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required columns: weight"):
        load_portfolio_file(path)


def test_invalid_weights_raise_clear_error(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text(
        json.dumps(
            [
                {"ticker": "SPY", "weight": 0.7},
                {"ticker": "QQQ", "weight": 0.4},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid portfolio weights"):
        load_portfolio_file(path)


def test_tool_executor_loads_portfolio_file(tmp_path):
    path = tmp_path / "portfolio.csv"
    pd.DataFrame(
        {"ticker": ["SPY", "QQQ"], "weight": [60, 40]}
    ).to_csv(path, index=False)

    result = ToolExecutor().execute("load_portfolio_file", path)

    assert result.status == "success"
    assert result.output == {"tickers": ["SPY", "QQQ"], "weights": [0.6, 0.4]}
    assert result.metadata["callable_name"] == "src.portfolio_loader.load_portfolio_file"


def test_load_exposure_profile_from_csv(tmp_path):
    path = tmp_path / "exposure_profile.csv"
    pd.DataFrame(
        {
            "netting_set": ["NS-001", "NS-001"],
            "time_years": [0.0, 1.0],
            "expected_exposure": [1_000_000, 1_200_000],
            "pfe_95": [1_500_000, 1_800_000],
            "pfe_99": [1_900_000, 2_200_000],
            "currency": ["USD", "USD"],
            "counterparty": ["Bank A", "Bank A"],
        }
    ).to_csv(path, index=False)

    profile = load_portfolio_file(path)

    assert isinstance(profile, ExposureProfile)
    assert len(profile.exposures) == 2
    assert profile.exposures[0].netting_set == "NS-001"
    assert profile.exposures[0].time_years == 0.0
    assert profile.exposures[0].expected_exposure == 1_000_000
    assert profile.exposures[0].pfe_95 == 1_500_000
    assert profile.exposures[0].pfe_99 == 1_900_000
    assert profile.exposures[0].currency == "USD"
    assert profile.exposures[0].counterparty == "Bank A"


def test_negative_exposure_is_rejected(tmp_path):
    path = tmp_path / "exposure_profile.csv"
    pd.DataFrame(
        {
            "netting_set": ["NS-001"],
            "time_years": [1.0],
            "expected_exposure": [-1.0],
            "pfe_95": [100.0],
        }
    ).to_csv(path, index=False)

    with pytest.raises(
        ValueError,
        match="expected_exposure in row 1 must be non-negative",
    ):
        load_portfolio_file(path)


def test_pfe_99_below_pfe_95_is_rejected(tmp_path):
    path = tmp_path / "exposure_profile.csv"
    pd.DataFrame(
        {
            "netting_set": ["NS-001"],
            "time_years": [1.0],
            "expected_exposure": [50.0],
            "pfe_95": [100.0],
            "pfe_99": [90.0],
        }
    ).to_csv(path, index=False)

    with pytest.raises(
        ValueError,
        match="pfe_99 in row 1 must be greater than or equal to pfe_95",
    ):
        load_portfolio_file(path)


def test_schema_detection_distinguishes_supported_file_types():
    assert detect_file_schema(["ticker", "weight"]) == "market_portfolio"
    assert detect_file_schema(
        ["netting_set", "time_years", "expected_exposure", "pfe_95"]
    ) == "exposure_profile"


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("netting_set", "", "netting_set is missing in row 1"),
        ("time_years", -0.1, "time_years in row 1 must be non-negative"),
        ("pfe_95", "not-a-number", "pfe_95 in row 1 must be numeric"),
        ("pfe_99", -1, "pfe_99 in row 1 must be non-negative"),
    ],
)
def test_exposure_profile_field_validation(tmp_path, column, value, message):
    row = {
        "netting_set": "NS-001",
        "time_years": 1.0,
        "expected_exposure": 50.0,
        "pfe_95": 100.0,
        "pfe_99": 120.0,
    }
    row[column] = value
    path = tmp_path / "exposure_profile.csv"
    pd.DataFrame([row]).to_csv(path, index=False)

    with pytest.raises(ValueError, match=message):
        load_portfolio_file(path)
