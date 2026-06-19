"""Top-level autonomous workflow orchestration for RiskFlow Agent.

This module keeps planning, validation, execution, and presentation assembly
separate so an LLM can propose a workflow without bypassing deterministic risk
tools or validation gates.
"""

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
SENSITIVITY_DATA_FILE = "examples/sample_sensitivities.csv"
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
    """Run planning, deterministic execution, validation, and report assembly."""
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

    # LLM mode fails closed: no stale scenario defaults or partial plans are executed.
    if planning["failed"]:
        plan_validation_result = PlanValidationResult(
            passed=False,
            errors=[planning["message"]],
            warnings=planning["warnings"],
        )
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
            detected_modules=[],
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

    required_tools = _required_tools_for_request(
        effective_query,
        available_input_schemas,
        requested_modules,
    )
    missing_required_tools = _missing_required_tools(plan, required_tools)
    proposed_detected_modules = _detect_modules_from_plan(plan)
    detected_modules = (
        _detect_modules_from_required_tools(required_tools)
        if missing_required_tools
        else proposed_detected_modules
    )
    execution_route = _execution_route_from_modules(detected_modules)
    approved_plan = plan
    route_mapping_note_override = None

    # Completeness is a second gate after syntactic plan validation. It catches
    # under-scoped LLM plans, then maps them to a deterministic route when safe.
    if missing_required_tools and not plan_validation_result.errors:
        missing_text = ", ".join(missing_required_tools)
        completeness_warning = (
            "Plan incomplete; missing required tool(s): "
            f"{missing_text}. Mapped to deterministic {execution_route} route."
        )
        if planning["mode"] == "llm":
            completeness_warning = (
                "LLM "
                + completeness_warning[0].lower()
                + completeness_warning[1:]
            )
            approved_plan = propose_autonomous_workflow_plan(
                effective_query,
                available_input_schemas=available_input_schemas,
                requested_modules=detected_modules,
                registered_tool_names=[
                    tool.name for tool in list_registered_tools()
                ],
            )
            plan_validation_result = validate_workflow_plan(approved_plan)
            plan_validation_result.warnings.append(completeness_warning)
            route_mapping_note_override = completeness_warning
        else:
            plan_validation_result.errors.append(completeness_warning)
            plan_validation_result.passed = False

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

    executed = _execute_approved_plan_or_route(
        approved_plan,
        execution_route,
        effective_query,
        scenario,
        force_route_fallback=route_mapping_note_override is not None,
        route_mapping_note_override=route_mapping_note_override,
    )
    orchestration_trace = _build_orchestration_trace(
        proposed_plan=plan,
        approved_plan=approved_plan,
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
        approved_plan=approved_plan,
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
    """Select the requested planner and return a proposed WorkflowPlan."""
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
        # Auto mode remains demo-friendly by falling back to rule planning; explicit
        # llm mode surfaces the failure and prevents execution.
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
    force_route_fallback: bool = False,
    route_mapping_note_override: str | None = None,
) -> dict:
    """Prefer direct approved-plan execution; retain route fallback for control."""
    context = WorkflowExecutionContext(
        user_query=effective_query,
        scenario=scenario,
        market_data_file=MARKET_DATA_FILE,
        credit_data_file=CREDIT_DATA_FILE,
        sensitivity_data_file=SENSITIVITY_DATA_FILE,
        config_file=CONFIG_FILE,
        use_llm=False,
        selected_route=execution_route,
    )
    plan_executor = ApprovedPlanExecutor()

    try:
        if force_route_fallback:
            raise PlanExecutionNotSupported(
                "Approved plan intentionally mapped to deterministic route fallback."
            )
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
        # The fallback is intentionally conservative: known scenario routes run
        # deterministic workflows when a validated plan cannot be executed directly.
        executed = _execute_approved_route(execution_route)
        executed["execution_mode"] = "deterministic_route_fallback"
        executed["route_mapping_note"] = (
            route_mapping_note_override
            or "Approved plan mapped to deterministic route fallback."
        )
        executed["selected_route"] = execution_route
        executed["skipped_or_unsupported_tools"] = []
        return executed


