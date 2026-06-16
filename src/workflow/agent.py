from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from src.core.tool_executor import ToolExecutor
from src.core.tool_registry import list_registered_tools
from src.validators.regulatory import validate_regulatory_readiness_report
from src.workflow.autonomous_planner import propose_autonomous_workflow_plan
from src.workflow.context import WorkflowExecutionContext
from src.workflow.engine import run_risk_workflow
from src.workflow.llm_planner import (
    is_llm_planner_available,
    propose_llm_workflow_plan,
)
from src.workflow.plan_executor import ApprovedPlanExecutor, PlanExecutionNotSupported
from src.workflow.plan_validator import PlanValidationResult, validate_workflow_plan
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
    planner_mode: str = "auto",
    planner_client=None,
) -> AgentWorkflowResult:
    """Run the policy-constrained autonomous planning workflow."""
    if scenario not in AGENT_SCENARIOS:
        supported = ", ".join(sorted(AGENT_SCENARIOS))
        raise ValueError(f"Unknown scenario '{scenario}'. Supported scenarios: {supported}.")
    if planner_mode not in {"auto", "llm", "rule"}:
        raise ValueError("planner_mode must be one of: auto, llm, rule.")

    scenario_config = AGENT_SCENARIOS[scenario]
    custom_query = query is not None
    effective_query = query or scenario_config.query
    requested_modules = None if custom_query else scenario_config.requested_modules
    available_input_schemas = (
        _default_input_schemas_for_query(effective_query)
        if custom_query
        else scenario_config.available_input_schemas
    )
    planning = _build_plan(
        effective_query,
        scenario,
        available_input_schemas,
        requested_modules,
        proposed_plan,
        planner_mode,
        planner_client,
    )
    plan = planning["plan"]
    plan_validation_result = validate_workflow_plan(plan)
    detected_modules = _detect_modules_from_plan(plan)
    execution_route = _execution_route_from_modules(detected_modules)

    if planning["failed"]:
        plan_validation_result = PlanValidationResult(
            passed=False,
            errors=[planning["message"]],
            warnings=planning["warnings"],
        )

    if not plan_validation_result.passed:
        orchestration_trace = _build_orchestration_trace(
            proposed_plan=plan,
            approved_plan=None,
            selected_route=None,
            execution_trace=[],
            validation_status="FAILED",
            execution_mode="not_executed",
            route_mapping_note="Plan validation failed; execution was not started.",
        )
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
            planner_mode=planning["mode"],
            planner_message=planning["message"],
            planner_warnings=planning["warnings"],
            orchestration_trace=orchestration_trace,
        )

    executed = _execute_approved_plan_or_route(plan, execution_route, effective_query, scenario)
    orchestration_trace = _build_orchestration_trace(
        proposed_plan=plan,
        approved_plan=plan,
        selected_route=executed["selected_route"],
        execution_trace=executed["execution_trace"],
        validation_status="PASSED",
        execution_mode=executed["execution_mode"],
        route_mapping_note=executed["route_mapping_note"],
        skipped_or_unsupported_tools=executed["skipped_or_unsupported_tools"],
    )
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
        planner_mode=planning["mode"],
        planner_message=planning["message"],
        planner_warnings=planning["warnings"],
        orchestration_trace=orchestration_trace,
    )


def _build_plan(
    effective_query: str,
    scenario: str,
    available_input_schemas: list[str],
    requested_modules: list[str] | None,
    proposed_plan: WorkflowPlan | None,
    planner_mode: str,
    planner_client,
) -> dict:
    if proposed_plan is not None:
        return {
            "plan": proposed_plan,
            "mode": "provided",
            "message": "Externally supplied plan with deterministic validation",
            "warnings": [],
            "failed": False,
        }

    registered_tools = list_registered_tools()
    registered_tool_names = [tool.name for tool in registered_tools]

    if planner_mode == "rule":
        return _rule_planning_result(
            effective_query,
            available_input_schemas,
            requested_modules,
            registered_tool_names,
            [],
        )

    if planner_mode == "auto" and planner_client is None and not is_llm_planner_available():
        return _rule_planning_result(
            effective_query,
            available_input_schemas,
            requested_modules,
            registered_tool_names,
            ["LLM planner unavailable; used rule-based fallback planner."],
        )

    try:
        proposal = propose_llm_workflow_plan(
            effective_query,
            scenario=scenario,
            available_input_schemas=available_input_schemas,
            registered_tools=registered_tools,
            client=planner_client,
        )
    except Exception as exc:
        if planner_mode == "auto":
            return _rule_planning_result(
                effective_query,
                available_input_schemas,
                requested_modules,
                registered_tool_names,
                [f"LLM planner failed; used rule-based fallback planner. Reason: {exc}"],
            )
        return {
            "plan": WorkflowPlan(
                objective="Failed LLM-planned RiskFlow Agent workflow.",
                steps=[],
            ),
            "mode": "llm",
            "message": f"LLM planner failed before execution: {exc}",
            "warnings": [],
            "failed": True,
        }

    return {
        "plan": proposal.plan,
        "mode": "llm",
        "message": "LLM planner with deterministic validation",
        "warnings": proposal.planner_notes,
        "failed": False,
    }


