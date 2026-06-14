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
    re.compile(r"\b(?:buy|sell|hold)\s+[A-Z][A-Z0-9.-]{0,9}\b", re.I),
    re.compile(
        r"\b(?:i\s+)?recommend(?:ation|ed|s|ing)?(?:\s+that\s+you)?\s+"
        r"(?:to\s+)?(?:buy|buying|sell|selling|hold|holding)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:increase|reduce|decrease|raise|lower)\s+(?:your\s+)?exposure\s+to\s+"
        r"[A-Z][A-Z0-9.-]{0,9}\b",
        re.I,
    ),
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
_PERCENTAGE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
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

    if pfe_result is None:
        _run_check(
            checks,
            errors,
            "portfolio_weights_sum_to_one",
            _weights_sum_to_one(parsed_portfolio),
            "Portfolio weights sum to 1 within tolerance.",
            "Portfolio weights must sum to 1 within tolerance.",
        )

    risk_metrics = _get(risk_report, "risk_metrics", {}) if risk_report else {}
    historical_var = _get(risk_metrics, "historical_var")
    expected_shortfall = _get(risk_metrics, "expected_shortfall")
    max_drawdown = _get(risk_metrics, "max_drawdown")

    if pfe_result is None:
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
    consistency_errors = _commentary_metric_consistency_errors(
        commentary_text,
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

    pfe_errors = _pfe_result_consistency_errors(
        commentary_text,
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

    stress_errors, stress_warning = _stress_result_consistency_findings(
        commentary_text,
        stress_results or [],
        percentage_tolerance,
        value_tolerance=0.10,
    )
    stress_check_passed = not stress_errors and stress_warning is None
    checks.append(
        ValidationCheck(
            name="stress_result_consistency",
            passed=stress_check_passed,
            message=(
                "Commentary stress figures are consistent with calculated stress results."
                if stress_check_passed
                else stress_warning
                or "Commentary contains figures inconsistent with calculated stress results."
            ),
        )
    )
    errors.extend(stress_errors)
    if stress_warning:
        warnings.append(stress_warning)

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
    for pattern in _RECOMMENDATION_PATTERNS:
        for match in pattern.finditer(commentary):
            sentence_start = max(
                commentary.rfind(".", 0, match.start()),
                commentary.rfind("!", 0, match.start()),
                commentary.rfind("?", 0, match.start()),
                commentary.rfind("\n", 0, match.start()),
            )
            sentence_prefix = commentary[sentence_start + 1 : match.start()].lower()
            if any(
                negation in sentence_prefix
                for negation in (
                    "not ",
                    "does not ",
                    "do not ",
                    "is not ",
                    "isn't ",
                    "no recommendation ",
                    "without ",
                )
            ):
                continue

            return True

    return False


def _commentary_metric_consistency_errors(
    commentary: str,
    risk_metrics,
    tolerance: float,
) -> list[str]:
    if tolerance < 0:
        raise ValueError("Percentage tolerance must be non-negative.")

    errors = []
    for metric_key, (display_name, label_patterns) in _METRIC_LABELS.items():
        expected_metric = _get(risk_metrics, metric_key)
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


def _stress_result_consistency_findings(
    commentary: str,
    stress_results,
    percentage_tolerance: float,
    value_tolerance: float,
) -> tuple[list[str], str | None]:
    if percentage_tolerance < 0 or value_tolerance < 0:
        raise ValueError("Stress result tolerances must be non-negative.")
    if not stress_results:
        return [], None

    relevant_segments = _stress_relevant_segments(commentary, stress_results)
    if not relevant_segments:
        return [], "Stress results are available, but commentary omits stress analysis."

    errors = []
    for result in stress_results:
        scenario_name = str(_get(result, "scenario_name", "")).strip()
        scenario_segments = [
            segment
            for segment in relevant_segments
            if scenario_name and scenario_name.lower() in segment.lower()
        ]
        if not scenario_segments and len(stress_results) == 1:
            scenario_segments = relevant_segments
        if not scenario_segments:
            continue

        scenario_text = " ".join(scenario_segments)
        expected_loss = float(_get(result, "portfolio_loss_pct")) * 100
        found_loss = _extract_stress_percentage(
            scenario_text,
            r"portfolio\s+loss(?:\s+(?:percentage|pct))?",
        )
        if found_loss is not None and abs(found_loss - expected_loss) > percentage_tolerance:
            errors.append(
                f"Stress scenario '{scenario_name}' portfolio loss mismatch: expected "
                f"{expected_loss:.2f}%, found {found_loss:.2f}%."
            )

        found_value = _extract_stressed_portfolio_value(scenario_text)
        expected_value = float(_get(result, "stressed_portfolio_value"))
        if found_value is not None and abs(found_value - expected_value) > value_tolerance:
            errors.append(
                f"Stress scenario '{scenario_name}' stressed portfolio value mismatch: "
                f"expected {expected_value:.2f}, found {found_value:.2f}."
            )

        contributions = _get(result, "per_ticker_contributions", {}) or {}
        if re.search(r"\bcontribut(?:ion|ions|or|ors|ed|es|ing)\b", scenario_text, re.I):
            for ticker, details in contributions.items():
                found_contribution = _extract_ticker_contribution(scenario_text, ticker)
                if found_contribution is None:
                    continue
                expected_contribution = (
                    float(_get(details, "portfolio_loss_contribution_pct")) * 100
                )
                if (
                    abs(found_contribution - expected_contribution)
                    > percentage_tolerance
                ):
                    errors.append(
                        f"Stress scenario '{scenario_name}' {ticker} contribution mismatch: "
                        f"expected {expected_contribution:.2f}%, found "
                        f"{found_contribution:.2f}%."
                    )

    return errors, None


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
        expected_peak = float(_get(pfe_result, "peak_pfe_95"))
        if abs(found_peak - expected_peak) > value_tolerance:
            errors.append(
                f"Peak PFE 95 mismatch: expected {expected_peak:.2f}, "
                f"found {found_peak:.2f}."
            )

        found_time = _number_from_match(peak_match, "time")
        expected_time = float(_get(pfe_result, "time_of_peak_pfe_95"))
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
        expected_epe = float(_get(pfe_result, "epe"))
        if abs(found_epe - expected_epe) > value_tolerance:
            errors.append(
                f"EPE mismatch: expected {expected_epe:.2f}, found {found_epe:.2f}."
            )

    return errors


def _number_from_match(match: re.Match, group: str) -> float:
    return float(match.group(group).replace(",", ""))


def _stress_relevant_segments(commentary: str, stress_results) -> list[str]:
    scenario_names = [
        str(_get(result, "scenario_name", "")).strip().lower()
        for result in stress_results
    ]
    segments = re.split(r"(?:[.!?;](?=\s|$)|\r?\n)", commentary)
    return [
        segment.strip()
        for segment in segments
        if segment.strip()
        and (
            re.search(r"\b(?:stress|scenario)\b", segment, re.I)
            or any(name and name in segment.lower() for name in scenario_names)
        )
    ]


def _extract_stress_percentage(text: str, label_pattern: str) -> float | None:
    match = re.search(
        rf"{label_pattern}[^.!?;\n%\d]{{0,40}}(?P<value>\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    )
    return float(match.group("value")) if match else None


def _extract_stressed_portfolio_value(text: str) -> float | None:
    match = re.search(
        r"stressed\s+portfolio\s+value[^.!?;\n\d]"
        r"{0,20}\$?(?P<value>\d+(?:\.\d+)?)",
        text,
        re.I,
    )
    return float(match.group("value")) if match else None


def _extract_ticker_contribution(text: str, ticker: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(str(ticker))}\b[^.!?;\n%\d]{{0,30}}"
        r"(?P<value>\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    )
    return float(match.group("value")) if match else None


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
                r"\s+threshold\b",
                label_suffix,
                re.I,
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
                if pattern == r"\bvar\b" and re.match(r"\s+threshold\b", suffix, re.I):
                    continue
                matches.append(match)

    return matches


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