def _outputs_from_plan_context(context: WorkflowExecutionContext) -> dict:
    """Convert execution context state into user report and raw output sections."""
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

    if context.sensitivity_result is not None:
        user_report_sections.append(_build_sensitivity_report(context.sensitivity_result))
        final_sections.append("Sensitivity Risk")
        raw_outputs["sensitivity_risk"] = context.sensitivity_result
        validation_results["sensitivity_risk"] = {"passed": True}
        validation_result = {"passed": True, "sensitivity_risk": {"passed": True}}

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


def _required_tools_for_request(
    query: str,
    available_input_schemas: list[str],
    requested_modules: list[str] | None,
) -> list[str]:
    """Infer the minimum tools needed to satisfy the requested risk scope."""
    normalized = query.lower()
    schemas = set(available_input_schemas)
    modules = {module.lower() for module in requested_modules or []}
    required: list[str] = []

    market_requested = (
        "market risk" in modules
        or "market_portfolio" in schemas
        or any(
            term in normalized
            for term in (
                "market risk",
                "portfolio risk",
                "portfolio",
                "var",
                "volatility",
                "drawdown",
                "downside",
            )
        )
    )
    stress_requested = any(
        term in normalized for term in ("stress", "shock", "scenario", "selloff")
    )
    counterparty_requested = (
        "credit risk" in modules
        or "counterparty risk" in modules
        or "exposure_profile" in schemas
        or any(
            term in normalized
            for term in ("counterparty", "credit risk", "pfe", "exposure profile")
        )
    )
    regulatory_requested = (
        "regulatory risk" in modules
        or any(
            term in normalized
            for term in ("regulatory", "readiness", "sa-ccr", "simm", "regim")
        )
    )
    sensitivity_requested = (
        "sensitivity risk" in modules
        or "sensitivity_file" in schemas
        or any(
            term in normalized
            for term in ("greek", "greeks", "sensitivity", "sensitivities")
        )
    )

    if market_requested or stress_requested:
        required.extend(
            ["load_portfolio_file", "validate_portfolio", "calculate_risk_metrics"]
        )
    if stress_requested:
        required.append("run_stress_test")
    if counterparty_requested:
        required.extend(["load_exposure_profile", "calculate_pfe_metrics"])
    if sensitivity_requested:
        required.extend(
            ["load_sensitivity_file", "validate_sensitivity_file", "aggregate_greeks"]
        )
    if regulatory_requested:
        required.append("assess_regulatory_readiness")

    return _dedupe(required)


def _missing_required_tools(plan: WorkflowPlan, required_tools: list[str]) -> list[str]:
    tool_names = {step.tool_name for step in plan.steps}
    return [tool_name for tool_name in required_tools if tool_name not in tool_names]


def _detect_modules_from_required_tools(required_tools: list[str]) -> list[str]:
    tools = set(required_tools)
    modules: list[str] = []
    if tools & {"calculate_risk_metrics", "run_stress_test"}:
        modules.append("Market Risk")
    if "calculate_pfe_metrics" in tools:
        modules.append("Credit Risk")
    if "assess_regulatory_readiness" in tools:
        modules.append("Regulatory Risk")
    if "aggregate_greeks" in tools:
        modules.append("Sensitivity Risk")
    return modules


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _default_input_schemas_for_query(query: str) -> list[str]:
    normalized = query.lower()
    schemas: list[str] = []
    if any(term in normalized for term in ("market", "portfolio", "var", "stress")):
        schemas.append("market_portfolio")
    if any(
        term in normalized
        for term in ("credit", "pfe", "exposure profile", "counterparty exposure")
    ):
        schemas.append("exposure_profile")
    if any(term in normalized for term in ("greek", "greeks", "sensitivity", "sensitivities")):
        schemas.append("sensitivity_file")
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
    if "aggregate_greeks" in tool_names:
        modules.append("Sensitivity Risk")
    return modules


