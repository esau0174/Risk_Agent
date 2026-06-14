from __future__ import annotations

import re

from src.validators.common import ValidationCheck, run_check


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


def validate_commentary_guardrails(
    checks: list[ValidationCheck],
    errors: list[str],
    warnings: list[str],
    commentary: str,
) -> None:
    run_check(
        checks,
        errors,
        "no_direct_trade_recommendations",
        not _contains_direct_recommendation(commentary),
        "Commentary does not contain direct buy, sell, or hold recommendations.",
        "Commentary must not contain direct buy, sell, or hold recommendations.",
    )

    has_assumptions_or_limitations = _contains_assumptions_or_limitations(commentary)
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

    run_check(
        checks,
        errors,
        "no_guaranteed_future_outcomes",
        not _contains_certainty_claim(commentary),
        "Commentary does not claim certainty or guaranteed future outcomes.",
        "Commentary must not claim certainty or guaranteed future outcomes.",
    )


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