def _rule_planning_result(
    effective_query: str,
    available_input_schemas: list[str],
    requested_modules: list[str] | None,
    registered_tool_names: list[str],
    warnings: list[str],
) -> dict:
    return {
        "plan": propose_autonomous_workflow_plan(
            effective_query,
            available_input_schemas=available_input_schemas,
            requested_modules=requested_modules,
            registered_tool_names=registered_tool_names,
        ),
        "mode": "rule",
        "message": "Rule-based fallback planner with deterministic validation",
        "warnings": warnings,
        "failed": False,
    }


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
    initial_report = _build_regulatory_report(readiness)
    validation_result = validate_regulatory_readiness_report(initial_report, readiness)
    report = _build_regulatory_report(readiness, validation_result=validation_result)
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


def _execute_approved_plan_or_route(
    plan: WorkflowPlan,
    execution_route: str,
    effective_query: str,
    scenario: str,
) -> dict:
    context = WorkflowExecutionContext(
        user_query=effective_query,
        scenario=scenario,
        market_data_file=MARKET_DATA_FILE,
        credit_data_file=CREDIT_DATA_FILE,
        config_file=CONFIG_FILE,
        use_llm=False,
        selected_route=execution_route,
    )
    plan_executor = ApprovedPlanExecutor()

    try:
        if not plan_executor.can_execute(plan, context):
            raise PlanExecutionNotSupported(
                "Approved plan contains steps that are not mapped for direct execution."
            )
        context = plan_executor.execute(plan, context)
        executed = _outputs_from_plan_context(context)
        executed["execution_mode"] = "approved_plan_executor"
        executed["route_mapping_note"] = (
            "Approved plan executed sequentially through the lightweight "
            "ApprovedPlanExecutor."
        )
        executed["selected_route"] = execution_route
        executed["skipped_or_unsupported_tools"] = []
        return executed
    except PlanExecutionNotSupported:
        executed = _execute_approved_route(execution_route)
        executed["execution_mode"] = "deterministic_route_fallback"
        executed["route_mapping_note"] = (
            "Approved plan mapped to deterministic route fallback."
        )
        executed["selected_route"] = execution_route
        executed["skipped_or_unsupported_tools"] = []
        return executed


def _outputs_from_plan_context(context: WorkflowExecutionContext) -> dict:
    raw_outputs: dict = {}
    user_report_sections: list[str] = []
    final_sections: list[str] = []
    validation_result = None
    validation_results: dict[str, dict] = {}

    if context.risk_report is not None:
        market_result = SimpleNamespace(
            risk_report=context.risk_report,
            stress_test_results=context.stress_test_results,
            validation_result=(
                context.market_validation_result
                or context.report_validation_result
            ),
            llm_commentary=context.market_commentary or context.commentary or "",
        )
        user_report_sections.append(_build_market_report(market_result))
        final_sections.append("Market Risk")
        validation_result = context.market_validation_result or context.report_validation_result
        validation_results["market_risk"] = _validation_result_as_dict(
            context.market_validation_result or context.report_validation_result
        )
        raw_outputs["market_risk"] = {
            "risk_report": context.risk_report,
            "stress_test_results": context.stress_test_results,
        }

    if context.pfe_result is not None:
        credit_result = SimpleNamespace(
            pfe_result=context.pfe_result,
            validation_result=(
                context.credit_validation_result
                or context.report_validation_result
            ),
            llm_commentary=context.credit_commentary or context.commentary or "",
        )
        user_report_sections.append(_build_credit_report(credit_result))
        final_sections.append("Credit Risk")
        validation_result = context.credit_validation_result or context.report_validation_result
        validation_results["credit_risk"] = _validation_result_as_dict(
            context.credit_validation_result or context.report_validation_result
        )
        raw_outputs["credit_risk"] = context.pfe_result

    if context.regulatory_readiness is not None:
        initial_regulatory_report = _build_regulatory_report(context.regulatory_readiness)
        regulatory_validation = validate_regulatory_readiness_report(
            initial_regulatory_report,
            context.regulatory_readiness,
        )
        regulatory_report = _build_regulatory_report(
            context.regulatory_readiness,
            validation_result=regulatory_validation,
        )
        regulatory_validation = validate_regulatory_readiness_report(
            regulatory_report,
            context.regulatory_readiness,
        )
        context.regulatory_validation_result = regulatory_validation
        user_report_sections.append(regulatory_report)
        final_sections.append("Regulatory Risk")
        validation_result = regulatory_validation
        validation_results["regulatory_risk"] = _validation_result_as_dict(
            regulatory_validation
        )
        raw_outputs["regulatory_risk"] = context.regulatory_readiness

    if not user_report_sections:
        user_report_sections.append("No executable risk report section was produced.")

    if len(validation_results) > 1:
        validation_result = {
            "passed": all(result["passed"] for result in validation_results.values()),
            **validation_results,
        }

    validation_passed = _validation_passed(validation_result)
    return {
        "user_report": "\n\n".join(user_report_sections),
        "final_report_summary": (
            f"- Validation: {'PASSED' if validation_passed else 'FAILED'}\n"
            f"- Final report sections: {', '.join(final_sections) if final_sections else 'none'}"
        ),
        "execution_trace": context.execution_trace,
        "validation_result": validation_result,
        "raw_outputs": raw_outputs,
    }