def _execution_route_from_modules(modules: list[str]) -> str:
    selected = set(modules)
    if selected == {"Market Risk"}:
        return "market"
    if selected == {"Credit Risk"}:
        return "credit"
    if selected == {"Regulatory Risk"}:
        return "regulatory"
    if selected == {"Sensitivity Risk"}:
        return "sensitivity"
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
    dollar_metrics = result.risk_report.get("dollar_risk_metrics", {})
    lines = [
        "Market Risk",
        *_market_metadata_lines(result.risk_report.get("metadata", {})),
        f"- Annualized volatility: {metrics['annualized_volatility']:.2%}",
        f"- 95% historical VaR: {metrics['historical_var']:.2%}",
        f"- 95% Expected Shortfall: {metrics['expected_shortfall']:.2%}",
        f"- Maximum drawdown: {metrics['max_drawdown']:.2%}",
    ]
    lines.extend(_dollar_market_metric_lines(dollar_metrics))
    if result.stress_test_results:
        lines.extend(_stress_result_lines(result.stress_test_results[0]))
    lines.extend(
        [
            f"- Validation: {'PASSED' if result.validation_result.passed else 'FAILED'}",
            "",
            "Market Risk Commentary",
            result.llm_commentary,
        ]
    )
    return "\n".join(lines)


def _dollar_market_metric_lines(dollar_metrics: dict) -> list[str]:
    lines = []
    if dollar_metrics.get("dollar_historical_var") is not None:
        lines.append(
            f"- Dollar historical VaR: USD {dollar_metrics['dollar_historical_var']:,.2f}"
        )
    if dollar_metrics.get("dollar_expected_shortfall") is not None:
        lines.append(
            "- Dollar Expected Shortfall: "
            f"USD {dollar_metrics['dollar_expected_shortfall']:,.2f}"
        )
    if dollar_metrics.get("dollar_max_drawdown") is not None:
        lines.append(
            f"- Dollar maximum drawdown: USD {dollar_metrics['dollar_max_drawdown']:,.2f}"
        )
    return lines


def _stress_result_lines(stress_result: dict) -> list[str]:
    lines = [f"- Stress scenario loss: {stress_result['portfolio_loss_pct']:.2%}"]
    if stress_result.get("dollar_portfolio_loss") is not None:
        lines[-1] += f" / USD {stress_result['dollar_portfolio_loss']:,.2f}"
    if stress_result.get("stressed_portfolio_value_usd") is not None:
        lines.append(
            "- Stressed portfolio value: "
            f"USD {stress_result['stressed_portfolio_value_usd']:,.2f}"
        )
    return lines


def _market_metadata_lines(metadata: dict) -> list[str]:
    portfolio_metadata = metadata.get("portfolio_metadata") or {}
    if not portfolio_metadata:
        return []

    lines = []
    if portfolio_metadata.get("portfolio_id"):
        lines.append(f"- Portfolio ID: {portfolio_metadata['portfolio_id']}")
    if portfolio_metadata.get("book"):
        lines.append(f"- Book: {portfolio_metadata['book']}")
    if portfolio_metadata.get("asset_classes"):
        lines.append(
            "- Asset classes: " + ", ".join(portfolio_metadata["asset_classes"])
        )
    if portfolio_metadata.get("risk_buckets"):
        lines.append(
            "- Risk buckets: " + ", ".join(portfolio_metadata["risk_buckets"])
        )
    if portfolio_metadata.get("regions"):
        lines.append("- Regions: " + ", ".join(portfolio_metadata["regions"]))
    total_notional = portfolio_metadata.get("total_notional_usd")
    if total_notional is not None:
        lines.append(f"- Total notional: USD {total_notional:,.2f}")
    return lines


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


