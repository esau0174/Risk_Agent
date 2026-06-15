import numpy as np
import pandas as pd
import pytest

from src.data.portfolio import (
    calculate_asset_returns,
    calculate_cumulative_returns,
    calculate_portfolio_returns,
    validate_weights,
)


def test_validate_weights_rejects_length_mismatch():
    with pytest.raises(ValueError, match="must match"):
        validate_weights(["SPY", "QQQ"], [1.0])


def test_validate_weights_rejects_weights_not_summing_to_one():
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_weights(["SPY", "QQQ"], [0.6, 0.5])


def test_validate_weights_returns_numpy_array():
    weights = validate_weights(["SPY", "QQQ"], [0.6, 0.4])

    assert isinstance(weights, np.ndarray)
    np.testing.assert_allclose(weights, np.array([0.6, 0.4]))


def test_calculate_asset_returns_uses_daily_percentage_returns():
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 110.0, 121.0],
            "QQQ": [200.0, 180.0, 198.0],
        }
    )

    returns = calculate_asset_returns(prices)

    expected = pd.DataFrame(
        {
            "SPY": [0.10, 0.10],
            "QQQ": [-0.10, 0.10],
        },
        index=[1, 2],
    )
    pd.testing.assert_frame_equal(returns, expected)


def test_calculate_portfolio_returns_uses_weighted_sum():
    asset_returns = pd.DataFrame(
        {
            "SPY": [0.01, -0.02, 0.03],
            "QQQ": [0.02, 0.01, -0.01],
        }
    )

    portfolio_returns = calculate_portfolio_returns(asset_returns, [0.75, 0.25])

    expected = pd.Series(
        [0.0125, -0.0125, 0.02],
        name="portfolio_return",
    )
    pd.testing.assert_series_equal(portfolio_returns, expected)


def test_calculate_cumulative_returns_compounds_returns():
    returns = pd.Series([0.10, -0.10, 0.05])

    cumulative = calculate_cumulative_returns(returns)

    expected = pd.Series([0.10, -0.01, 0.0395], name="cumulative_return")
    pd.testing.assert_series_equal(cumulative, expected)
