"""Compatibility wrapper for src.core.risk_config. New code should import from src.core.risk_config."""

from src.core.risk_config import (
    MarketDataConfig,
    ReportingConfig,
    ReturnsConfig,
    RiskConfig,
    RiskMetricsConfig,
    StressScenario,
    VarConfig,
    load_risk_config,
    parse_stress_scenarios,
)

__all__ = [
    "MarketDataConfig",
    "ReportingConfig",
    "ReturnsConfig",
    "RiskConfig",
    "RiskMetricsConfig",
    "StressScenario",
    "VarConfig",
    "load_risk_config",
    "parse_stress_scenarios",
]