def _build_sensitivity_report(result: dict) -> str:
    warnings = result.get("warnings", [])
    lines = [
        "Sensitivity Risk",
        "- Source: precomputed sensitivities from an upstream pricing/risk engine",
        f"- Records: {result['record_count']}",
        f"- Portfolio IDs: {', '.join(result['portfolio_ids'])}",
        f"- Books: {', '.join(result['books'])}",
        f"- Currencies: {', '.join(result['currencies'])}",
        f"- Total delta: {result['total_delta']:,.2f}",
        f"- Total gamma: {result['total_gamma']:,.2f}",
        f"- Total vega: {result['total_vega']:,.2f}",
        f"- Total theta: {result['total_theta']:,.2f}",
        (
            "- Largest delta risk factor: "
            f"{result['largest_delta_risk_factor']['risk_factor']} "
            f"({result['largest_delta_risk_factor']['absolute_value']:,.2f})"
        ),
        (
            "- Largest vega risk factor: "
            f"{result['largest_vega_risk_factor']['risk_factor']} "
            f"({result['largest_vega_risk_factor']['absolute_value']:,.2f})"
        ),
        "- Validation: PASSED",
        "",
        "Sensitivity Risk Commentary",
        (
            "RiskFlow Agent aggregates and validates supplied Greeks only. "
            "Delta, gamma, vega, and theta are assumed to come from an upstream "
            "pricing or risk engine; this project does not calculate pricing-model "
            "Greeks."
        ),
    ]
    if warnings:
        lines.insert(7, "- Warnings: " + " ".join(warnings))
    return "\n".join(lines)


def _build_regulatory_report(readiness: dict, validation_result=None) -> str:
    sa_ccr = readiness["sa_ccr"]
    sa_ccr_available = sa_ccr.get("available_portfolio_metadata", [])
    sa_ccr_missing = sa_ccr.get(
        "missing_trade_level_inputs",
        sa_ccr.get("missing_required_fields", []),
    )
    simm_regim = readiness["simm_regim"]
    simm_available = simm_regim.get("available_inputs", [])
    simm_missing = simm_regim.get(
        "missing_inputs",
        simm_regim.get("missing_required_fields", []),
    )
    lines = [
        "Regulatory Risk",
        f"- SA-CCR readiness: {sa_ccr['status']}",
        f"- SIMM / RegIM readiness: {simm_regim['status']}",
        f"- Regulatory capital calculation: {readiness['regulatory_capital_calculation']}",
        "- SA-CCR available portfolio metadata: "
        f"{', '.join(sa_ccr_available) if sa_ccr_available else 'none'}",
        "- SA-CCR missing trade-level inputs: "
        f"{', '.join(sa_ccr_missing)}",
        f"- SA-CCR guardrail: {sa_ccr.get('guardrail_note', readiness['guardrail'])}",
        "- SIMM / RegIM available inputs: "
        f"{', '.join(simm_available) if simm_available else 'none'}",
        "- SIMM / RegIM missing inputs: "
        f"{', '.join(simm_missing)}",
        f"- SIMM / RegIM guardrail: {simm_regim.get('guardrail_note', readiness['guardrail'])}",
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
    """Build the high-level audit trace comparing proposed, approved, and run tools."""
    proposed_plan_steps = _plan_tool_names(proposed_plan)
    approved_plan_steps = _plan_tool_names(approved_plan)
    executed_tools = _clean_tool_names(
        [
            entry.get("tool_name")
            for entry in execution_trace
            if isinstance(entry, dict)
        ]
    )
    skipped_tools = (
        _clean_tool_names(skipped_or_unsupported_tools)
        if skipped_or_unsupported_tools is not None
        else _clean_tool_names(proposed_plan_steps) if approved_plan is None else []
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


def _clean_tool_names(tool_names) -> list[str]:
    return [
        str(tool_name)
        for tool_name in (tool_names or [])
        if tool_name not in (None, "") and str(tool_name).strip().lower() != "none"
    ]
