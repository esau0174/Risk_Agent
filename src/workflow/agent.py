from __future__ import annotations

from dataclasses import dataclass

from src.core.tool_executor import ToolExecutor
from src.core.tool_registry import list_registered_tools
from src.validators.regulatory import validate_regulatory_readiness_report
from src.workflow.autonomous_planner import propose_autonomous_workflow_plan
from src.workflow.engine import run_risk_workflow
from src.workflow.plan_validator import validate_workflow_plan
from src.workflow.presentation import run_full_risk_agent_workflow
from src.workflow.types import AgentWorkflowResult, WorkflowPlan


MARKET_DATA_FILE = "examples/sample_portfolio.csv"
CREDIT_DATA_FILE = "examples/sample_exposure_profile.csv"
CONFIG_FILE = "examples/sample_risk_config.json"


@dataclass(frozen=True)
class AgentScenarioConfig:
    query: str
    requested_modules: list[str]
    available_input_schemas: list[str]


AGENT_SCENARIOS = {
    "full": AgentScenarioConfig(
        query=(
            "Plan a Market Risk, Credit Risk, and Regulatory Risk review with stress "
            "testing, PFE exposure analysis, and regulatory readiness screening."
        ),
        requested_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
        available_input_schemas=["market_portfolio", "exposure_profile"],
    ),
    "market": AgentScenarioConfig(
        query="Plan a Market Risk review with stress testing for the uploaded portfolio.",
        requested_modules=["Market Risk"],
        available_input_schemas=["market_portfolio"],
    ),
    "credit": AgentScenarioConfig(
        query="Plan a Credit Risk review of the counterparty exposure profile.",
        requested_modules=["Credit Risk"],
        available_input_schemas=["exposure_profile"],
    ),
    "regulatory": AgentScenarioConfig(
        query="Plan a Regulatory Risk readiness screen for SA-CCR and SIMM / RegIM.",
        requested_modules=["Regulatory Risk"],
        available_input_schemas=[],
    ),
}


def run_agent_workflow(
    query: str | None = None,
    scenario: str = "full",
    proposed_plan: WorkflowPlan | None = None,
) -> AgentWorkflowResult:
    """Run the policy-constrained autonomous planning workflow."""
    if scenario not in AGENT_SCENARIOS:
        supported = ", ".join(sorted(AGENT_SCENARIOS))
        raise ValueError(f"Unknown scenario '{scenario}'. Supported scenarios: {supported}.")

    scenario_config = AGENT_SCENARIOS[scenario]
    custom_query = query is not None
    effective_query = query or scenario_config.query
    requested_modules = None if custom_query else scenario_config.requested_modules
    available_input_schemas = (
        _default_input_schemas_for_query(effective_query)
        if custom_query
        else scenario_config.available_input_schemas
    )
    registered_tool_names = [tool.name for tool in list_registered_tools()]
    plan = proposed_plan or propose_autonomous_workflow_plan(
        effective_query,
        available_input_schemas=available_input_schemas,
        requested_modules=requested_modules,
        registered_tool_names=registered_tool_names,
    )
    plan_validation_result = validate_workflow_plan(plan)
    detected_modules = _detect_modules_from_plan(plan)
    execution_route = _execution_route_from_modules(detected_modules)

    if not plan_validation_result.passed:
        return AgentWorkflowResult(
            query=effective_query,
            scenario=scenario,
            detected_modules=detected_modules,
            proposed_plan=plan,
            plan_validation_result=plan_validation_result,
            approved_plan=None,
            user_report=None,
            final_report_summary="Approved Plan: none; execution was not started.",
            execution_trace=[],
            validation_result=None,
            raw_outputs={},
        )

    executed = _execute_approved_route(execution_route)
    return AgentWorkflowResult(
        query=effective_query,
        scenario=scenario,
        detected_modules=detected_modules,
        proposed_plan=plan,
        plan_validation_result=plan_validation_result,
        approved_plan=plan,
        user_report=executed["user_report"],
        final_report_summary=executed["final_report_summary"],
        execution_trace=executed["execution_trace"],
        validation_result=executed["validation_result"],
        raw_outputs=executed["raw_outputs"],
    )


