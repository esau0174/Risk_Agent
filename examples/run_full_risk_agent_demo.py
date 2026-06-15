from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.demo_utils import (
    print_execution_trace,
    print_input_summary,
    print_methodology_notes,
    print_registered_tools_by_module,
    print_validation_result,
    print_workflow_plan,
)
from src.core.tool_registry import list_registered_tools
from src.workflow import run_risk_workflow


MARKET_QUERY = "Analyze the uploaded portfolio for downside risk and concentration risk."
CREDIT_QUERY = (
    "Analyze the counterparty exposure profile and summarize PFE concentration."
)
MARKET_DATA_FILE = "examples/sample_portfolio.csv"
CREDIT_DATA_FILE = "examples/sample_exposure_profile.csv"
CONFIG_FILE = "examples/sample_risk_config.json"


def main() -> None:
    market_result = run_risk_workflow(
        MARKET_QUERY,
        data_file=MARKET_DATA_FILE,
        config_file=CONFIG_FILE,
        use_llm=False,
    )
    credit_result = run_risk_workflow(
        CREDIT_QUERY,
        data_file=CREDIT_DATA_FILE,
        use_llm=False,
    )

    print("FinRisk Agent - Full Risk Workflow Demo")
    print("=======================================")
    print_executive_summary(market_result, credit_result)
    print_registered_tools_by_module(list_registered_tools())
    print_market_workflow(market_result)
    print_credit_workflow(credit_result)


def print_executive_summary(market_result, credit_result) -> None:
    market_metrics = market_result.risk_report["risk_metrics"]
    pfe_metrics = credit_result.pfe_result
    stress_loss = (
        market_result.stress_test_results[0]["portfolio_loss_pct"]
        if market_result.stress_test_results
        else None
    )

    print("Combined Executive Summary")
    print("- Active modules covered: Market Risk, Credit Risk")
    print("- Market Risk:")
    print(
        "  Annualized volatility: "
        f"{market_metrics['annualized_volatility']:.2%}"
    )
    print(f"  95% historical VaR: {market_metrics['historical_var']:.2%}")
    print(f"  95% Expected Shortfall: {market_metrics['expected_shortfall']:.2%}")
    print(f"  Maximum drawdown: {market_metrics['max_drawdown']:.2%}")
    if stress_loss is not None:
        print(f"  Stress scenario loss: {stress_loss:.2%}")
    print("- Credit Risk / PFE:")
    print(f"  Peak 95% PFE: {pfe_metrics['peak_pfe_95']:,.2f}")
    if pfe_metrics.get("peak_pfe_99") is not None:
        print(f"  Peak 99% PFE: {pfe_metrics['peak_pfe_99']:,.2f}")
    print(f"  EPE: {pfe_metrics['epe']:,.2f}")
    print(
        "  Largest netting set: "
        f"{pfe_metrics['largest_netting_set_by_peak_pfe']}"
    )
    print(
        "- Market validation: "
        f"{_validation_status(market_result.validation_result)}"
    )
    print(
        "- Credit validation: "
        f"{_validation_status(credit_result.validation_result)}"
    )
    print()


def print_market_workflow(result) -> None:
    print("Market Risk Workflow")
    print("--------------------")
    print_input_summary(
        MARKET_QUERY,
        MARKET_DATA_FILE,
        CONFIG_FILE,
        result.active_modules,
    )
    print_workflow_plan(result.plan)
    print_execution_trace(result.execution_trace)

    metrics = result.risk_report["risk_metrics"]
    print("Market Risk Results")
    print(f"- Annualized volatility: {metrics['annualized_volatility']:.2%}")
    print(f"- 95% historical VaR: {metrics['historical_var']:.2%}")
    print(f"- 95% Expected Shortfall: {metrics['expected_shortfall']:.2%}")
    print(f"- Maximum drawdown: {metrics['max_drawdown']:.2%}")
    print()

    if result.stress_test_results:
        print("Stress Test Results")
        for scenario in result.stress_test_results:
            print(f"- {scenario['scenario_name']}: {scenario['portfolio_loss_pct']:.2%} loss")
        print()

    print_methodology_notes(result.methodology_notes)
    print("Commentary")
    print(result.llm_commentary)
    print()
    print_validation_result(result.validation_result)
    print()


def print_credit_workflow(result) -> None:
    print("Credit Risk / PFE Workflow")
    print("--------------------------")
    print_input_summary(
        CREDIT_QUERY,
        CREDIT_DATA_FILE,
        active_modules=result.active_modules,
    )
    print_workflow_plan(result.plan)
    print_execution_trace(result.execution_trace)

    metrics = result.pfe_result
    print("Credit Risk Results / PFE Metrics")
    print(f"- Peak 95% PFE: {metrics['peak_pfe_95']:,.2f}")
    if metrics.get("peak_pfe_99") is not None:
        print(f"- Peak 99% PFE: {metrics['peak_pfe_99']:,.2f}")
    print(f"- EPE: {metrics['epe']:,.2f}")
    print(
        "- Largest netting set: "
        f"{metrics['largest_netting_set_by_peak_pfe']}"
    )
    print()

    print_methodology_notes(result.methodology_notes)
    print("Commentary")
    print(result.llm_commentary)
    print()
    print_validation_result(result.validation_result)


def _validation_status(validation_result) -> str:
    return "PASSED" if validation_result.passed else "FAILED"


if __name__ == "__main__":
    main()
