from __future__ import annotations

import json

import pandas as pd
import pytest

from src.portfolio_loader import load_portfolio_file
from src.tool_executor import ToolExecutor


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
