from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    message: str


@dataclass
class ValidationResult:
    passed: bool
    checks: list[ValidationCheck]
    errors: list[str]
    warnings: list[str]


_RECOMMENDATION_PATTERNS = (
    re.compile(r"\b(you should|recommend(?:ed|s)?|must|need to)\s+(buy|sell|hold)\b", re.I),
    re.compile(r"\b(buy|sell|hold)\s+[A-Z]{1,10}\b", re.I),
)
_CERTAINTY_PATTERNS = (
    re.compile(r"\bguarantee(?:d|s)?\b", re.I),
    re.compile(r"\bcertain(?:ly)?\b", re.I),
    re.compile(r"\bwill definitely\b", re.I),
    re.compile(r"\brisk[- ]free\b", re.I),
)
_METHODOLOGY_REFERENCE_PATTERN = re.compile(
    r"Methodology references?:\s*([^\n.]+)",
    re.I,
)


def validate_generated_report(
    parsed_portfolio,
    risk_report,
    methodology_notes,
    commentary: str,
) -> ValidationResult:
    """Validate calculated risk outputs and generated commentary guardrails."""
    checks: list[ValidationCheck] = []
    errors: list[str] = []
    warnings: list[str] = []

    _run_check(
        checks,
        errors,
        "portfolio_weights_sum_to_one",
        _weights_sum_to_one(parsed_portfolio),
        "Portfolio weights sum to 1 within tolerance.",
        "Portfolio weights must sum to 1 within tolerance.",
    )

    risk_metrics = _get(risk_report, "risk_metrics", {})
    historical_var = _get(risk_metrics, "historical_var")
    expected_shortfall = _get(risk_metrics, "expected_shortfall")
    max_drawdown = _get(risk_metrics, "max_drawdown")

    _run_check(
        checks,
        errors,
        "historical_var_positive_loss",
        _is_positive_number(historical_var),
        "Historical VaR is a positive loss magnitude.",
        "Historical VaR must be a positive loss magnitude.",
    )
    _run_check(
        checks,
        errors,
        "expected_shortfall_positive_loss",
        _is_positive_number(expected_shortfall),
        "Expected Shortfall is a positive loss magnitude.",
        "Expected Shortfall must be a positive loss magnitude.",
    )
    _run_check(
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
    _run_check(
        checks,
        errors,
        "max_drawdown_positive_loss",
        _is_positive_number(max_drawdown),
        "Maximum drawdown is a positive loss magnitude.",
        "Maximum drawdown must be a positive loss magnitude.",
    )

    commentary_text = commentary or ""
    _run_check(
        checks,
        errors,
        "no_direct_trade_recommendations",
        not _contains_direct_recommendation(commentary_text),
        "Commentary does not contain direct buy, sell, or hold recommendations.",
        "Commentary must not contain direct buy, sell, or hold recommendations.",
    )

    has_assumptions_or_limitations = _contains_assumptions_or_limitations(commentary_text)
    checks.append(
        ValidationCheck(
            name="includes_assumptions_or_limitations",
            passed=has_assumptions_or_limitations,
            message=(
                "Commentary includes assumptions or limitations."
                if has_assumptions_or_limitations
                else "Commentary should include assumptions or limitations."
            ),
        )
    )
    if not has_assumptions_or_limitations:
        warnings.append("Commentary should include assumptions or limitations.")

    _run_check(
        checks,
        errors,
        "no_guaranteed_future_outcomes",
        not _contains_certainty_claim(commentary_text),
        "Commentary does not claim certainty or guaranteed future outcomes.",
        "Commentary must not claim certainty or guaranteed future outcomes.",
    )

    unsupported_titles = _unsupported_methodology_references(
        commentary_text,
        methodology_notes,
    )
    _run_check(
        checks,
        errors,
        "methodology_citations_retrieved",
        not unsupported_titles,
        "Commentary cites only retrieved methodology notes.",
        (
            "Commentary cites methodology notes that were not retrieved: "
            f"{', '.join(unsupported_titles)}."
        ),
    )

    return ValidationResult(
        passed=not errors,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


def _run_check(
    checks: list[ValidationCheck],
    errors: list[str],
    name: str,
    passed: bool,
    success_message: str,
    failure_message: str,
) -> None:
    message = success_message if passed else failure_message
    checks.append(ValidationCheck(name=name, passed=passed, message=message))
    if not passed:
        errors.append(failure_message)


def _weights_sum_to_one(parsed_portfolio, tolerance: float = 1e-6) -> bool:
    weights = _get(parsed_portfolio, "weights")
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


def _contains_direct_recommendation(commentary: str) -> bool:
    return any(pattern.search(commentary) for pattern in _RECOMMENDATION_PATTERNS)


def _contains_assumptions_or_limitations(commentary: str) -> bool:
    lower_commentary = commentary.lower()
    return "assumption" in lower_commentary or "limitation" in lower_commentary


def _contains_certainty_claim(commentary: str) -> bool:
    for pattern in _CERTAINTY_PATTERNS:
        for match in pattern.finditer(commentary):
            prefix = commentary[max(0, match.start() - 20) : match.start()].lower()
            if any(negation in prefix for negation in ("not ", "no ", "without ")):
                continue

            return True

    return False


def _unsupported_methodology_references(
    commentary: str,
    methodology_notes,
) -> list[str]:
    retrieved_titles = {_get(note, "title") for note in methodology_notes or []}
    retrieved_titles = {title for title in retrieved_titles if title}
    referenced_titles = _extract_methodology_references(commentary)

    return sorted(title for title in referenced_titles if title not in retrieved_titles)


def _extract_methodology_references(commentary: str) -> set[str]:
    references: set[str] = set()

    for match in _METHODOLOGY_REFERENCE_PATTERN.finditer(commentary):
        reference_text = match.group(1)
        for title in re.split(r",|\band\b", reference_text):
            clean_title = title.strip(" .;:")
            if clean_title:
                references.add(clean_title)

    return references


def _get(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)
