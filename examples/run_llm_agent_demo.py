from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tool_registry import list_registered_tools
from src.workflow import run_risk_workflow


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Skipping LLM agent demo.")
        return

    query = (
        "Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT. "
        "Focus on downside risk and concentration risk."
    )

    result = run_risk_workflow(query, use_llm=True)

    print("FinRisk Agent - Agentic Risk Workflow Demo")
    print("==========================================")
    print(f"Original query: {result.query}")
    print()
    print("Registered Risk Tools")
    for tool in list_registered_tools():
        print(f"- {tool.name}: {tool.description}")
    print()
    print("Agentic Workflow Plan")
    for step in result.plan.steps:
        print(
            f"- {step.name} [{step.tool_name}]: "
            f"{step.status} - {step.output_summary}"
        )
    print()
    print("Parsed portfolio:")
    print(f"Tickers: {result.parsed_portfolio['tickers']}")
    print(f"Weights: {result.parsed_portfolio['weights']}")
    print()
    print("Risk metrics:")
    metrics = result.risk_report["risk_metrics"]
    print(f"Annualized volatility: {metrics['annualized_volatility']:.2%}")
    print(f"95% historical VaR: {metrics['historical_var']:.2%}")
    print(f"95% Expected Shortfall: {metrics['expected_shortfall']:.2%}")
    print(f"Maximum drawdown: {metrics['max_drawdown']:.2%}")
    print()
    print("Retrieved Methodology Notes")
    for doc in result.methodology_notes:
        print(f"- {doc['title']}")
    print()
    print("LLM commentary:")
    print(result.llm_commentary)
    print()
    print("Report Validation")
    validation_status = "PASSED" if result.validation_result.passed else "FAILED"
    print(f"Overall validation status: {validation_status}")
    for check in result.validation_result.checks:
        check_status = "PASSED" if check.passed else "FAILED"
        print(f"- {check.name}: {check_status} - {check.message}")

    if result.validation_result.warnings:
        print("Warnings:")
        for warning in result.validation_result.warnings:
            print(f"- {warning}")

    if result.validation_result.errors:
        print("Errors:")
        for error in result.validation_result.errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
