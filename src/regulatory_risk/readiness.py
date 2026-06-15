from __future__ import annotations

from collections.abc import Mapping


SA_CCR_REQUIRED_FIELDS = (
    "trade_type",
    "notional",
    "maturity",
    "asset_class",
    "supervisory_category",
)
SIMM_REGIM_REQUIRED_FIELDS = (
    "risk_factor_sensitivities",
    "margin_class",
    "product_class",
    "risk_factor_type",
    "currency",
)


def assess_regulatory_readiness(inputs: Mapping | None = None) -> dict:
    """Assess whether inputs are sufficient for downstream regulatory workflows."""
    provided_inputs = dict(inputs or {})
    sa_ccr_missing = _missing_fields(provided_inputs, SA_CCR_REQUIRED_FIELDS)
    simm_regim_missing = _missing_fields(provided_inputs, SIMM_REGIM_REQUIRED_FIELDS)
    missing_inputs = list(dict.fromkeys([*sa_ccr_missing, *simm_regim_missing]))

    return {
        "sa_ccr": {
            "status": "READY" if not sa_ccr_missing else "WARNING",
            "missing_required_fields": sa_ccr_missing,
        },
        "simm_regim": {
            "status": "READY" if not simm_regim_missing else "WARNING",
            "missing_required_fields": simm_regim_missing,
        },
        "overall_status": "READY" if not missing_inputs else "WARNING",
        "missing_inputs": missing_inputs,
        "regulatory_capital_calculation": "Not performed",
        "margin_calculation": "Not performed",
        "guardrail": "No regulatory capital number was generated from insufficient inputs",
    }


def _missing_fields(inputs: Mapping, required_fields: tuple[str, ...]) -> list[str]:
    return [
        field
        for field in required_fields
        if field not in inputs or inputs[field] in (None, "")
    ]
