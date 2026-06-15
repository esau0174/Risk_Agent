"""Compatibility wrapper for src.market_risk.risk_report. New code should import from src.market_risk.risk_report."""

from src.market_risk.risk_report import generate_portfolio_risk_report

__all__ = ["generate_portfolio_risk_report"]
