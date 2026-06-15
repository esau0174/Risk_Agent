from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_FREQUENCIES = {"daily"}
SUPPORTED_VAR_METHODS = {"historical"}
SUPPORTED_RISK_METRICS = {
    "annualized_volatility",
    "historical_var",
    "expected_shortfall",
    "max_drawdown",
    "concentration",
}


@dataclass(frozen=True)
class MarketDataConfig:
    start_date: str = "2023-01-01"
    end_date: str | None = None


@dataclass(frozen=True)
class ReturnsConfig:
    frequency: str = "daily"
    annualization_factor: int = 252


@dataclass(frozen=True)
class VarConfig:
    confidence_level: float = 0.95
    method: str = "historical"


@dataclass(frozen=True)
class RiskMetricsConfig:
    enabled: tuple[str, ...] = (
        "annualized_volatility",
        "historical_var",
        "expected_shortfall",
        "max_drawdown",
        "concentration",
    )


@dataclass(frozen=True)
class ReportingConfig:
    include_methodology_notes: bool = True
    include_llm_commentary: bool = True
    validate_commentary: bool = True


@dataclass(frozen=True)
class StressScenario:
    name: str
    equity_selloff_pct: float
    tech_selloff_pct: float
    rates_shock_bps: float


@dataclass(frozen=True)
class RiskConfig:
    """Validated calculation and reporting assumptions for a risk workflow."""

    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    returns: ReturnsConfig = field(default_factory=ReturnsConfig)
    var: VarConfig = field(default_factory=VarConfig)
    risk_metrics: RiskMetricsConfig = field(default_factory=RiskMetricsConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    stress_scenarios: tuple[StressScenario, ...] = ()
    credit_limits: dict[str, float] = field(default_factory=dict)


def load_risk_config(config_file: str | None = None) -> RiskConfig:
    """Load a validated JSON risk config or return documented defaults."""
    if config_file is None:
        return RiskConfig()

    path = Path(config_file)
    if not path.exists():
        raise ValueError(f"Risk config file does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Risk config JSON is invalid: {exc.msg}.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Risk config JSON must contain an object.")

    market_data = _config_section(payload, "market_data")
    returns = _config_section(payload, "returns")
    var = _config_section(payload, "var")
    risk_metrics = _config_section(payload, "risk_metrics")
    reporting = _config_section(payload, "reporting")
    stress_scenarios = parse_stress_scenarios(payload.get("stress_scenarios", []))
    credit_limits = _parse_credit_limits(payload.get("credit_limits", {}))

    enabled_value = risk_metrics.get("enabled")
    if enabled_value is None:
        metric_flags = {
            name: enabled
            for name, enabled in risk_metrics.items()
            if name in SUPPORTED_RISK_METRICS
        }
        enabled_value = metric_flags or None
    unknown_metric_options = set(risk_metrics) - SUPPORTED_RISK_METRICS - {"enabled"}
    if unknown_metric_options:
        raise ValueError(
            "Unsupported risk_metrics options: "
            + ", ".join(sorted(unknown_metric_options))
            + "."
        )
    enabled_metrics = _parse_enabled_metrics(enabled_value)
    config = RiskConfig(
        market_data=MarketDataConfig(
            start_date=str(market_data.get("start_date", "2023-01-01")),
            end_date=_optional_string(market_data.get("end_date")),
        ),
        returns=ReturnsConfig(
            frequency=str(returns.get("frequency", "daily")).lower(),
            annualization_factor=_positive_integer(
                returns.get("annualization_factor", 252),
                "returns.annualization_factor",
            ),
        ),
        var=VarConfig(
            confidence_level=_confidence_level(var.get("confidence_level", 0.95)),
            method=str(var.get("method", "historical")).lower(),
        ),
        risk_metrics=RiskMetricsConfig(enabled=enabled_metrics),
        reporting=ReportingConfig(
            include_methodology_notes=_boolean(
                reporting.get("include_methodology_notes", True),
                "reporting.include_methodology_notes",
            ),
            include_llm_commentary=_boolean(
                reporting.get("include_llm_commentary", True),
                "reporting.include_llm_commentary",
            ),
            validate_commentary=_boolean(
                reporting.get("validate_commentary", True),
                "reporting.validate_commentary",
            ),
        ),
        stress_scenarios=stress_scenarios,
        credit_limits=credit_limits,
    )
    _validate_config(config)
    return config


def _validate_config(config: RiskConfig) -> None:
    if config.returns.frequency not in SUPPORTED_FREQUENCIES:
        supported = ", ".join(sorted(SUPPORTED_FREQUENCIES))
        raise ValueError(
            f"Unsupported returns frequency '{config.returns.frequency}'. "
            f"Supported values: {supported}."
        )

    if config.var.method not in SUPPORTED_VAR_METHODS:
        supported = ", ".join(sorted(SUPPORTED_VAR_METHODS))
        raise ValueError(
            f"Unsupported VaR method '{config.var.method}'. Supported values: {supported}."
        )


def _config_section(payload: dict, name: str) -> dict:
    section = payload.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"Risk config section '{name}' must be an object.")
    return section


