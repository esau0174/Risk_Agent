"""Compatibility wrapper for src.data.market_data. New code should import from src.data.market_data."""

from src.data.market_data import download_price_data

__all__ = ["download_price_data"]
