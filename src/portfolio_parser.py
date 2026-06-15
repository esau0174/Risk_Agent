"""Compatibility wrapper for src.data.portfolio_parser. New code should import from src.data.portfolio_parser."""

from src.data.portfolio_parser import parse_portfolio_text

__all__ = ["parse_portfolio_text"]
