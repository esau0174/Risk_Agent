"""Market-risk consistency checks for generated commentary."""

from __future__ import annotations

import math
import re
from typing import Any

from src.validators.common import ValidationCheck, get_value, run_check


_PERCENTAGE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_DOLLAR_MARKET_METRICS = {
    "historical_var": ("dollar_historical_var", "Dollar historical VaR"),
    "expected_shortfall": ("dollar_expected_shortfall", "Dollar Expected Shortfall"),
    "max_drawdown": ("dollar_max_drawdown", "Dollar maximum drawdown"),
}
_METRIC_LABELS = {
    "annualized_volatility": (
        "Annualized volatility",
        (r"annuali[sz]ed\s+volatility",),
    ),
    "historical_var": (
        "Historical VaR",
        (r"historical\s+var", r"95%\s+var", r"\bvar\b"),
    ),
    "expected_shortfall": (
        "Expected Shortfall",
        (r"expected\s+shortfall", r"\bes\b"),
    ),
    "max_drawdown": (
        "Maximum drawdown",
        (r"maximum\s+drawdown", r"max(?:imum)?\s+drawdown"),
    ),
}


def validate_market_metric_consistency(
    checks: list[ValidationCheck],
    errors: list[str],
    parsed_portfolio,
    risk_report,
    commentary: str,
    percentage_tolerance: float,
    enabled: bool,
) -> None:
    """Check deterministic market metrics and any matching commentary figures."""
    if not enabled:
        return

    run_check(
        checks,
        errors,
        "portfolio_weights_sum_to_one",
        _weights_sum_to_one(parsed_portfolio),
        "Portfolio weights sum to 1 within tolerance.",
        "Portfolio weights must sum to 1 within tolerance.",
    )

    risk_metrics = get_value(risk_report, "risk_metrics", {}) if risk_report else {}
    historical_var = get_value(risk_metrics, "historical_var")
    expected_shortfall = get_value(risk_metrics, "expected_shortfall")
    max_drawdown = get_value(risk_metrics, "max_drawdown")
    run_check(
        checks,
        errors,
        "historical_var_positive_loss",
        _is_positive_number(historical_var),
        "Historical VaR is a positive loss magnitude.",
        "Historical VaR must be a positive loss magnitude.",
    )
    run_check(
        checks,
        errors,
        "expected_shortfall_positive_loss",
        _is_positive_number(expected_shortfall),
        "Expected Shortfall is a positive loss magnitude.",
        "Expected Shortfall must be a positive loss magnitude.",
    )
    run_check(
        checks,
        errors,
        "expected_shortfall_at_least_var",
        (
            _is_number(expected_shortfall)
            and _is_number(historical_var)
            and expected_shortfall >= historical_var
        ),
        "Expected Shortfall is greater than or equal to historical VaR.",
        "Expected Shortfall must be greater than or equal to historical VaR.",
    )
    run_check(
        checks,
        errors,
        "max_drawdown_positive_loss",
        _is_positive_number(max_drawdown),
        "Maximum drawdown is a positive loss magnitude.",
        "Maximum drawdown must be a positive loss magnitude.",
    )

    if risk_report is None:
        return

    dollar_errors = _dollar_metric_consistency_errors(risk_report)
    checks.append(
        ValidationCheck(
            name="dollar_market_metric_consistency",
            passed=not dollar_errors,
            message=(
                "Dollar market risk metrics are consistent with percentage metrics and notional."
                if not dollar_errors
                else "Dollar market risk metrics are inconsistent with percentage metrics and notional."
            ),
        )
    )
    errors.extend(dollar_errors)

    consistency_errors = _commentary_metric_consistency_errors(
        commentary,
        risk_metrics,
        percentage_tolerance,
    )
    checks.append(
        ValidationCheck(
            name="commentary_metric_consistency",
            passed=not consistency_errors,
            message=(
                "Commentary percentage figures are consistent with calculated risk metrics."
                if not consistency_errors
                else "Commentary contains percentage figures inconsistent with calculated risk metrics."
            ),
        )
    )
    errors.extend(consistency_errors)


def _weights_sum_to_one(parsed_portfolio, tolerance: float = 1e-6) -> bool:
    weights = get_value(parsed_portfolio, "weights")
    if weights is None:
        return False
    try:
        weight_sum = sum(float(weight) for weight in weights)
    except (TypeError, ValueError):
        return False
    return math.isclose(weight_sum, 1.0, abs_tol=tolerance)


def _is_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def _is_positive_number(value: Any) -> bool:
    return _is_number(value) and float(value) > 0


def _commentary_metric_consistency_errors(
    commentary: str,
    risk_metrics,
    tolerance: float,
) -> list[str]:
    if tolerance < 0:
        raise ValueError("Percentage tolerance must be non-negative.")

    errors = []
    for metric_key, (display_name, label_patterns) in _METRIC_LABELS.items():
        expected_metric = get_value(risk_metrics, metric_key)
        if not _is_number(expected_metric):
            continue
        expected_percentage = float(expected_metric) * 100
        found_values = _extract_labeled_percentages(commentary, label_patterns)
        for found_percentage in found_values:
            if abs(found_percentage - expected_percentage) > tolerance:
                errors.append(
                    f"{display_name} percentage mismatch: expected "
                    f"{expected_percentage:.2f}%, found {found_percentage:.2f}%."
                )
    return errors


