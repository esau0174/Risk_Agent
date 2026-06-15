"""Compatibility wrapper for src.data.portfolio. New code should import from src.data.portfolio."""

from src.data.portfolio import (
    calculate_asset_returns,
    calculate_cumulative_returns,
    calculate_portfolio_returns,
    validate_weights,
)

__all__ = [
    "calculate_asset_returns",
    "calculate_cumulative_returns",
    "calculate_portfolio_returns",
    "validate_weights",
]
