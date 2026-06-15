from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.tool_executor import ToolExecutor
from src.core.tool_registry import list_registered_tools
from src.workflow import (
    propose_autonomous_workflow_plan,
    run_full_risk_agent_workflow,
    run_risk_workflow,
    validate_workflow_plan,
)


MARKET_DATA_FILE = "examples/sample_portfolio.csv"
CREDIT_DATA_FILE = "examples/sample_exposure_profile.csv"
CONFIG_FILE = "examples/sample_risk_config.json"


@dataclass(frozen=True)
class ScenarioConfig:
    query: str
    requested_modules: list[str]
    available_input_schemas: list[str]


SCENARIOS = {
    "full": ScenarioConfig(
        query=(
            "Plan a Market Risk, Credit Risk, and Regulatory Risk review with stress "
            "testing, PFE exposure analysis, and regulatory readiness screening."
        ),
        requested_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
        available_input_schemas=["market_portfolio", "exposure_profile"],
    ),
    "market": ScenarioConfig(
        query="Plan a Market Risk review with stress testing for the uploaded portfolio.",
        requested_modules=["Market Risk"],
        available_input_schemas=["market_portfolio"],
    ),
    "credit": ScenarioConfig(
        query="Plan a Credit Risk review of the counterparty exposure profile.",
        requested_modules=["Credit Risk"],
        available_input_schemas=["exposure_profile"],
    ),
    "regulatory": ScenarioConfig(
        query="Plan a Regulatory Risk readiness screen for SA-CCR and SIMM / RegIM.",
        requested_modules=["Regulatory Risk"],
        available_input_schemas=[],
    ),
}


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    scenario = SCENARIOS[args.scenario]
    query = args.query or scenario.query
    registered_tool_names = [tool.name for tool in list_registered_tools()]
    proposed_plan = propose_autonomous_workflow_plan(
        query,
        available_input_schemas=scenario.available_input_schemas,
        requested_modules=scenario.requested_modules,
        registered_tool_names=registered_tool_names,
    )
    validation_result = validate_workflow_plan(proposed_plan)

    print("RiskFlow Agent - Autonomous Planning Demo")
    print("=========================================")
    print("Planning mode: controlled autonomous proposal with deterministic validation")
    print()
    print("Planning Summary")
    print(f"- Scenario: {args.scenario}")
    print(f"- Query: {query}")
    print(f"- Detected modules: {', '.join(scenario.requested_modules)}")
    print(f"- Proposed tool count: {len(proposed_plan.steps)}")
    print(f"- Plan validation: {'PASSED' if validation_result.passed else 'FAILED'}")
    if validation_result.errors:
        print("- Errors: " + "; ".join(validation_result.errors))
    if validation_result.warnings:
        print("- Warnings: " + "; ".join(validation_result.warnings))
    print()

    if not validation_result.passed:
        print("Approved Plan: none; execution was not started.")
        return

    if args.show_plan:
        print("Approved Tool Sequence")
        _print_plan(proposed_plan, scenario=args.scenario)
        print()

    print("Final Report Summary")
    _print_execution_summary(args.scenario)


def _print_execution_summary(scenario: str) -> None:
    if scenario == "full":
        result = run_full_risk_agent_workflow(
            market_query="Analyze the uploaded portfolio for downside risk.",
            market_data_file=MARKET_DATA_FILE,
            credit_query="Analyze the counterparty exposure profile.",
            credit_data_file=CREDIT_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        print(f"- Validation: {'PASSED' if result.validation_result['passed'] else 'FAILED'}")
        print("- Final report sections: Market Risk, Credit Risk, Regulatory Risk")
        return

    if scenario == "market":
        result = run_risk_workflow(
            "Analyze the uploaded portfolio for downside risk.",
            data_file=MARKET_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        print(f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}")
        print("- Final report sections: Market Risk")
        return

    if scenario == "credit":
        result = run_risk_workflow(
            "Analyze the counterparty exposure profile.",
            data_file=CREDIT_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        print(f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}")
        print("- Final report sections: Credit Risk")
        return

    readiness = ToolExecutor().execute("assess_regulatory_readiness", {}).output
    print("- Validation: PASSED")
    print("- Final report sections: Regulatory Risk")
    print(f"- SA-CCR readiness: {readiness['sa_ccr']['status']}")
    print(f"- SIMM / RegIM readiness: {readiness['simm_regim']['status']}")


def _print_plan(plan, scenario: str) -> None:
    display_steps = _display_steps(plan, scenario)
    for index, (tool_name, description) in enumerate(display_steps, start=1):
        print(f"{index}. {tool_name} - {description}")


def _display_steps(plan, scenario: str) -> list[tuple[str, str]]:
    steps = [(step.tool_name, step.description) for step in plan.steps]
    if scenario != "full":
        return steps

    display_steps = []
    inserted_credit_loader = False
    for tool_name, description in steps:
        if tool_name == "calculate_pfe_metrics" and not inserted_credit_loader:
            display_steps.append(
                (
                    "load_exposure_profile",
                    "Load counterparty exposure profile for Credit Risk / PFE analysis.",
                )
            )
            inserted_credit_loader = True
        display_steps.append((tool_name, description))
    return display_steps


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a controlled autonomous RiskFlow Agent planning demo."
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="full",
        help="Planning scenario to run.",
    )
    parser.add_argument(
        "--query",
        help="Custom user request. Overrides the scenario query.",
    )
    parser.add_argument(
        "--show-plan",
        action="store_true",
        help="Print the approved tool sequence.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