def _execute_approved_route(route: str) -> dict:
    if route == "full":
        result = run_full_risk_agent_workflow(
            market_query="Analyze the uploaded portfolio for downside risk.",
            market_data_file=MARKET_DATA_FILE,
            credit_query="Analyze the counterparty exposure profile.",
            credit_data_file=CREDIT_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        user_report = _strip_legacy_report_title(result.user_report)
        return {
            "user_report": user_report,
            "final_report_summary": (
                f"- Validation: {'PASSED' if result.validation_result['passed'] else 'FAILED'}\n"
                "- Final report sections: Market Risk, Credit Risk, Regulatory Risk"
            ),
            "execution_trace": result.execution_trace,
            "validation_result": result.validation_result,
            "raw_outputs": result.raw_outputs,
        }

    if route == "market":
        result = run_risk_workflow(
            "Analyze the uploaded portfolio for downside risk.",
            data_file=MARKET_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        return {
            "user_report": _build_market_report(result),
            "final_report_summary": (
                f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}\n"
                "- Final report sections: Market Risk"
            ),
            "execution_trace": [entry.__dict__ for entry in result.execution_trace],
            "validation_result": result.validation_result,
            "raw_outputs": {"market_risk": result},
        }

    if route == "credit":
        result = run_risk_workflow(
            "Analyze the counterparty exposure profile.",
            data_file=CREDIT_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        return {
            "user_report": _build_credit_report(result),
            "final_report_summary": (
                f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}\n"
                "- Final report sections: Credit Risk"
            ),
            "execution_trace": [entry.__dict__ for entry in result.execution_trace],
            "validation_result": result.validation_result,
            "raw_outputs": {"credit_risk": result},
        }

    readiness = ToolExecutor().execute("assess_regulatory_readiness", {}).output
    report = _build_regulatory_report(readiness)
    validation_result = validate_regulatory_readiness_report(report, readiness)
    return {
        "user_report": report,
        "final_report_summary": (
            f"- Validation: {'PASSED' if validation_result.passed else 'FAILED'}\n"
            "- Final report sections: Regulatory Risk\n"
            f"- SA-CCR readiness: {readiness['sa_ccr']['status']}\n"
            f"- SIMM / RegIM readiness: {readiness['simm_regim']['status']}"
        ),
        "execution_trace": [
            {
                "step_number": 1,
                "tool_name": "assess_regulatory_readiness",
                "status": "success",
                "input_summary": "Available regulatory readiness inputs.",
                "output_summary": (
                    f"Assessed readiness with {len(readiness['missing_inputs'])} missing inputs."
                ),
                "error": None,
                "workflow": "regulatory_risk",
            }
        ],
        "validation_result": validation_result,
        "raw_outputs": {"regulatory_risk": readiness},
    }


def _default_input_schemas_for_query(query: str) -> list[str]:
    normalized = query.lower()
    schemas: list[str] = []
    if any(term in normalized for term in ("market", "portfolio", "var", "stress")):
        schemas.append("market_portfolio")
    if any(term in normalized for term in ("credit", "pfe", "exposure", "counterparty")):
        schemas.append("exposure_profile")
    if not schemas and "regulatory" not in normalized and "sa-ccr" not in normalized:
        schemas.append("market_portfolio")
    return schemas


def _detect_modules_from_plan(plan: WorkflowPlan) -> list[str]:
    tool_names = [step.tool_name for step in plan.steps]
    modules: list[str] = []
    if any(tool in tool_names for tool in ("calculate_risk_metrics", "run_stress_test")):
        modules.append("Market Risk")
    if "calculate_pfe_metrics" in tool_names:
        modules.append("Credit Risk")
    if "assess_regulatory_readiness" in tool_names:
        modules.append("Regulatory Risk")
    return modules or ["Market Risk"]


def _execution_route_from_modules(modules: list[str]) -> str:
    selected = set(modules)
    if selected == {"Market Risk"}:
        return "market"
    if selected == {"Credit Risk"}:
        return "credit"
    if selected == {"Regulatory Risk"}:
        return "regulatory"
    return "full"


def _strip_legacy_report_title(user_report: str) -> str:
    lines = user_report.splitlines()
    if lines[:2] == [
        "RiskFlow Agent - Full Risk Workflow Demo",
        "=======================================",
    ]:
        return "\n".join(lines[2:]).lstrip()
    return user_report


def _build_market_report(result) -> str:
    metrics = result.risk_report["risk_metrics"]
    lines = [
        "Market Risk",
        f"- Annualized volatility: {metrics['annualized_volatility']:.2%}",
        f"- 95% historical VaR: {metrics['historical_var']:.2%}",
        f"- 95% Expected Shortfall: {metrics['expected_shortfall']:.2%}",
        f"- Maximum drawdown: {metrics['max_drawdown']:.2%}",
    ]
    if result.stress_test_results:
        lines.append(
            f"- Stress scenario loss: {result.stress_test_results[0]['portfolio_loss_pct']:.2%}"
        )
    lines.extend(
        [
            f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}",
            "",
            "Market Risk Commentary",
            result.llm_commentary,
        ]
    )
    return "\n".join(lines)


def _build_credit_report(result) -> str:
    pfe_metrics = result.pfe_result
    lines = [
        "Credit Risk",
        f"- Peak 95% PFE: USD {pfe_metrics['peak_pfe_95']:,.2f}",
    ]
    if pfe_metrics.get("peak_pfe_99") is not None:
        lines.append(f"- Peak 99% PFE: USD {pfe_metrics['peak_pfe_99']:,.2f}")
    lines.extend(
        [
            f"- EPE: USD {pfe_metrics['epe']:,.2f}",
            (
                "- Largest netting set: "
                f"{pfe_metrics['largest_netting_set_by_peak_pfe']}"
            ),
            _limit_utilization_line(pfe_metrics),
            f"- Limit status: {pfe_metrics['limit_status']}",
            f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}",
            "",
            "Credit Risk Commentary",
            result.llm_commentary,
        ]
    )
    return "\n".join(lines)


def _build_regulatory_report(readiness: dict) -> str:
    return (
        "Regulatory Risk\n"
        f"- SA-CCR readiness: {readiness['sa_ccr']['status']}\n"
        f"- SIMM / RegIM readiness: {readiness['simm_regim']['status']}\n"
        f"- Regulatory capital calculation: {readiness['regulatory_capital_calculation']}\n"
        "- SA-CCR missing inputs: "
        f"{', '.join(readiness['sa_ccr']['missing_required_fields'])}\n"
        "- SIMM / RegIM missing inputs: "
        f"{', '.join(readiness['simm_regim']['missing_required_fields'])}\n"
        f"- Guardrail: {readiness['guardrail']}"
    )


def _limit_utilization_line(pfe_metrics: dict) -> str:
    if pfe_metrics.get("limit_utilization") is None:
        return "- Limit utilization: not available; no configured limit"
    return (
        f"- Limit utilization: {pfe_metrics['limit_utilization']:.2%} of "
        f"USD {pfe_metrics['configured_limit']:,.2f}"
    )
