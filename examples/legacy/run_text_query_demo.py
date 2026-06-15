from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.portfolio_parser import parse_portfolio_text
from src.market_risk.risk_report import generate_portfolio_risk_report


def main() -> None:
    query = (
        "Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT. "
        "Focus on downside risk and concentration risk."
    )
    start_date = "2023-01-01"

    parsed_portfolio = parse_portfolio_text(query)
    report = generate_portfolio_risk_report(
        parsed_portfolio["tickers"],
        parsed_portfolio["weights"],
        start_date=start_date,
    )

    print("Phase 2A Text Query Demo")
    print("=======================")
    print(f"Original user query: {query}")
    print()
    print("Parsed portfolio:")
    print(f"Tickers: {parsed_portfolio['tickers']}")
    print(f"Weights: {parsed_portfolio['weights']}")
    print()
    print("Risk metrics:")
    _print_risk_metrics(report)
    print()
    print("Analyst summary:")
    print(_build_analyst_summary(report))


def _print_risk_metrics(report: dict) -> None:
    metrics = report["risk_metrics"]

    print(f"Annualized volatility: {metrics['annualized_volatility']:.2%}")
    print(f"95% historical VaR: {metrics['historical_var']:.2%}")
    print(f"95% Expected Shortfall: {metrics['expected_shortfall']:.2%}")
    print(f"Maximum drawdown: {metrics['max_drawdown']:.2%}")
    print(f"Latest cumulative return: {report['latest_cumulative_return']:.2%}")
    print(f"Number of observations: {report['number_of_observations']}")


def _build_analyst_summary(report: dict) -> str:
    metadata = report["metadata"]
    metrics = report["risk_metrics"]
    tickers = metadata["tickers"]
    weights = metadata["weights"]
    largest_index = max(range(len(weights)), key=weights.__getitem__)
    largest_ticker = tickers[largest_index]
    largest_weight = weights[largest_index]

    return (
        f"Based on historical daily returns since {metadata['start_date']}, the portfolio's "
        f"95% historical VaR is {metrics['historical_var']:.2%}, meaning a one-day loss "
        "worse than this threshold occurred in the historical tail. Expected Shortfall is "
        f"{metrics['expected_shortfall']:.2%}, which estimates the average loss on days "
        "beyond the VaR threshold. The maximum historical drawdown over the sample was "
        f"{metrics['max_drawdown']:.2%}. Concentration risk is led by {largest_ticker}, "
        f"the largest position at {largest_weight:.2%} of portfolio weight. This analysis "
        "uses historical data only and is not investment advice."
    )


if __name__ == "__main__":
    main()
