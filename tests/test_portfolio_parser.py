import pytest

from src.portfolio_parser import parse_portfolio_text


def test_parse_percentage_before_ticker():
    result = parse_portfolio_text("40% SPY, 30% QQQ, 20% NVDA, 10% TLT")

    assert result == {
        "tickers": ["SPY", "QQQ", "NVDA", "TLT"],
        "weights": [0.4, 0.3, 0.2, 0.1],
    }


def test_parse_percentage_before_ticker_in_sentence():
    result = parse_portfolio_text(
        "Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT."
    )

    assert result["tickers"] == ["SPY", "QQQ", "NVDA", "TLT"]
    assert result["weights"] == [0.4, 0.3, 0.2, 0.1]


def test_parse_ticker_before_percentage():
    result = parse_portfolio_text("SPY 40%, QQQ 30%, NVDA 20%, TLT 10%")

    assert result == {
        "tickers": ["SPY", "QQQ", "NVDA", "TLT"],
        "weights": [0.4, 0.3, 0.2, 0.1],
    }


def test_parse_decimal_weights():
    result = parse_portfolio_text("0.4 SPY, 0.3 qqq, 0.2 NVDA, 0.1 TLT")

    assert result == {
        "tickers": ["SPY", "QQQ", "NVDA", "TLT"],
        "weights": [0.4, 0.3, 0.2, 0.1],
    }


def test_parse_rejects_weights_not_summing_to_one():
    with pytest.raises(ValueError, match="Invalid portfolio weights"):
        parse_portfolio_text("50% SPY, 30% QQQ")


def test_parse_rejects_malformed_input():
    with pytest.raises(ValueError, match="Could not parse portfolio holdings"):
        parse_portfolio_text("Analyze SPY and QQQ with no weights")
