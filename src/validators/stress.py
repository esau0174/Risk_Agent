from __future__ import annotations

import re

from src.validators.common import ValidationCheck, get_value


def validate_stress_result_consistency(
    checks: list[ValidationCheck],
    errors: list[str],
    warnings: list[str],
    commentary: str,
    stress_results,
    percentage_tolerance: float,
) -> None:
    if not stress_results:
        return
    stress_errors, stress_warning = _stress_result_consistency_findings(
        commentary,
        stress_results,
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
        scenario_name = str(get_value(result, "scenario_name", "")).strip()
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
        expected_loss = float(get_value(result, "portfolio_loss_pct")) * 100
        found_loss = _extract_stress_percentage(
            scenario_text,
            r"portfolio\s+loss(?:\s+(?:percentage|pct))?",
        )
        if found_loss is not None and abs(found_loss - expected_loss) > percentage_tolerance:
            errors.append(
                f"Stress scenario '{scenario_name}' portfolio loss mismatch: expected "
                f"{expected_loss:.2f}%, found {found_loss:.2f}%."
            )

        dollar_loss = get_value(result, "dollar_portfolio_loss")
        notional = get_value(result, "base_portfolio_value_usd")
        if dollar_loss is not None and notional is not None:
            expected_dollar_loss = (
                float(get_value(result, "portfolio_loss_pct")) * float(notional)
            )
            if abs(float(dollar_loss) - expected_dollar_loss) > value_tolerance:
                errors.append(
                    f"Stress scenario '{scenario_name}' dollar portfolio loss mismatch: "
                    f"expected USD {expected_dollar_loss:.2f}, found USD "
                    f"{float(dollar_loss):.2f}."
                )

        found_value = _extract_stressed_portfolio_value(scenario_text)
        expected_value = float(
            get_value(
                result,
                "stressed_portfolio_value_usd",
                get_value(result, "stressed_portfolio_value"),
            )
        )
        if found_value is not None and abs(found_value - expected_value) > value_tolerance:
            errors.append(
                f"Stress scenario '{scenario_name}' stressed portfolio value mismatch: "
                f"expected {expected_value:.2f}, found {found_value:.2f}."
            )

        contributions = get_value(result, "per_ticker_contributions", {}) or {}
        if re.search(r"\bcontribut(?:ion|ions|or|ors|ed|es|ing)\b", scenario_text, re.I):
            for ticker, details in contributions.items():
                found_contribution = _extract_ticker_contribution(scenario_text, ticker)
                if found_contribution is None:
                    continue
                expected_contribution = (
                    float(get_value(details, "portfolio_loss_contribution_pct")) * 100
                )
                if abs(found_contribution - expected_contribution) > percentage_tolerance:
                    errors.append(
                        f"Stress scenario '{scenario_name}' {ticker} contribution mismatch: "
                        f"expected {expected_contribution:.2f}%, found "
                        f"{found_contribution:.2f}%."
                    )
    return errors, None


def _stress_relevant_segments(commentary: str, stress_results) -> list[str]:
    scenario_names = [
        str(get_value(result, "scenario_name", "")).strip().lower()
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
        r"{0,20}(?:USD\s*)?\$?(?P<value>\d[\d,]*(?:\.\d+)?)",
        text,
        re.I,
    )
    return float(match.group("value").replace(",", "")) if match else None


def _extract_ticker_contribution(text: str, ticker: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(str(ticker))}\b[^.!?;\n%\d]{{0,30}}"
        r"(?P<value>\d+(?:\.\d+)?)\s*%",
        text,
        re.I,
    )
    return float(match.group("value")) if match else None
