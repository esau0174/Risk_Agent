"""Regulatory readiness screening for downstream SA-CCR and SIMM workflows.

This module checks input completeness only. It intentionally does not calculate
SA-CCR EAD, SIMM margin, RegIM, or regulatory capital.
"""

from __future__ import annotations

from collections.abc import Mapping


SA_CCR_TRADE_LEVEL_REQUIRED_FIELDS = (
    "trade_type",
    "trade_notional",
    "maturity",
    "supervisory_category",
    "netting_agreement_details",
    "supervisory_factor_category_mapping",
)

SIMM_REGIM_SENSITIVITY_FIELDS = (
    "risk_class",
    "risk_factor",
    "bucket",
    "delta",
    "gamma",
    "vega",
    "theta",
    "currency",
)
SIMM_REGIM_MODEL_FIELDS = (
    "product_class",
    "margin_class",
    "risk_weight_mapping",
    "correlation_parameters",
    "margin_currency",
)


def assess_regulatory_readiness(inputs: Mapping | None = None) -> dict:
    """Assess available and missing inputs without producing capital numbers."""
    provided_inputs = dict(inputs or {})
    sa_ccr_available_portfolio_metadata = _available_sa_ccr_portfolio_metadata(
        provided_inputs
    )
    sa_ccr_missing = _missing_fields(
        provided_inputs,
        SA_CCR_TRADE_LEVEL_REQUIRED_FIELDS,
    )
    simm_available = _available_simm_regim_inputs(provided_inputs)
    simm_required_fields = (*SIMM_REGIM_SENSITIVITY_FIELDS, *SIMM_REGIM_MODEL_FIELDS)
    simm_regim_missing = [
        field for field in simm_required_fields if field not in simm_available
    ]
    missing_inputs = list(dict.fromkeys([*sa_ccr_missing, *simm_regim_missing]))
    simm_status = _simm_regim_status(simm_available, simm_regim_missing)

    return {
        "sa_ccr": {
            "status": "READY" if not sa_ccr_missing else "WARNING",
            "available_portfolio_metadata": sa_ccr_available_portfolio_metadata,
            "missing_trade_level_inputs": sa_ccr_missing,
            "missing_required_fields": sa_ccr_missing,
            "guardrail_note": (
                "Portfolio-level metadata is useful context, but it does not "
                "replace trade-level SA-CCR inputs."
            ),
        },
        "simm_regim": {
            "status": simm_status,
            "available_inputs": sorted(simm_available),
            "missing_inputs": simm_regim_missing,
            "missing_required_fields": simm_regim_missing,
            "guardrail_note": (
                "No SIMM margin amount is generated. No regulatory capital or "
                "margin number is fabricated from incomplete inputs."
            ),
        },
        "overall_status": "READY" if not missing_inputs else "WARNING",
        "missing_inputs": missing_inputs,
        "regulatory_capital_calculation": "Not performed",
        "margin_calculation": "Not performed",
        "guardrail": (
            "No regulatory capital or margin number was generated from insufficient inputs."
        ),
    }


def _missing_fields(inputs: Mapping, required_fields: tuple[str, ...]) -> list[str]:
    return [
        field
        for field in required_fields
        if field not in inputs or inputs[field] in (None, "")
    ]


def _available_sa_ccr_portfolio_metadata(inputs: Mapping) -> list[str]:
    """Report portfolio-level metadata separately from trade-level inputs."""
    available = []
    if any(
        inputs.get(field) not in (None, "")
        for field in (
            "portfolio_notional",
            "portfolio_notional_usd",
            "total_notional_usd",
            "notional_usd",
        )
    ):
        available.append("portfolio_notional")
    if any(
        inputs.get(field) not in (None, "")
        for field in (
            "portfolio_asset_class",
            "portfolio_asset_classes",
            "asset_class",
        )
    ):
        available.append("asset_class")
    return available


def _available_simm_regim_inputs(inputs: Mapping) -> set[str]:
    available = {
        field
        for field in (*SIMM_REGIM_SENSITIVITY_FIELDS, *SIMM_REGIM_MODEL_FIELDS)
        if field in inputs and inputs[field] not in (None, "")
    }

    for field in inputs.get("sensitivity_fields", []) or []:
        if field in SIMM_REGIM_SENSITIVITY_FIELDS:
            available.add(field)

    if inputs.get("precomputed_sensitivities") or inputs.get("sensitivity_records"):
        available.update(SIMM_REGIM_SENSITIVITY_FIELDS)

    if inputs.get("sensitivity_result"):
        available.update(SIMM_REGIM_SENSITIVITY_FIELDS)

    return available


def _simm_regim_status(available_inputs: set[str], missing_inputs: list[str]) -> str:
    if not missing_inputs:
        return "READY"
    if any(field in available_inputs for field in SIMM_REGIM_SENSITIVITY_FIELDS):
        return "PARTIAL"
    return "WARNING"
