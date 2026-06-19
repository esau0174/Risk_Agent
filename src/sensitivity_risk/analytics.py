"""Aggregation of supplied sensitivity/Greeks records.

RiskFlow Agent consumes precomputed Greeks from an upstream pricing or risk
engine. It validates and aggregates those records, but does not calculate
pricing-model Greeks.
"""

from __future__ import annotations

from collections import defaultdict

from src.sensitivity_risk.loader import SensitivityRecord
from src.sensitivity_risk.validator import validate_sensitivity_file


def aggregate_greeks(records: list[SensitivityRecord]) -> dict:
    """Aggregate supplied Greeks without calculating pricing-model sensitivities."""
    validated_records = validate_sensitivity_file(records)

    total_delta = sum(record.delta for record in validated_records)
    total_gamma = sum(record.gamma for record in validated_records)
    total_vega = sum(record.vega for record in validated_records)
    total_theta = sum(record.theta for record in validated_records)

    absolute_delta_by_risk_class = defaultdict(float)
    absolute_vega_by_bucket = defaultdict(float)
    absolute_delta_by_risk_factor = defaultdict(float)
    absolute_vega_by_risk_factor = defaultdict(float)
    currencies = []

    for record in validated_records:
        absolute_delta_by_risk_class[record.risk_class] += abs(record.delta)
        absolute_vega_by_bucket[record.bucket] += abs(record.vega)
        absolute_delta_by_risk_factor[record.risk_factor] += abs(record.delta)
        absolute_vega_by_risk_factor[record.risk_factor] += abs(record.vega)
        currencies.append(record.currency)

    unique_currencies = sorted(set(currencies))
    warnings = []
    if len(unique_currencies) > 1:
        warnings.append(
            "Multiple currencies are present in supplied sensitivities: "
            + ", ".join(unique_currencies)
            + ". Aggregates are not FX-normalized."
        )

    largest_delta_risk_factor = _largest_factor(absolute_delta_by_risk_factor)
    largest_vega_risk_factor = _largest_factor(absolute_vega_by_risk_factor)

    return {
        "source": "precomputed_sensitivities",
        "record_count": len(validated_records),
        "portfolio_ids": sorted({record.portfolio_id for record in validated_records}),
        "books": sorted({record.book for record in validated_records}),
        "currencies": unique_currencies,
        "total_delta": float(total_delta),
        "total_gamma": float(total_gamma),
        "total_vega": float(total_vega),
        "total_theta": float(total_theta),
        "absolute_delta_by_risk_class": dict(absolute_delta_by_risk_class),
        "absolute_vega_by_bucket": dict(absolute_vega_by_bucket),
        "largest_delta_risk_factor": largest_delta_risk_factor,
        "largest_vega_risk_factor": largest_vega_risk_factor,
        "warnings": warnings,
        "assumptions": [
            "Greeks are supplied by an upstream pricing or risk engine.",
            "RiskFlow Agent aggregates and validates supplied sensitivities only.",
            "No Black-Scholes, Monte Carlo, or pricing-model Greeks are calculated here.",
        ],
    }


def _largest_factor(values_by_factor: dict[str, float]) -> dict:
    factor, value = max(values_by_factor.items(), key=lambda item: item[1])
    return {"risk_factor": factor, "absolute_value": float(value)}