def _dollar_metric_consistency_errors(
    risk_report,
    dollar_tolerance: float = 0.01,
) -> list[str]:
    metadata = get_value(risk_report, "metadata", {}) or {}
    notional = get_value(metadata, "total_notional_usd")
    if not _is_number(notional):
        return []

    risk_metrics = get_value(risk_report, "risk_metrics", {}) or {}
    dollar_metrics = get_value(risk_report, "dollar_risk_metrics", {}) or {}
    errors = []
    for metric_key, (dollar_key, display_name) in _DOLLAR_MARKET_METRICS.items():
        metric_value = get_value(risk_metrics, metric_key)
        dollar_value = get_value(dollar_metrics, dollar_key)
        if not _is_number(metric_value) or dollar_value is None:
            continue
        expected_value = float(metric_value) * float(notional)
        if not _is_number(dollar_value) or abs(float(dollar_value) - expected_value) > dollar_tolerance:
            found = float(dollar_value) if _is_number(dollar_value) else float("nan")
            errors.append(
                f"{display_name} mismatch: expected USD {expected_value:.2f}, "
                f"found USD {found:.2f}."
            )
    return errors


def _extract_labeled_percentages(
    commentary: str,
    label_patterns: tuple[str, ...],
) -> list[float]:
    values: list[float] = []
    seen_spans: set[tuple[int, int]] = set()

    for label_pattern in label_patterns:
        for label_match in re.finditer(label_pattern, commentary, re.I):
            label_suffix = commentary[label_match.end() : label_match.end() + 15]
            if label_pattern == r"\bvar\b" and re.match(
                r"\s+threshold\b", label_suffix, re.I
            ):
                continue

            segment_start, segment_end = _segment_bounds(commentary, label_match)
            before = commentary[segment_start : label_match.start()]
            before = _text_after_last_other_metric_label(before, label_patterns)
            before_matches = list(_PERCENTAGE_PATTERN.finditer(before))
            if before_matches:
                percentage_match = before_matches[-1]
                gap = before[percentage_match.end() :]
                percentage_value = float(percentage_match.group("value"))
                is_confidence_label = (
                    percentage_value in {90.0, 95.0, 99.0}
                    and any("var" in pattern.lower() for pattern in label_patterns)
                )
                if re.fullmatch(r"\s*", gap) and not is_confidence_label:
                    span = (
                        label_match.start() - len(before) + percentage_match.start(),
                        label_match.start() - len(before) + percentage_match.end(),
                    )
                    if span not in seen_spans:
                        values.append(percentage_value)
                        seen_spans.add(span)
                        continue

            after = commentary[label_match.end() : segment_end]
            after = _text_before_first_other_metric_label(after, label_patterns)
            for percentage_match in _PERCENTAGE_PATTERN.finditer(after):
                suffix = after[percentage_match.end() : percentage_match.end() + 20]
                if re.match(r"\s*(?:confidence|level)", suffix, re.I):
                    continue
                span = (
                    label_match.end() + percentage_match.start(),
                    label_match.end() + percentage_match.end(),
                )
                if span not in seen_spans:
                    values.append(float(percentage_match.group("value")))
                    seen_spans.add(span)
                break
    return values


def _segment_bounds(commentary: str, label_match: re.Match) -> tuple[int, int]:
    boundaries = list(re.finditer(r"(?:[.!?;](?=\s|$)|\r?\n)", commentary))
    segment_start = 0
    segment_end = len(commentary)
    for boundary in boundaries:
        if boundary.end() <= label_match.start():
            segment_start = boundary.end()
            continue
        if boundary.start() >= label_match.end():
            segment_end = boundary.start()
            break
    return segment_start, segment_end


def _text_before_first_other_metric_label(
    text: str,
    current_patterns: tuple[str, ...],
) -> str:
    other_matches = _other_metric_matches(text, current_patterns)
    if not other_matches:
        return text
    return text[: min(match.start() for match in other_matches)]


def _text_after_last_other_metric_label(
    text: str,
    current_patterns: tuple[str, ...],
) -> str:
    other_matches = _other_metric_matches(text, current_patterns)
    if not other_matches:
        return text
    return text[max(match.end() for match in other_matches) :]


def _other_metric_matches(
    text: str,
    current_patterns: tuple[str, ...],
) -> list[re.Match]:
    matches = []
    for _, label_patterns in _METRIC_LABELS.values():
        if label_patterns == current_patterns:
            continue
        for pattern in label_patterns:
            for match in re.finditer(pattern, text, re.I):
                suffix = text[match.end() : match.end() + 15]
                if pattern == r"\bvar\b" and re.match(
                    r"\s+threshold\b", suffix, re.I
                ):
                    continue
                matches.append(match)
    return matches
