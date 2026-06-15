from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.tool_registry import list_registered_tools
from src.workflow import run_risk_workflow
from examples.demo_utils import (
    print_execution_trace,
    print_input_summary,
    print_methodology_notes,
    print_registered_tools_by_module,
    print_validation_result,
    print_workflow_plan,
)


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Skipping LLM agent demo.")
        return

    query = "Analyze the uploaded portfolio for downside risk and concentration risk."
    data_file = "examples/sample_portfolio.csv"
    config_file = "examples/sample_risk_config.json"

    result = run_risk_workflow(
        query,
        use_llm=True,
        data_file=data_file,
        config_file=config_file,
    )

    print("FinRisk Agent - Agentic Risk Workflow Demo")
    print("==========================================")
    print_input_summary(query, data_file, config_file, result.active_modules)
    print_registered_tools_by_module(list_registered_tools())
    print_workflow_plan(result.plan)
    print_execution_trace(result.execution_trace)
    print("Parsed portfolio:")
    print(f"Tickers: {result.parsed_portfolio['tickers']}")
    print(f"Weights: {result.parsed_portfolio['weights']}")
    print()
    print("Market Risk Results")
    metrics = result.risk_report["risk_metrics"]
    print(f"Annualized volatility: {metrics['annualized_volatility']:.2%}")
    print(f"95% historical VaR: {metrics['historical_var']:.2%}")
    print(f"95% Expected Shortfall: {metrics['expected_shortfall']:.2%}")
    print(f"Maximum drawdown: {metrics['max_drawdown']:.2%}")
    print()
    if result.stress_test_results:
        print("Stress Test Results")
        for scenario in result.stress_test_results:
            print(f"- Scenario: {scenario['scenario_name']}")
            print(f"  Base portfolio value: {scenario['base_portfolio_value']:.2f}")
            print(
                "  Stressed portfolio value: "
                f"{scenario['stressed_portfolio_value']:.2f}"
            )
            print(f"  Portfolio loss: {scenario['portfolio_loss_pct']:.2%}")
            print("  Per-ticker contributions:")
            for ticker, contribution in scenario["per_ticker_contributions"].items():
                print(
                    f"    {ticker}: "
                    f"{contribution['portfolio_loss_contribution_pct']:.2%}"
                )
        print()
    print_methodology_notes(result.methodology_notes)
    print("Commentary")
    print(result.llm_commentary)
    print()
    print_validation_result(result.validation_result)


if __name__ == "__main__":
    main()
