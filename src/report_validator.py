"""Public report validation entry point.

Validators check generated commentary against deterministic analytics outputs,
methodology retrieval, and financial guardrails before a report is considered
safe to present.
"""

from __future__ import annotations

from src.validators.common import ValidationCheck, ValidationResult
from src.validators.credit import validate_pfe_result_consistency
from src.validators.guardrails import validate_commentary_guardrails
from src.validators.market import validate_market_metric_consistency
from src.validators.methodology import validate_methodology_grounding
from src.validators.stress import validate_stress_result_consistency


# Descriptive alias retained alongside the established ValidationResult API.
ReportValidationResult = ValidationResult


def validate_generated_report(
    parsed_portfolio,
    risk_report,
    methodology_notes,
    commentary: str,
    percentage_tolerance: float = 0.10,
    stress_results=None,
    pfe_result=None,
) -> ValidationResult:
    """Validate calculated risk outputs and generated commentary guardrails."""
    checks: list[ValidationCheck] = []
    errors: list[str] = []
    warnings: list[str] = []
    commentary_text = commentary or ""

    validate_market_metric_consistency(
        checks,
        errors,
        parsed_portfolio,
        risk_report,
        commentary_text,
        percentage_tolerance,
        enabled=pfe_result is None,
    )
    validate_pfe_result_consistency(checks, errors, warnings, commentary_text, pfe_result)
    validate_stress_result_consistency(
        checks,
        errors,
        warnings,
        commentary_text,
        stress_results,
        percentage_tolerance,
    )
    validate_commentary_guardrails(checks, errors, warnings, commentary_text)
    validate_methodology_grounding(
        checks,
        errors,
        commentary_text,
        methodology_notes,
    )

    return ValidationResult(
        passed=not errors,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


__all__ = [
    "ReportValidationResult",
    "ValidationCheck",
    "ValidationResult",
    "validate_generated_report",
]
