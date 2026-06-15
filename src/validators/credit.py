from __future__ import annotations

import re

from src.validators.common import ValidationCheck, get_value


def validate_pfe_result_consistency(
    checks: list[ValidationCheck],
    errors: list[str],
    warnings: list[str],
    commentary: str,
    pfe_result,
) -> None:
    if pfe_result is None:
        return
    pfe_errors = _pfe_result_consistency_errors(
        commentary,
        pfe_result,
        value_tolerance=0.10,
        time_tolerance=0.01,
    )
    checks.append(
        ValidationCheck(
            name="pfe_result_consistency",
            passed=not pfe_errors,
            message=(
                "Commentary PFE figures are consistent with calculated exposure metrics."
                if not pfe_errors
                else "Commentary contains figures inconsistent with calculated PFE metrics."
            ),
        )
    )
    errors.extend(pfe_errors)
    _validate_credit_limit_utilization(checks, errors, warnings, pfe_result)


def _pfe_result_consistency_errors(
    commentary: str,
    pfe_result,
    value_tolerance: float,
    time_tolerance: float,
) -> list[str]:
    if value_tolerance < 0 or time_tolerance < 0:
        raise ValueError("PFE result tolerances must be non-negative.")
    if not pfe_result:
        return []

    segments = [
        segment.strip()
        for segment in re.split(r"(?:[.!?;](?=\s|$)|\r?\n)", commentary)
        if segment.strip()
        and re.search(
            r"\b(?:pfe|epe|expected\s+exposure|counterparty\s+exposure)\b",
            segment,
            re.I,
        )
    ]
    pfe_text = " ".join(segments)
    if not pfe_text:
        return ["PFE results are available, but commentary omits PFE analysis."]

    errors = []
    peak_match = re.search(
        r"peak\s+(?:95%\s+)?pfe[^.!?;\n\d]{0,30}"
        r"(?P<value>\d[\d,]*(?:\.\d+)?)"
        r"[^.!?;\n]{0,30}?\b(?:at|time(?:\s+of\s+peak)?(?:\s+is)?)\s+"
        r"(?P<time>\d+(?:\.\d+)?)\s*(?:years?|yrs?)",
        pfe_text,
        re.I,
    )
    if peak_match:
        found_peak = _number_from_match(peak_match, "value")
        expected_peak = float(get_value(pfe_result, "peak_pfe_95"))
        if abs(found_peak - expected_peak) > value_tolerance:
            errors.append(
                f"Peak PFE 95 mismatch: expected {expected_peak:.2f}, "
                f"found {found_peak:.2f}."
            )

        found_time = _number_from_match(peak_match, "time")
        expected_time = float(get_value(pfe_result, "time_of_peak_pfe_95"))
        if abs(found_time - expected_time) > time_tolerance:
            errors.append(
                f"Time of peak PFE 95 mismatch: expected {expected_time:.2f} years, "
                f"found {found_time:.2f} years."
            )

    epe_match = re.search(
        r"(?:average\s+expected\s+exposure\s*\(\s*epe\s*\)|"
        r"average\s+expected\s+exposure|\bepe\b)"
        r"[^.!?;\n\d]{0,30}(?P<value>\d[\d,]*(?:\.\d+)?)",
        pfe_text,
        re.I,
    )
    if epe_match:
        found_epe = _number_from_match(epe_match, "value")
        expected_epe = float(get_value(pfe_result, "epe"))
        if abs(found_epe - expected_epe) > value_tolerance:
            errors.append(
                f"EPE mismatch: expected {expected_epe:.2f}, found {found_epe:.2f}."
            )
    return errors


def _number_from_match(match: re.Match, group: str) -> float:
    return float(match.group(group).replace(",", ""))


def _validate_credit_limit_utilization(
    checks: list[ValidationCheck],
    errors: list[str],
    warnings: list[str],
    pfe_result,
) -> None:
    configured_limit = get_value(pfe_result, "configured_limit")
    utilization = get_value(pfe_result, "limit_utilization")
    status = get_value(pfe_result, "limit_status")
    limit_warning = get_value(pfe_result, "limit_warning")

    if configured_limit is None:
        message = limit_warning or "No credit limit configured for largest netting set."
        checks.append(
            ValidationCheck(
                name="credit_limit_utilization",
                passed=False,
                message=message,
            )
        )
        warnings.append(message)
        return

    limit_errors = []
    if utilization is None:
        limit_errors.append("Limit utilization is missing despite configured limit.")
    elif float(utilization) < 0:
        limit_errors.append("Limit utilization must be non-negative.")

    expected_status = "BREACHED" if utilization is not None and float(utilization) > 1 else "PASSED"
    if status != expected_status:
        limit_errors.append(
            f"Limit status mismatch: expected {expected_status}, found {status}."
        )

    checks.append(
        ValidationCheck(
            name="credit_limit_utilization",
            passed=not limit_errors,
            message=(
                "Credit limit utilization is consistent with configured limit."
                if not limit_errors
                else "Credit limit utilization is inconsistent with configured limit."
            ),
        )
    )
    errors.extend(limit_errors)
