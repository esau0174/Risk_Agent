from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflow import AGENT_SCENARIOS, run_agent_workflow


DEFAULT_TRACE_FILE = "logs/riskflow_agent_trace.json"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    result = run_agent_workflow(
        query=args.query,
        scenario=args.scenario,
        planner_mode=args.planner,
    )

    print("RiskFlow Agent Demo")
    print("===================")
    print()
    print("User Request")
    print(result.query)
    print()
    print("Input Context")
    print(f"- Scenario: {result.scenario}")
    print(f"- Requested modules: {_requested_modules_text(result)}")
    print(f"- Available input schemas: {_available_input_schemas_text(result)}")
    print()
    print("Autonomous Planning Summary")
    print(f"- Planner: {result.planner_message}")
    if result.orchestration_trace.get("execution_mode"):
        print(f"- Execution mode: {result.orchestration_trace['execution_mode']}")
    if result.orchestration_trace.get("selected_route"):
        print(f"- Selected route: {result.orchestration_trace['selected_route']}")
    approved_tool_count = (
        len(_display_steps(result.approved_plan, result.scenario))
        if result.approved_plan is not None
        else 0
    )
    print(f"- Approved tool count: {approved_tool_count}")
    print(
        "- Plan validation: "
        f"{'PASSED' if result.plan_validation_result.passed else 'FAILED'}"
    )
    if result.plan_validation_result.errors:
        print("- Errors: " + "; ".join(result.plan_validation_result.errors))
    if result.plan_validation_result.warnings:
        print("- Warnings: " + "; ".join(result.plan_validation_result.warnings))
    if result.planner_warnings:
        print("- Planner warnings: " + "; ".join(result.planner_warnings))
    print()

    if not result.plan_validation_result.passed:
        print(result.final_report_summary)
        return

    if args.show_plan:
        print("Approved Tool Sequence")
        _print_plan(result.approved_plan, scenario=result.scenario)
        print()

    print("Execution Trace")
    print(f"- Execution mode: {result.orchestration_trace.get('execution_mode', 'unknown')}")
    print(f"- Selected route: {result.orchestration_trace.get('selected_route') or 'none'}")
    executed_tools = result.orchestration_trace.get("executed_tools") or []
    skipped_tools = result.orchestration_trace.get("skipped_or_unsupported_tools") or []
    print(f"- Executed tools: {', '.join(executed_tools) if executed_tools else 'none'}")
    print(
        "- Skipped / unsupported tools: "
        f"{', '.join(skipped_tools) if skipped_tools else 'none'}"
    )
    route_mapping_note = result.orchestration_trace.get("route_mapping_note")
    if route_mapping_note:
        print(f"- Route mapping note: {route_mapping_note}")
    print()

    print("Risk Report")
    print(result.user_report or result.final_report_summary)
    print()
    print("Validation / Guardrail Summary")
    print(_validation_summary(result.validation_result))

    if args.trace_file:
        save_execution_trace(result, args.trace_file)


def save_execution_trace(result, trace_file: str | Path) -> Path:
    """Write the structured execution trace to a JSON file."""
    path = Path(trace_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "orchestration_trace": result.orchestration_trace,
                "execution_trace": result.execution_trace,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _print_plan(plan, scenario: str) -> None:
    for index, (tool_name, description) in enumerate(
        _display_steps(plan, scenario),
        start=1,
    ):
        print(f"{index}. {tool_name} - {description}")


def _display_steps(plan, scenario: str) -> list[tuple[str, str]]:
    steps = [(step.tool_name, step.description) for step in plan.steps]
    if scenario != "full":
        return steps

    display_steps = []
    inserted_credit_loader = False
    for tool_name, description in steps:
        if tool_name == "load_exposure_profile":
            inserted_credit_loader = True
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


def _available_input_schemas(detected_modules: list[str]) -> list[str]:
    schemas: list[str] = []
    if "Market Risk" in detected_modules:
        schemas.append("market_portfolio")
    if "Credit Risk" in detected_modules:
        schemas.append("exposure_profile")
    return schemas


def _requested_modules_text(result) -> str:
    if not result.detected_modules and not result.approved_plan:
        return "unavailable because planning failed"
    return ", ".join(result.detected_modules) or "none"


def _available_input_schemas_text(result) -> str:
    if not result.detected_modules and not result.approved_plan:
        return "unavailable because planning failed"
    return ", ".join(_available_input_schemas(result.detected_modules)) or "none"


def _validation_summary(validation_result) -> str:
    if validation_result is None:
        return "- Validation: NOT_RUN"
    if isinstance(validation_result, dict):
        status = "PASSED" if validation_result.get("passed") else "FAILED"
        lines = [f"- Validation: {status}"]
        for name in ("market_risk", "credit_risk", "regulatory_risk"):
            domain_result = validation_result.get(name)
            if isinstance(domain_result, dict):
                domain_status = "PASSED" if domain_result.get("passed") else "FAILED"
                lines.append(f"- {name.replace('_', ' ').title()}: {domain_status}")
        return "\n".join(lines)

    status = "PASSED" if getattr(validation_result, "passed", False) else "FAILED"
    return f"- Validation: {status}"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the primary RiskFlow Agent autonomous workflow demo."
    )
    parser.add_argument(
        "--planner",
        choices=("auto", "llm", "rule"),
        default="auto",
        help="Planner mode. Auto uses LLM planning when available, otherwise rule fallback.",
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
    parser.add_argument(
        "--trace-file",
        nargs="?",
        const=DEFAULT_TRACE_FILE,
        help=(
            "Optionally save the internal execution trace as JSON. "
            f"Defaults to {DEFAULT_TRACE_FILE} when no path is supplied."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
