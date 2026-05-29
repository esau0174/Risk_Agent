from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


def main() -> None:
    tickers = ["SPY", "QQQ", "NVDA", "TLT"]
    weights = [0.4, 0.3, 0.2, 0.1]
    start_date = "2023-01-01"

    prices = download_price_data(tickers, start_date)
    asset_returns = calculate_asset_returns(prices)
    portfolio_returns = calculate_portfolio_returns(asset_returns, weights)
    cumulative_returns = calculate_cumulative_returns(portfolio_returns)

    print("Phase 1 Risk Analytics Demo")
    print("===========================")
    print(f"Annualized volatility: {annualized_volatility(portfolio_returns):.2%}")
    print(f"95% historical VaR: {historical_var(portfolio_returns, 0.95):.2%}")
    print(f"95% Expected Shortfall: {expected_shortfall(portfolio_returns, 0.95):.2%}")
    print(f"Maximum drawdown: {max_drawdown(cumulative_returns):.2%}")
    print(f"Latest cumulative return: {cumulative_returns.iloc[-1]:.2%}")
    print()
    print("Correlation matrix:")
    print(correlation_matrix(asset_returns).round(4))


if __name__ == "__main__":
    main()
