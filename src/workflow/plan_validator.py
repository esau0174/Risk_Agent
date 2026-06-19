"""Deterministic validation gate for proposed workflow plans."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.tool_registry import get_tool
from src.workflow.types import WorkflowPlan


UNSUPPORTED_REGULATORY_TOOL_TERMS = (
    "sa_ccr",
    "simm",
    "regim",
    "capital",
    "margin",
)


@dataclass
class PlanValidationResult:
    passed: bool
    errors: list[str]
    warnings: list[str]


def validate_workflow_plan(plan: WorkflowPlan) -> PlanValidationResult:
    """Reject unknown, unsupported, or misordered tools before execution."""
    errors: list[str] = []
    warnings: list[str] = []
    tool_names = [step.tool_name for step in plan.steps]

    for tool_name in tool_names:
        # Regulatory capital and margin calculators are intentionally not exposed.
        if _is_unsupported_regulatory_capital_tool(tool_name):
            errors.append(
                f"Unsupported regulatory capital or margin tool requested: {tool_name}."
            )
            continue
        try:
            get_tool(tool_name)
        except KeyError:
            errors.append(f"Unknown or unregistered tool requested: {tool_name}.")

    _require_order(tool_names, "validate_portfolio", "calculate_risk_metrics", errors)
    _require_order(tool_names, "load_risk_config", "calculate_risk_metrics", errors)
    _require_order(tool_names, "load_risk_config", "calculate_pfe_metrics", errors)
    _require_order(tool_names, "load_sensitivity_file", "validate_sensitivity_file", errors)
    _require_order(tool_names, "validate_sensitivity_file", "aggregate_greeks", errors)
    _require_order(tool_names, "aggregate_greeks", "assess_regulatory_readiness", errors)

    for analytics_tool in (
        "calculate_risk_metrics",
        "calculate_pfe_metrics",
        "run_stress_test",
        "aggregate_greeks",
    ):
        _require_order(tool_names, analytics_tool, "generate_commentary", errors)

    _require_order(tool_names, "generate_commentary", "validate_report", errors)

    if "assess_regulatory_readiness" in tool_names and any(
        _is_unsupported_regulatory_capital_tool(tool_name)
        for tool_name in tool_names
    ):
        errors.append(
            "Regulatory readiness may be assessed, but unsupported capital or margin "
            "calculation tools must not be executed."
        )

    return PlanValidationResult(
        passed=not errors,
        errors=errors,
        warnings=warnings,
    )


def _require_order(
    tool_names: list[str],
    before_tool: str,
    after_tool: str,
    errors: list[str],
) -> None:
    if before_tool not in tool_names or after_tool not in tool_names:
        return
    if tool_names.index(before_tool) > tool_names.index(after_tool):
        errors.append(f"{before_tool} must occur before {after_tool}.")


def _is_unsupported_regulatory_capital_tool(tool_name: str) -> bool:
    if tool_name == "assess_regulatory_readiness":
        return False
    normalized = tool_name.lower()
    return any(term in normalized for term in UNSUPPORTED_REGULATORY_TOOL_TERMS)
