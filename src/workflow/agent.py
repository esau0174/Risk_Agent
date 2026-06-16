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
    effective_query = query or scenario_config.query
    registered_tool_names = [tool.name for tool in list_registered_tools()]
    plan = proposed_plan or propose_autonomous_workflow_plan(
        effective_query,
        available_input_schemas=scenario_config.available_input_schemas,
        requested_modules=scenario_config.requested_modules,
        registered_tool_names=registered_tool_names,
    )
    plan_validation_result = validate_workflow_plan(plan)

    if not plan_validation_result.passed:
        return AgentWorkflowResult(
            query=effective_query,
            scenario=scenario,
            detected_modules=scenario_config.requested_modules,
            proposed_plan=plan,
            plan_validation_result=plan_validation_result,
            approved_plan=None,
            user_report=None,
            final_report_summary="Approved Plan: none; execution was not started.",
            execution_trace=[],
            validation_result=None,
            raw_outputs={},
        )

    executed = _execute_approved_scenario(scenario)
    return AgentWorkflowResult(
        query=effective_query,
        scenario=scenario,
        detected_modules=scenario_config.requested_modules,
        proposed_plan=plan,
        plan_validation_result=plan_validation_result,
        approved_plan=plan,
        user_report=executed["user_report"],
        final_report_summary=executed["final_report_summary"],
        execution_trace=executed["execution_trace"],
        validation_result=executed["validation_result"],
        raw_outputs=executed["raw_outputs"],
    )


def _execute_approved_scenario(scenario: str) -> dict:
    if scenario == "full":
        result = run_full_risk_agent_workflow(
            market_query="Analyze the uploaded portfolio for downside risk.",
            market_data_file=MARKET_DATA_FILE,
            credit_query="Analyze the counterparty exposure profile.",
            credit_data_file=CREDIT_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        return {
            "user_report": result.user_report,
            "final_report_summary": (
                f"- Validation: {'PASSED' if result.validation_result['passed'] else 'FAILED'}\n"
                "- Final report sections: Market Risk, Credit Risk, Regulatory Risk"
            ),
            "execution_trace": result.execution_trace,
            "validation_result": result.validation_result,
            "raw_outputs": result.raw_outputs,
        }

    if scenario == "market":
        result = run_risk_workflow(
            "Analyze the uploaded portfolio for downside risk.",
            data_file=MARKET_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        return {
            "user_report": None,
            "final_report_summary": (
                f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}\n"
                "- Final report sections: Market Risk"
            ),
            "execution_trace": [entry.__dict__ for entry in result.execution_trace],
            "validation_result": result.validation_result,
            "raw_outputs": {"market_risk": result},
        }

    if scenario == "credit":
        result = run_risk_workflow(
            "Analyze the counterparty exposure profile.",
            data_file=CREDIT_DATA_FILE,
            config_file=CONFIG_FILE,
            use_llm=False,
        )
        return {
            "user_report": None,
            "final_report_summary": (
                f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}\n"
                "- Final report sections: Credit Risk"
            ),
            "execution_trace": [entry.__dict__ for entry in result.execution_trace],
            "validation_result": result.validation_result,
            "raw_outputs": {"credit_risk": result},
        }

    readiness = ToolExecutor().execute("assess_regulatory_readiness", {}).output
    report = (
        "Regulatory Risk\n"
        f"SA-CCR missing inputs: {', '.join(readiness['sa_ccr']['missing_required_fields'])}\n"
        "SIMM / RegIM missing inputs: "
        f"{', '.join(readiness['simm_regim']['missing_required_fields'])}\n"
        f"Regulatory capital calculation: {readiness['regulatory_capital_calculation']}\n"
        f"Guardrail: {readiness['guardrail']}"
    )
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
