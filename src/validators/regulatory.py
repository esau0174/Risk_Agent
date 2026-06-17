from __future__ import annotations

import re

from src.validators.common import ValidationCheck, ValidationResult


def validate_regulatory_readiness_report(
    report_text: str,
    readiness_result: dict,
) -> ValidationResult:
    """Validate that regulatory readiness output does not imply unsupported capital."""
    checks: list[ValidationCheck] = []
    errors: list[str] = []
    warnings: list[str] = []
    text = report_text or ""
    missing_inputs = readiness_result.get("missing_inputs", [])

    supported_statuses = {"READY", "PARTIAL", "WARNING", "NOT_READY"}
    structured_status = (
        readiness_result.get("sa_ccr", {}).get("status") in supported_statuses
        and readiness_result.get("simm_regim", {}).get("status") in supported_statuses
    )
    checks.append(
        ValidationCheck(
            name="regulatory_readiness_status_structured",
            passed=structured_status,
            message=(
                "Regulatory readiness status is structured."
                if structured_status
                else "Regulatory readiness status must be structured."
            ),
        )
    )
    if not structured_status:
        errors.append("Regulatory readiness status must be structured.")

    missing_fields_reported = all(field in text for field in missing_inputs)
    checks.append(
        ValidationCheck(
            name="regulatory_missing_inputs_reported",
            passed=missing_fields_reported,
            message=(
                "Regulatory missing inputs are reported clearly."
                if missing_fields_reported
                else "Regulatory missing inputs must be reported clearly."
            ),
        )
    )
    if not missing_fields_reported:
        errors.append("Regulatory missing inputs must be reported clearly.")

    no_fabricated_number = not _contains_unsupported_capital_or_margin_number(text)
    checks.append(
        ValidationCheck(
            name="no_fabricated_regulatory_capital_or_margin",
            passed=no_fabricated_number,
            message=(
                "No unsupported regulatory capital or margin number was generated."
                if no_fabricated_number
                else "Report must not contain unsupported regulatory capital or margin numbers."
            ),
        )
    )
    if not no_fabricated_number:
        errors.append(
            "Report must not contain unsupported regulatory capital or margin numbers."
        )

    return ValidationResult(
        passed=not errors,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


def _contains_unsupported_capital_or_margin_number(text: str) -> bool:
    for segment in re.split(r"(?:[.!?;\n])", text):
        lower_segment = segment.lower()
        if (
            "not performed" in lower_segment
            or "no regulatory capital number" in lower_segment
            or "no regulatory capital or margin number" in lower_segment
            or "no simm margin amount is generated" in lower_segment
        ):
            continue
        if not re.search(r"\b(?:capital|margin|regim)\b", lower_segment):
            continue
        if re.search(r"(?:usd\s*)?\d[\d,]*(?:\.\d+)?\s*(?:usd|%)?", segment, re.I):
            return True
    return False
