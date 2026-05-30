from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from src.market_data import download_price_data
from src.portfolio import (
    calculate_asset_returns,
    calculate_cumulative_returns,
    calculate_portfolio_returns,
)
from src.risk_metrics import (
    annualized_volatility,
    correlation_matrix,
    expected_shortfall,
    historical_var,
    max_drawdown,
)


def generate_portfolio_risk_report(
    tickers: Sequence[str],
    weights: Sequence[float],
    start_date: str,
    end_date: str | None = None,
    confidence_level: float = 0.95,
) -> dict:
    """Generate a high-level Phase 1 portfolio risk report."""
    ticker_list = list(tickers)
    weight_list = [float(weight) for weight in weights]

    prices = download_price_data(ticker_list, start_date, end_date)
    asset_returns = calculate_asset_returns(prices)
    portfolio_returns = calculate_portfolio_returns(asset_returns, weight_list)
    cumulative_returns = calculate_cumulative_returns(portfolio_returns)

    correlations = correlation_matrix(asset_returns)

    return {
        "metadata": {
            "tickers": ticker_list,
            "weights": weight_list,
            "start_date": start_date,
            "end_date": end_date,
            "confidence_level": float(confidence_level),
        },
        "risk_metrics": {
            "annualized_volatility": annualized_volatility(portfolio_returns),
            "historical_var": historical_var(portfolio_returns, confidence_level),
            "expected_shortfall": expected_shortfall(
                portfolio_returns,
                confidence_level,
            ),
            "max_drawdown": max_drawdown(cumulative_returns),
        },
        "correlation_matrix": correlations.to_dict(),
        "latest_cumulative_return": float(cumulative_returns.iloc[-1]),
        "number_of_observations": int(len(portfolio_returns)),
        "analysis_timestamp": datetime.now(UTC).isoformat(),
    }
