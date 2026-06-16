from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflow import AGENT_SCENARIOS, run_agent_workflow


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    result = run_agent_workflow(query=args.query, scenario=args.scenario)

    print("RiskFlow Agent - Autonomous Planning Demo")
    print("=========================================")
    print("Planning mode: controlled autonomous proposal with deterministic validation")
    print()
    print("Planning Summary")
    print(f"- Scenario: {result.scenario}")
    print(f"- Query: {result.query}")
    print(f"- Detected modules: {', '.join(result.detected_modules)}")
    print(f"- Proposed tool count: {len(result.proposed_plan.steps)}")
    print(
        "- Plan validation: "
        f"{'PASSED' if result.plan_validation_result.passed else 'FAILED'}"
    )
    if result.plan_validation_result.errors:
        print("- Errors: " + "; ".join(result.plan_validation_result.errors))
    if result.plan_validation_result.warnings:
        print("- Warnings: " + "; ".join(result.plan_validation_result.warnings))
    print()

    if not result.plan_validation_result.passed:
        print(result.final_report_summary)
        return

    if args.show_plan:
        print("Approved Tool Sequence")
        _print_plan(result.approved_plan, scenario=result.scenario)
        print()

    print("Final Report Summary")
    print(result.final_report_summary)


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
                    "Load counterparty exposure profile for Credit Risk analysis.",
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
        choices=sorted(AGENT_SCENARIOS),
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
