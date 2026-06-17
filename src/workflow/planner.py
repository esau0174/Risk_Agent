from __future__ import annotations

from enum import Enum

from src.data.portfolio_loader import ExposureProfile
from src.core.tool_registry import get_tool
from src.workflow.types import ExecutionTraceEntry, WorkflowPlan, WorkflowStep


class Intent(str, Enum):
    PORTFOLIO_RISK = "portfolio_risk"
    METHODOLOGY_EXPLANATION = "methodology_explanation"
    STRESS_TEST = "stress_test"
    REPORT_VALIDATION = "report_validation"


def resolve_data_file(
    data_file: str | None,
    portfolio_file: str | None,
) -> str | None:
    if data_file is not None and portfolio_file is not None:
        raise ValueError("Provide either data_file or portfolio_file, not both.")
    return data_file if data_file is not None else portfolio_file


def detect_data_route(loaded_data: object) -> str:
    """Identify the workflow route for loaded structured data."""
    if isinstance(loaded_data, ExposureProfile):
        return "credit_risk"
    return "market_risk"


def build_risk_workflow_plan(query: str) -> WorkflowPlan:
    """Build a deterministic, explicit plan for the risk analysis workflow."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string.")
    return build_workflow_plan_for_intent(Intent.PORTFOLIO_RISK)


def classify_intent(user_query: str) -> Intent:
    """Classify a user query with deterministic keyword rules."""
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("User query must be a non-empty string.")

    normalized_query = " ".join(user_query.lower().split())
    if any(keyword in normalized_query for keyword in ("stress", "shock", "scenario", "selloff")):
        return Intent.STRESS_TEST
    if any(
        phrase in normalized_query
        for phrase in ("methodology", "explain", "how is", "how are", "definition")
    ):
        return Intent.METHODOLOGY_EXPLANATION
    if any(
        phrase in normalized_query
        for phrase in ("validate", "check report", "review report")
    ):
        return Intent.REPORT_VALIDATION
    return Intent.PORTFOLIO_RISK


def build_workflow_plan_for_intent(intent: Intent) -> WorkflowPlan:
    """Build a deterministic plan for an already-classified intent."""
    if not isinstance(intent, Intent):
        raise ValueError("Intent must be an Intent enum value.")

    if intent is Intent.PORTFOLIO_RISK:
        return WorkflowPlan(
            objective="Analyze a risk workflow from a natural-language query.",
            steps=[
                registered_step("parse_portfolio"),
                registered_step("validate_portfolio"),
                registered_step("load_risk_config"),
                registered_step("calculate_risk_metrics"),
                registered_step("retrieve_methodology"),
                registered_step("generate_commentary"),
                registered_step("validate_report"),
            ],
        )
    if intent is Intent.METHODOLOGY_EXPLANATION:
        return WorkflowPlan(
            objective="Explain financial risk methodology using local reference notes.",
            steps=[registered_step("retrieve_methodology"), registered_step("generate_commentary")],
        )
    if intent is Intent.STRESS_TEST:
        return WorkflowPlan(
            objective="Plan a portfolio stress-test analysis.",
            steps=[
                WorkflowStep(
                    name="stress_test",
                    description=(
                        "Placeholder for a future stress-test workflow; no stress tool is "
                        "registered or executed yet."
                    ),
                    status="pending",
                    tool_name="stress_test",
                )
            ],
        )
    return WorkflowPlan(
        objective="Validate an existing generated risk report.",
        steps=[registered_step("validate_report")],
    )


def build_file_portfolio_workflow_plan() -> WorkflowPlan:
    return WorkflowPlan(
        objective="Analyze risk for a structured data file using a natural-language instruction.",
        steps=[
            registered_step("load_portfolio_file"),
            registered_step("validate_portfolio"),
            registered_step("load_risk_config"),
            registered_step("calculate_risk_metrics"),
            registered_step("retrieve_methodology"),
            registered_step("generate_commentary"),
            registered_step("validate_report"),
        ],
    )


def build_exposure_profile_workflow_plan() -> WorkflowPlan:
    return WorkflowPlan(
        objective="Analyze counterparty exposure profile and PFE metrics.",
        steps=[
            registered_step("load_portfolio_file"),
            registered_step("load_risk_config"),
            registered_step("calculate_pfe_metrics"),
            registered_step("retrieve_methodology"),
            registered_step("generate_commentary"),
            registered_step("validate_report"),
        ],
    )


def registered_step(tool_name: str) -> WorkflowStep:
    tool = get_tool(tool_name)
    return WorkflowStep(
        name=tool.name,
        description=tool.description,
        status="pending",
        tool_name=tool.name,
    )


def insert_step_after(
    plan: WorkflowPlan,
    preceding_step_name: str,
    tool_name: str,
) -> None:
    if any(step.name == tool_name for step in plan.steps):
        return
    for index, step in enumerate(plan.steps):
        if step.name == preceding_step_name:
            plan.steps.insert(index + 1, registered_step(tool_name))
            return
    raise ValueError(f"Workflow step not found: {preceding_step_name}")


def infer_active_modules(execution_trace: list[ExecutionTraceEntry]) -> list[str]:
    """Infer active workflow modules from successfully executed tools."""
    successful_tools = {
        entry.tool_name for entry in execution_trace if entry.status == "success"
    }
    active_modules = ["shared"]
    if successful_tools & {"calculate_risk_metrics", "run_stress_test"}:
        active_modules.append("market_risk")
    if "calculate_pfe_metrics" in successful_tools:
        active_modules.append("credit_risk")
    return active_modules
