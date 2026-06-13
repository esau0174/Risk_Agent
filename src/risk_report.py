from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from src.market_data import download_price_data
from src.portfolio import (
    calculate_asset_returns,
    calculate_cumulative_returns,
    calculate_portfolio_returns,
)
from src.risk_config import RiskConfig
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
    risk_config: RiskConfig | None = None,
) -> dict:
    """Generate a high-level Phase 1 portfolio risk report."""
    ticker_list = list(tickers)
    weight_list = [float(weight) for weight in weights]

    if risk_config is not None:
        start_date = risk_config.market_data.start_date
        end_date = risk_config.market_data.end_date
        confidence_level = risk_config.var.confidence_level
        annualization_factor = risk_config.returns.annualization_factor
        enabled_metrics = set(risk_config.risk_metrics.enabled)
    else:
        annualization_factor = 252
        enabled_metrics = {
            "annualized_volatility",
            "historical_var",
            "expected_shortfall",
            "max_drawdown",
        }

    prices = download_price_data(ticker_list, start_date, end_date)
    asset_returns = calculate_asset_returns(prices)
    portfolio_returns = calculate_portfolio_returns(asset_returns, weight_list)
    cumulative_returns = calculate_cumulative_returns(portfolio_returns)

    correlations = correlation_matrix(asset_returns)

    calculated_metrics = {}
    if "annualized_volatility" in enabled_metrics:
        calculated_metrics["annualized_volatility"] = annualized_volatility(
            portfolio_returns,
            trading_days=annualization_factor,
        )
    if "historical_var" in enabled_metrics:
        calculated_metrics["historical_var"] = historical_var(
            portfolio_returns,
            confidence_level,
        )
    if "expected_shortfall" in enabled_metrics:
        calculated_metrics["expected_shortfall"] = expected_shortfall(
            portfolio_returns,
            confidence_level,
        )
    if "max_drawdown" in enabled_metrics:
        calculated_metrics["max_drawdown"] = max_drawdown(cumulative_returns)

    metadata = {
        "tickers": ticker_list,
        "weights": weight_list,
        "start_date": start_date,
        "end_date": end_date,
        "confidence_level": float(confidence_level),
    }
    if risk_config is not None:
        metadata.update(
            {
                "returns_frequency": risk_config.returns.frequency,
                "annualization_factor": annualization_factor,
                "var_method": risk_config.var.method,
                "enabled_risk_metrics": sorted(enabled_metrics),
            }
        )

    return {
        "metadata": metadata,
        "risk_metrics": calculated_metrics,
        "correlation_matrix": correlations.to_dict(),
        "latest_cumulative_return": float(cumulative_returns.iloc[-1]),
        "number_of_observations": int(len(portfolio_returns)),
        "analysis_timestamp": datetime.now(UTC).isoformat(),
    }
