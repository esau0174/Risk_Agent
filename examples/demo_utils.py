from __future__ import annotations

from collections.abc import Iterable

from src.tool_registry import RiskTool
from src.workflow import ExecutionTraceEntry, WorkflowPlan


MODULE_LABELS = {
    "shared": "Shared",
    "market_risk": "Market Risk",
    "credit_risk": "Credit Risk",
}


def print_input_summary(
    query: str,
    portfolio_file: str | None = None,
    config_file: str | None = None,
    active_modules: Iterable[str] | None = None,
) -> None:
    print("Input Summary")
    print(f"- Query: {query}")
    if portfolio_file:
        print(f"- Portfolio file: {portfolio_file}")
    if config_file:
        print(f"- Risk config: {config_file}")
    if active_modules:
        module_names = [MODULE_LABELS.get(module, module) for module in active_modules]
        print(f"- Active modules: {', '.join(module_names)}")
    print()


def print_registered_tools_by_module(tools: Iterable[RiskTool]) -> None:
    print("Registered Risk Tools")
    tool_list = list(tools)
    for module in ("shared", "market_risk", "credit_risk"):
        module_tools = [tool for tool in tool_list if tool.module == module]
        if not module_tools:
            continue
        print(f"{MODULE_LABELS[module]}:")
        for tool in module_tools:
            print(f"- {tool.name}: {tool.description}")
    print()


def print_workflow_plan(plan: WorkflowPlan) -> None:
    print("Workflow Plan")
    for step in plan.steps:
        print(
            f"- {step.name} [{step.tool_name}]: "
            f"{step.status} - {step.output_summary}"
        )
    print()


def print_execution_trace(execution_trace: Iterable[ExecutionTraceEntry]) -> None:
    print("Execution Trace")
    for entry in execution_trace:
        print(f"- Step {entry.step_number}: {entry.tool_name} [{entry.status}]")
        print(f"  Input: {entry.input_summary}")
        print(f"  Output: {entry.output_summary}")
        if entry.error:
            print(f"  Error: {entry.error}")
    print()


def print_methodology_notes(methodology_notes: Iterable[dict]) -> None:
    print("Retrieved Methodology Notes")
    for note in methodology_notes:
        print(f"- {note['title']}")
    print()


def print_validation_result(validation_result) -> None:
    print("Report Validation")
    status = "PASSED" if validation_result.passed else "FAILED"
    print(f"Overall validation status: {status}")
    for check in validation_result.checks:
        check_status = "PASSED" if check.passed else "FAILED"
        print(f"- {check.name}: {check_status} - {check.message}")
    if validation_result.warnings:
        print("Warnings:")
        for warning in validation_result.warnings:
            print(f"- {warning}")
    if validation_result.errors:
        print("Errors:")
        for error in validation_result.errors:
            print(f"- {error}")
