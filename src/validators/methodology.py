from __future__ import annotations

import re

from src.validators.common import ValidationCheck, get_value, run_check


_METHODOLOGY_REFERENCE_PATTERN = re.compile(
    r"Methodology references?:\s*([^\n.]+)",
    re.I,
)


def validate_methodology_grounding(
    checks: list[ValidationCheck],
    errors: list[str],
    commentary: str,
    methodology_notes,
) -> None:
    unsupported_titles = _unsupported_methodology_references(
        commentary,
        methodology_notes,
    )
    run_check(
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


def _unsupported_methodology_references(
    commentary: str,
    methodology_notes,
) -> list[str]:
    retrieved_titles = {
        get_value(note, "title") for note in methodology_notes or []
    }
    retrieved_titles = {title for title in retrieved_titles if title}
    referenced_titles = _extract_methodology_references(commentary, retrieved_titles)
    return sorted(title for title in referenced_titles if title not in retrieved_titles)


def _extract_methodology_references(
    commentary: str,
    retrieved_titles: set[str] | None = None,
) -> set[str]:
    references: set[str] = set()
    retrieved_titles = retrieved_titles or set()

    for match in _METHODOLOGY_REFERENCE_PATTERN.finditer(commentary):
        reference_text = match.group(1)
        remaining_text = reference_text
        for title in sorted(retrieved_titles, key=len, reverse=True):
            title_match = re.search(re.escape(title), remaining_text, re.I)
            if title_match:
                references.add(title)
                remaining_text = (
                    remaining_text[: title_match.start()]
                    + ","
                    + remaining_text[title_match.end() :]
                )

        for title in re.split(r",|\band\b", remaining_text):
            clean_title = title.strip(" .;:")
            if clean_title:
                references.add(clean_title)
    return references
