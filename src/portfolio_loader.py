"""Compatibility wrapper for src.data.portfolio_loader. New code should import from src.data.portfolio_loader."""

from src.data.portfolio_loader import (
    EXPOSURE_PROFILE_COLUMNS,
    MARKET_PORTFOLIO_COLUMNS,
    ExposureProfile,
    ExposureProfileRow,
    detect_file_schema,
    load_portfolio_file,
)

__all__ = [
    "EXPOSURE_PROFILE_COLUMNS",
    "MARKET_PORTFOLIO_COLUMNS",
    "ExposureProfile",
    "ExposureProfileRow",
    "detect_file_schema",
    "load_portfolio_file",
]