def _parse_enabled_metrics(value) -> tuple[str, ...]:
    if value is None:
        return RiskMetricsConfig().enabled

    if isinstance(value, dict):
        invalid_flags = [name for name, enabled in value.items() if not isinstance(enabled, bool)]
        if invalid_flags:
            raise ValueError(
                "Risk metric flags must be boolean for: " + ", ".join(invalid_flags) + "."
            )
        metrics = [name for name, enabled in value.items() if enabled]
    elif isinstance(value, list):
        metrics = value
    else:
        raise ValueError("risk_metrics.enabled must be a list or an object of boolean flags.")

    normalized = tuple(str(metric).strip().lower() for metric in metrics)
    invalid = sorted(set(normalized) - SUPPORTED_RISK_METRICS)
    if invalid:
        raise ValueError("Unsupported enabled risk metrics: " + ", ".join(invalid) + ".")

    return normalized


def parse_stress_scenarios(value) -> tuple[StressScenario, ...]:
    """Normalize and validate stress scenario dictionaries or dataclasses."""
    if not isinstance(value, (list, tuple)):
        raise ValueError("stress_scenarios must be a list.")

    scenarios = []
    for index, scenario in enumerate(value, start=1):
        field_prefix = f"stress_scenarios[{index - 1}]"
        if isinstance(scenario, StressScenario):
            scenario = {
                "name": scenario.name,
                "equity_selloff_pct": scenario.equity_selloff_pct,
                "tech_selloff_pct": scenario.tech_selloff_pct,
                "rates_shock_bps": scenario.rates_shock_bps,
            }
        if not isinstance(scenario, dict):
            raise ValueError(f"{field_prefix} must be an object.")

        required_fields = {
            "name",
            "equity_selloff_pct",
            "tech_selloff_pct",
            "rates_shock_bps",
        }
        missing_fields = sorted(required_fields - set(scenario))
        if missing_fields:
            raise ValueError(
                f"{field_prefix} is missing required fields: "
                + ", ".join(missing_fields)
                + "."
            )

        name = scenario["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{field_prefix}.name must be a non-empty string.")

        scenarios.append(
            StressScenario(
                name=name.strip(),
                equity_selloff_pct=_bounded_number(
                    scenario["equity_selloff_pct"],
                    f"{field_prefix}.equity_selloff_pct",
                    minimum=0.0,
                    maximum=1.0,
                ),
                tech_selloff_pct=_bounded_number(
                    scenario["tech_selloff_pct"],
                    f"{field_prefix}.tech_selloff_pct",
                    minimum=0.0,
                    maximum=1.0,
                ),
                rates_shock_bps=_bounded_number(
                    scenario["rates_shock_bps"],
                    f"{field_prefix}.rates_shock_bps",
                    minimum=-1000.0,
                    maximum=1000.0,
                ),
            )
        )

    return tuple(scenarios)


def _parse_credit_limits(value) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("credit_limits must be an object mapping netting sets to limits.")

    limits = {}
    for netting_set, limit in value.items():
        key = str(netting_set).strip()
        if not key:
            raise ValueError("credit_limits netting set names must be non-empty.")
        limits[key] = _bounded_number(
            limit,
            f"credit_limits.{key}",
            minimum=0.0,
            maximum=math.inf,
        )
        if limits[key] == 0:
            raise ValueError(f"credit_limits.{key} must be greater than 0.")
    return limits


def _confidence_level(value) -> float:
    try:
        confidence_level = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("var.confidence_level must be numeric.") from exc

    if not 0 < confidence_level < 1:
        raise ValueError("var.confidence_level must be between 0 and 1.")

    return confidence_level


def _bounded_number(value, field_name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(
            f"{field_name} must be between {minimum:g} and {maximum:g}."
        )
    return number


def _positive_integer(value, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer.")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer.") from exc
    if integer <= 0 or float(value) != integer:
        raise ValueError(f"{field_name} must be a positive integer.")
    return integer


def _boolean(value, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be true or false.")
    return value


def _optional_string(value) -> str | None:
    if value is None:
        return None
    return str(value)
