from __future__ import annotations

from collections.abc import Iterable, Sequence

from src.core.tool_registry import get_tool, list_registered_tools
from src.workflow.types import WorkflowPlan, WorkflowStep


MODULE_ALIASES = {
    "market risk": "market_risk",
    "market_risk": "market_risk",
    "credit risk": "credit_risk",
    "credit_risk": "credit_risk",
    "pfe": "credit_risk",
    "regulatory risk": "regulatory_risk",
    "regulatory_risk": "regulatory_risk",
    "regulatory": "regulatory_risk",
    "sa-ccr": "regulatory_risk",
    "simm": "regulatory_risk",
    "regim": "regulatory_risk",
    "sensitivity risk": "sensitivity_risk",
    "sensitivity_risk": "sensitivity_risk",
    "sensitivity": "sensitivity_risk",
    "sensitivities": "sensitivity_risk",
    "greeks": "sensitivity_risk",
    "greek": "sensitivity_risk",
}


def propose_autonomous_workflow_plan(
    user_query: str,
    available_input_schemas: Sequence[str] | None = None,
    requested_modules: Sequence[str] | None = None,
    registered_tool_names: Iterable[str] | None = None,
) -> WorkflowPlan:
    """Propose a deterministic tool plan from user intent and available inputs."""
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query must be a non-empty string.")

    available_tools = set(
        registered_tool_names
        if registered_tool_names is not None
        else [tool.name for tool in list_registered_tools()]
    )
    schemas = {schema.lower() for schema in (available_input_schemas or [])}
    modules = _infer_requested_modules(user_query, requested_modules)
    selected_tools: list[str] = []

    if "market_risk" in modules:
        if "market_portfolio" in schemas or "portfolio" in schemas:
            selected_tools.append("load_portfolio_file")
        else:
            selected_tools.append("parse_portfolio")
        selected_tools.extend(
            [
                "validate_portfolio",
                "load_risk_config",
                "calculate_risk_metrics",
            ]
        )
        if _requests_stress(user_query):
            selected_tools.append("run_stress_test")

    if "credit_risk" in modules:
        if "exposure_profile" in schemas:
            selected_tools.append("load_exposure_profile")
        elif "load_portfolio_file" not in selected_tools:
            selected_tools.append("load_portfolio_file")
        if "load_risk_config" not in selected_tools:
            selected_tools.append("load_risk_config")
        selected_tools.append("calculate_pfe_metrics")

    if "regulatory_risk" in modules:
        selected_tools.append("assess_regulatory_readiness")

    if "sensitivity_risk" in modules:
        selected_tools.extend(
            [
                "load_sensitivity_file",
                "validate_sensitivity_file",
                "aggregate_greeks",
            ]
        )

    if any(module in modules for module in ("market_risk", "credit_risk")):
        selected_tools.extend(
            ["retrieve_methodology", "generate_commentary", "validate_report"]
        )

    proposed_tools = [
        tool_name for tool_name in selected_tools if tool_name in available_tools
    ]
    return WorkflowPlan(
        objective="Autonomously propose a guarded RiskFlow Agent workflow.",
        steps=[_registered_step(tool_name) for tool_name in proposed_tools],
    )


def _infer_requested_modules(
    user_query: str,
    requested_modules: Sequence[str] | None,
) -> set[str]:
    modules = {
        MODULE_ALIASES.get(module.strip().lower(), module.strip().lower())
        for module in (requested_modules or [])
    }
    normalized_query = user_query.lower()
    for phrase, module in MODULE_ALIASES.items():
        if phrase in normalized_query:
            modules.add(module)
    if not modules:
        modules.add("market_risk")
    return modules


def _requests_stress(user_query: str) -> bool:
    normalized_query = user_query.lower()
    return any(
        keyword in normalized_query
        for keyword in ("stress", "shock", "scenario", "selloff")
    )


def _registered_step(tool_name: str) -> WorkflowStep:
    tool = get_tool(tool_name)
    return WorkflowStep(
        name=tool.name,
        description=tool.description,
        status="proposed",
        tool_name=tool.name,
    )
