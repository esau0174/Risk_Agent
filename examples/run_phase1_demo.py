from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.market_risk.risk_report import generate_portfolio_risk_report


def main() -> None:
    tickers = ["SPY", "QQQ", "NVDA", "TLT"]
    weights = [0.4, 0.3, 0.2, 0.1]
    start_date = "2023-01-01"

    report = generate_portfolio_risk_report(tickers, weights, start_date)
    metrics = report["risk_metrics"]

    print("Phase 1 Risk Analytics Demo")
    print("===========================")
    print(f"Annualized volatility: {metrics['annualized_volatility']:.2%}")
    print(f"95% historical VaR: {metrics['historical_var']:.2%}")
    print(f"95% Expected Shortfall: {metrics['expected_shortfall']:.2%}")
    print(f"Maximum drawdown: {metrics['max_drawdown']:.2%}")
    print(f"Latest cumulative return: {report['latest_cumulative_return']:.2%}")
    print(f"Number of observations: {report['number_of_observations']}")
    print(f"Analysis timestamp: {report['analysis_timestamp']}")
    print()
    print("Correlation matrix:")
    print(pd.DataFrame(report["correlation_matrix"]).round(4))


if __name__ == "__main__":
    main()
