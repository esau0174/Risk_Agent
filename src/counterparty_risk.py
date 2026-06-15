"""Compatibility wrapper for src.credit_risk.counterparty_risk. New code should import from src.credit_risk.counterparty_risk."""

from src.credit_risk.counterparty_risk import calculate_pfe_metrics

__all__ = ["calculate_pfe_metrics"]