def _validation_passed(validation_result) -> bool:
    if validation_result is None:
        return False
    if isinstance(validation_result, dict):
        return bool(validation_result.get("passed"))
    return bool(getattr(validation_result, "passed", False))


def _validation_result_as_dict(validation_result) -> dict:
    if validation_result is None:
        return {"passed": False}
    if isinstance(validation_result, dict):
        return {"passed": bool(validation_result.get("passed"))}
    return {"passed": bool(getattr(validation_result, "passed", False))}


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
    return modules


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


def _build_regulatory_report(readiness: dict, validation_result=None) -> str:
    lines = [
        "Regulatory Risk",
        f"- SA-CCR readiness: {readiness['sa_ccr']['status']}",
        f"- SIMM / RegIM readiness: {readiness['simm_regim']['status']}",
        f"- Regulatory capital calculation: {readiness['regulatory_capital_calculation']}",
        "- SA-CCR missing inputs: "
        f"{', '.join(readiness['sa_ccr']['missing_required_fields'])}",
        "- SIMM / RegIM missing inputs: "
        f"{', '.join(readiness['simm_regim']['missing_required_fields'])}",
        f"- Guardrail: {readiness['guardrail']}",
    ]
    if validation_result is not None:
        status = "PASSED" if validation_result.passed else "FAILED"
        lines.append(f"- Validation: {status}")
    return "\n".join(lines)


def _limit_utilization_line(pfe_metrics: dict) -> str:
    if pfe_metrics.get("limit_utilization") is None:
        return "- Limit utilization: not available; no configured limit"
    return (
        f"- Limit utilization: {pfe_metrics['limit_utilization']:.2%} of "
        f"USD {pfe_metrics['configured_limit']:,.2f}"
    )


def _build_orchestration_trace(
    proposed_plan: WorkflowPlan,
    approved_plan: WorkflowPlan | None,
    selected_route: str | None,
    execution_trace: list[dict],
    validation_status: str,
    execution_mode: str,
    route_mapping_note: str,
    skipped_or_unsupported_tools: list[str] | None = None,
) -> dict:
    proposed_plan_steps = _plan_tool_names(proposed_plan)
    approved_plan_steps = _plan_tool_names(approved_plan)
    executed_tools = [
        entry.get("tool_name")
        for entry in execution_trace
        if isinstance(entry, dict) and entry.get("tool_name")
    ]
    skipped_tools = (
        skipped_or_unsupported_tools
        if skipped_or_unsupported_tools is not None
        else proposed_plan_steps if approved_plan is None else []
    )
    return {
        "execution_mode": execution_mode,
        "proposed_plan_steps": proposed_plan_steps,
        "approved_plan_steps": approved_plan_steps,
        "selected_route": selected_route,
        "executed_tools": executed_tools,
        "skipped_or_unsupported_tools": skipped_tools,
        "validation_status": validation_status,
        "route_mapping_note": route_mapping_note,
    }


def _plan_tool_names(plan: WorkflowPlan | None) -> list[str]:
    if plan is None:
        return []
    return [step.tool_name for step in plan.steps]
