from __future__ import annotations

import re

from src.data.portfolio import validate_weights


_TICKER_PATTERN = r"[A-Za-z][A-Za-z0-9.-]{0,9}"
_NUMBER_PATTERN = r"\d+(?:\.\d+)?"
_DECIMAL_WEIGHT_PATTERN = r"(?:0?\.\d+|1(?:\.0+)?)"

_HOLDING_PATTERN = re.compile(
    rf"""
    (?:
        (?P<percent_before>{_NUMBER_PATTERN})\s*%\s*
        (?P<ticker_after_percent>{_TICKER_PATTERN})
    )
    |
    (?:
        (?P<ticker_before_percent>{_TICKER_PATTERN})\s+
        (?P<percent_after>{_NUMBER_PATTERN})\s*%(?!\s*[A-Za-z])
    )
    |
    (?:
        (?P<decimal_before>{_DECIMAL_WEIGHT_PATTERN})\s+
        (?P<ticker_after_decimal>{_TICKER_PATTERN})
    )
    """,
    re.VERBOSE,
)


def parse_portfolio_text(text: str) -> dict:
    """Parse rule-based natural language portfolio text into tickers and weights."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Portfolio text must be a non-empty string.")

    holdings = []
    for match in _HOLDING_PATTERN.finditer(text):
        if match.group("percent_before") is not None:
            weight = float(match.group("percent_before")) / 100
            ticker = match.group("ticker_after_percent")
        elif match.group("percent_after") is not None:
            weight = float(match.group("percent_after")) / 100
            ticker = match.group("ticker_before_percent")
        else:
            weight = float(match.group("decimal_before"))
            ticker = match.group("ticker_after_decimal")

        holdings.append((ticker.upper().rstrip(".,;:!?"), weight))

    if not holdings:
        raise ValueError(
            "Could not parse portfolio holdings. Include weights with tickers, such as '40% SPY' or 'SPY 40%'."
        )

    tickers = [ticker for ticker, _ in holdings]
    weights = [weight for _, weight in holdings]

    try:
        validated_weights = validate_weights(tickers, weights)
    except ValueError as exc:
        raise ValueError(f"Invalid portfolio weights: {exc}") from exc

    return {
        "tickers": tickers,
        "weights": validated_weights.tolist(),
    }
