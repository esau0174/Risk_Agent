from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def validate_weights(
    tickers: Sequence[str],
    weights: Sequence[float],
    tolerance: float = 1e-6,
) -> np.ndarray:
    """Validate portfolio weights and return them as a numpy array."""
    ticker_list = list(tickers)
    weight_array = np.asarray(weights, dtype=float)

    if len(ticker_list) == 0:
        raise ValueError("At least one ticker is required.")

    if weight_array.ndim != 1:
        raise ValueError("Weights must be a one-dimensional sequence.")

    if len(ticker_list) != len(weight_array):
        raise ValueError(
            f"Number of tickers ({len(ticker_list)}) must match number of weights ({len(weight_array)})."
        )

    if not np.all(np.isfinite(weight_array)):
        raise ValueError("Weights must contain only finite numeric values.")

    weight_sum = weight_array.sum()
    if not np.isclose(weight_sum, 1.0, atol=tolerance):
        raise ValueError(f"Weights must sum to 1.0; received sum {weight_sum:.8f}.")

    return weight_array


def calculate_asset_returns(price_data: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily percentage returns from asset price data."""
    if price_data.empty:
        raise ValueError("Price data must not be empty.")

    returns = price_data.pct_change().dropna(how="all")

    if returns.empty:
        raise ValueError("Price data must contain enough observations to calculate returns.")

    return returns


def calculate_portfolio_returns(
    asset_returns: pd.DataFrame,
    weights: Sequence[float],
) -> pd.Series:
    """Calculate weighted daily portfolio returns."""
    if asset_returns.empty:
        raise ValueError("Asset returns must not be empty.")

    weight_array = validate_weights(list(asset_returns.columns), weights)
    portfolio_returns = asset_returns.dot(weight_array)
    portfolio_returns.name = "portfolio_return"
    return portfolio_returns


def calculate_cumulative_returns(portfolio_returns: pd.Series) -> pd.Series:
    """Calculate cumulative portfolio returns."""
    if portfolio_returns.empty:
        raise ValueError("Portfolio returns must not be empty.")

    cumulative_returns = (1 + portfolio_returns).cumprod() - 1
    cumulative_returns.name = "cumulative_return"
    return cumulative_returns
