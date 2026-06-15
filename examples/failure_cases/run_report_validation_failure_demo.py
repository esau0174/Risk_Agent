from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.demo_utils import print_validation_result
from src.report_validator import validate_generated_report


def main() -> None:
    parsed_portfolio = {"tickers": ["SPY", "QQQ"], "weights": [0.4, 0.6]}
    risk_report = {
        "risk_metrics": {
            "annualized_volatility": 0.20,
            "historical_var": 0.02,
            "expected_shortfall": 0.03,
            "max_drawdown": 0.15,
        }
    }
    commentary = (
        "Historical VaR is 9.00%. "
        "This commentary is for analytical demonstration only and does not "
        "constitute investment advice."
    )

    validation_result = validate_generated_report(
        parsed_portfolio=parsed_portfolio,
        risk_report=risk_report,
        methodology_notes=[],
        commentary=commentary,
    )

    print("Report Validation Failure Demo")
    print("==============================")
    print("Intentional inconsistency: reported VaR is 9.00%; calculated VaR is 2.00%.\n")
    print_validation_result(validation_result)


if __name__ == "__main__":
    main()
