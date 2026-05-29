from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        raise ValueError("Returns must not be empty.")

    clean_returns = returns.dropna()
    if clean_returns.empty:
        raise ValueError("Returns must contain at least one non-missing value.")

    return clean_returns


def annualized_volatility(returns: pd.Series, trading_days: int = 252) -> float:
    """Calculate annualized volatility from daily returns."""
    if trading_days <= 0:
        raise ValueError("Trading days must be greater than zero.")

    clean_returns = _validate_returns(returns)
    return float(clean_returns.std() * np.sqrt(trading_days))


def historical_var(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """Calculate historical Value at Risk as a positive loss magnitude."""
    _validate_confidence_level(confidence_level)
    clean_returns = _validate_returns(returns)

    percentile = 1 - confidence_level
    threshold_return = clean_returns.quantile(percentile)
    return float(max(-threshold_return, 0.0))


def expected_shortfall(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """Calculate Expected Shortfall as a positive loss magnitude."""
    _validate_confidence_level(confidence_level)
    clean_returns = _validate_returns(returns)

    threshold_return = clean_returns.quantile(1 - confidence_level)
    tail_returns = clean_returns[clean_returns <= threshold_return]

    if tail_returns.empty:
        raise ValueError("No tail returns available to calculate Expected Shortfall.")

    return float(max(-tail_returns.mean(), 0.0))


def max_drawdown(cumulative_returns: pd.Series) -> float:
    """Calculate maximum drawdown as a positive loss magnitude."""
    if cumulative_returns.empty:
        raise ValueError("Cumulative returns must not be empty.")

    clean_cumulative = cumulative_returns.dropna()
    if clean_cumulative.empty:
        raise ValueError("Cumulative returns must contain at least one non-missing value.")

    wealth_index = 1 + clean_cumulative
    running_peak = wealth_index.cummax()
    drawdowns = wealth_index / running_peak - 1
    return float(abs(drawdowns.min()))


def correlation_matrix(asset_returns: pd.DataFrame) -> pd.DataFrame:
    """Calculate the asset return correlation matrix."""
    if asset_returns.empty:
        raise ValueError("Asset returns must not be empty.")

    return asset_returns.corr()


def _validate_confidence_level(confidence_level: float) -> None:
    if not 0 < confidence_level < 1:
        raise ValueError("Confidence level must be between 0 and 1.")
