from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from src.agent import _build_methodology_query
from src.portfolio_loader import ExposureProfile
from src.rag import load_methodology_docs
from src.tool_executor import ToolExecutor
from src.tool_registry import get_tool
from src.workflow_types import (
    ExecutionTraceEntry,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStep,
)


PFE_METHODOLOGY_TITLES = {
    "Potential Future Exposure",
    "Expected Exposure and EPE",
    "Netting Set Exposure",
    "Counterparty Exposure Limitations",
}


class Intent(str, Enum):
    PORTFOLIO_RISK = "portfolio_risk"
    METHODOLOGY_EXPLANATION = "methodology_explanation"
    STRESS_TEST = "stress_test"
    REPORT_VALIDATION = "report_validation"


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
            objective="Analyze portfolio risk from a natural-language query.",
            steps=[
                _registered_step("parse_portfolio"),
                _registered_step("validate_portfolio"),
                _registered_step("load_risk_config"),
                _registered_step("calculate_risk_metrics"),
                _registered_step("retrieve_methodology"),
                _registered_step("generate_commentary"),
                _registered_step("validate_report"),
            ],
        )

    if intent is Intent.METHODOLOGY_EXPLANATION:
        return WorkflowPlan(
            objective="Explain financial risk methodology using local reference notes.",
            steps=[
                _registered_step("retrieve_methodology"),
                _registered_step("generate_commentary"),
            ],
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
        steps=[_registered_step("validate_report")],
    )


def run_risk_workflow(
    query: str,
    use_llm: bool = True,
    tool_executor: ToolExecutor | None = None,
    portfolio_file: str | None = None,
    config_file: str | None = None,
    data_file: str | None = None,
) -> WorkflowResult:
    """Run the deterministic multi-step risk workflow."""
    if data_file is not None and portfolio_file is not None:
        raise ValueError("Provide either data_file or portfolio_file, not both.")
    resolved_data_file = data_file if data_file is not None else portfolio_file

    plan = (
        _build_file_portfolio_workflow_plan()
        if resolved_data_file is not None
        else build_risk_workflow_plan(query)
    )
    warnings: list[str] = []
    execution_trace: list[ExecutionTraceEntry] = []
    executor = tool_executor or ToolExecutor()

    if resolved_data_file is not None:
        loaded_portfolio = _execute_traced(
            executor,
            execution_trace,
            "load_portfolio_file",
            f"Structured data file: {resolved_data_file}.",
            lambda output: (
                f"Loaded {len(output.exposures)} exposure profile rows."
                if isinstance(output, ExposureProfile)
                else f"Loaded {len(output['tickers'])} tickers from file."
            ),
            resolved_data_file,
        )
        if isinstance(loaded_portfolio, ExposureProfile):
            plan = _build_exposure_profile_workflow_plan()
            _complete_step(
                plan,
                "load_portfolio_file",
                f"Loaded {len(loaded_portfolio.exposures)} exposure profile rows.",
            )
            return _run_exposure_profile_workflow(
                query=query,
                exposure_profile=loaded_portfolio,
                config_file=config_file,
                use_llm=use_llm,
                executor=executor,
                plan=plan,
                execution_trace=execution_trace,
                warnings=warnings,
            )
        parsed_portfolio = loaded_portfolio
        _complete_step(
            plan,
            "load_portfolio_file",
            (
                f"Loaded tickers {parsed_portfolio['tickers']} with weights "
                f"{parsed_portfolio['weights']}."
            ),
        )
    else:
        parsed_portfolio = _execute_traced(
            executor,
            execution_trace,
            "parse_portfolio",
            "Natural-language portfolio query.",
            lambda output: f"Parsed {len(output['tickers'])} tickers.",
            query,
        )
        _complete_step(
            plan,
            "parse_portfolio",
            (
                f"Parsed tickers {parsed_portfolio['tickers']} with weights "
                f"{parsed_portfolio['weights']}."
            ),
        )

    tickers = parsed_portfolio["tickers"]
    validated_weights = _execute_traced(
        executor,
        execution_trace,
        "validate_portfolio",
        f"{len(tickers)} tickers and portfolio weights.",
        lambda output: f"Portfolio validation passed for {len(output)} weights.",
        tickers,
        parsed_portfolio["weights"],
    )
    weights = validated_weights.tolist()
    parsed_portfolio = {"tickers": tickers, "weights": weights}
    _complete_step(
        plan,
        "validate_portfolio",
        f"Validated {len(tickers)} holdings; weights sum to 1.0.",
    )

    risk_config = _execute_traced(
        executor,
        execution_trace,
        "load_risk_config",
        (
            f"Risk configuration file: {config_file}."
            if config_file is not None
            else "Default risk configuration."
        ),
        lambda output: (
            f"Loaded {output.var.method} VaR configuration at "
            f"{output.var.confidence_level:.0%} confidence."
        ),
        config_file,
    )
    _complete_step(
        plan,
        "load_risk_config",
        (
            f"Loaded {risk_config.returns.frequency} return assumptions with "
            f"annualization factor {risk_config.returns.annualization_factor}."
        ),
    )
    if risk_config.stress_scenarios:
        _insert_step_after(plan, "calculate_risk_metrics", "run_stress_test")

    risk_report = _execute_traced(
        executor,
        execution_trace,
        "calculate_risk_metrics",
        (
            f"Portfolio with {len(tickers)} holdings from "
            f"{risk_config.market_data.start_date}."
        ),
        lambda output: (
            "Calculated metrics: " + ", ".join(output["risk_metrics"].keys()) + "."
        ),
        tickers,
        weights,
        start_date=risk_config.market_data.start_date,
        risk_config=risk_config,
    )
    metric_names = ", ".join(risk_report["risk_metrics"].keys())
    _complete_step(
        plan,
        "calculate_risk_metrics",
        f"Calculated risk metrics: {metric_names}.",
    )

    stress_test_results = []
    if risk_config.stress_scenarios:
        stress_test_results = _execute_traced(
            executor,
            execution_trace,
            "run_stress_test",
            (
                f"Portfolio with {len(tickers)} holdings and "
                f"{len(risk_config.stress_scenarios)} configured stress scenarios."
            ),
            lambda output: f"Calculated {len(output)} stress scenario results.",
            tickers,
            weights,
            risk_config=risk_config,
        )
        _complete_step(
            plan,
            "run_stress_test",
            f"Calculated {len(stress_test_results)} deterministic stress scenarios.",
        )

    # TODO: Consider moving methodology loading behind a registered tool or provider.
    docs = load_methodology_docs()
    methodology_query = _build_methodology_query(query, risk_report)
    methodology_notes = _execute_traced(
        executor,
        execution_trace,
        "retrieve_methodology",
        f"Methodology query across {len(docs)} local documents.",
        lambda output: f"Retrieved {len(output)} methodology notes.",
        methodology_query,
        docs,
        top_k=4,
    )
    methodology_titles = [doc["title"] for doc in methodology_notes]
    _complete_step(
        plan,
        "retrieve_methodology",
        f"Retrieved methodology notes: {methodology_titles}.",
    )

    commentary = _execute_traced(
        executor,
        execution_trace,
        "generate_commentary",
        (
            f"Calculated risk report and {len(methodology_notes)} methodology notes; "
            f"LLM enabled: {use_llm}."
        ),
        lambda output: (
            f"Generated commentary with {len(output)} characters."
        ),
        query,
        risk_report,
        methodology_notes,
        use_llm=use_llm,
        **(
            {"stress_results": stress_test_results}
            if stress_test_results
            else {}
        ),
    )
    if use_llm:
        commentary_summary = "Generated LLM commentary from calculated facts and retrieved methodology."
    else:
        warnings.append("LLM commentary disabled; returned deterministic fallback commentary.")
        commentary_summary = "Generated deterministic fallback commentary without calling the LLM."

    _complete_step(plan, "generate_commentary", commentary_summary)

    validation_result = _execute_traced(
        executor,
        execution_trace,
        "validate_report",
        "Parsed portfolio, risk report, methodology notes, and commentary.",
        lambda output: (
            f"Validation {'passed' if output.passed else 'failed'} with "
            f"{len(output.errors)} errors and {len(output.warnings)} warnings."
        ),
        parsed_portfolio,
        risk_report,
        methodology_notes,
        commentary,
        **(
            {"stress_results": stress_test_results}
            if stress_test_results
            else {}
        ),
    )

    if not validation_result.passed:
        initial_errors = list(validation_result.errors)
        initial_warnings = list(validation_result.warnings)
        commentary = _execute_traced(
            executor,
            execution_trace,
            "regenerate_commentary_with_validation_errors",
            (
                f"Original commentary with {len(initial_errors)} validation errors and "
                f"{len(initial_warnings)} warnings."
            ),
            lambda output: (
                f"Regenerated commentary with {len(output)} characters."
            ),
            risk_report,
            commentary,
            initial_errors,
            initial_warnings,
            methodology_notes,
            use_llm=use_llm,
            **(
                {"stress_results": stress_test_results}
                if stress_test_results
                else {}
            ),
        )
        warnings.append(
            "Initial commentary failed validation; commentary was regenerated once."
        )
        validation_result = _execute_traced(
            executor,
            execution_trace,
            "validate_report",
            "Regenerated commentary and original analytical report inputs.",
            lambda output: (
                f"Validation {'passed' if output.passed else 'failed'} with "
                f"{len(output.errors)} errors and {len(output.warnings)} warnings."
            ),
            parsed_portfolio,
            risk_report,
            methodology_notes,
            commentary,
            **(
                {"stress_results": stress_test_results}
                if stress_test_results
                else {}
            ),
        )

    warnings.extend(validation_result.warnings)
    validation_status = "passed" if validation_result.passed else "failed"
    _complete_step(
        plan,
        "validate_report",
        (
            f"Report validation {validation_status}; "
            f"{len(validation_result.errors)} errors and "
            f"{len(validation_result.warnings)} warnings."
        ),
    )

    return WorkflowResult(
        query=query,
        plan=plan,
        execution_trace=execution_trace,
        active_modules=infer_active_modules(execution_trace),
        parsed_portfolio=parsed_portfolio,
        risk_report=risk_report,
        pfe_result=None,
        stress_test_results=stress_test_results,
        methodology_notes=methodology_notes,
        llm_commentary=commentary,
        validation_result=validation_result,
        warnings=warnings,
    )


def _complete_step(plan: WorkflowPlan, step_name: str, output_summary: str) -> None:
    for step in plan.steps:
        if step.name == step_name:
            step.status = "completed"
            step.output_summary = output_summary
            return

    raise ValueError(f"Workflow step not found: {step_name}")


def infer_active_modules(
    execution_trace: list[ExecutionTraceEntry],
) -> list[str]:
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


def _registered_step(tool_name: str) -> WorkflowStep:
    tool = get_tool(tool_name)
    return WorkflowStep(
        name=tool.name,
        description=tool.description,
        status="pending",
        tool_name=tool.name,
    )


def _insert_step_after(
    plan: WorkflowPlan,
    preceding_step_name: str,
    tool_name: str,
) -> None:
    if any(step.name == tool_name for step in plan.steps):
        return
    for index, step in enumerate(plan.steps):
        if step.name == preceding_step_name:
            plan.steps.insert(index + 1, _registered_step(tool_name))
            return
    raise ValueError(f"Workflow step not found: {preceding_step_name}")


def _build_file_portfolio_workflow_plan() -> WorkflowPlan:
    return WorkflowPlan(
        objective="Analyze risk for a structured data file using a natural-language instruction.",
        steps=[
            _registered_step("load_portfolio_file"),
            _registered_step("validate_portfolio"),
            _registered_step("load_risk_config"),
            _registered_step("calculate_risk_metrics"),
            _registered_step("retrieve_methodology"),
            _registered_step("generate_commentary"),
            _registered_step("validate_report"),
        ],
    )


def _build_exposure_profile_workflow_plan() -> WorkflowPlan:
    return WorkflowPlan(
        objective="Analyze counterparty exposure profile and PFE metrics.",
        steps=[
            _registered_step("load_portfolio_file"),
            _registered_step("load_risk_config"),
            _registered_step("calculate_pfe_metrics"),
            _registered_step("retrieve_methodology"),
            _registered_step("generate_commentary"),
            _registered_step("validate_report"),
        ],
    )


def _run_exposure_profile_workflow(
    query: str,
    exposure_profile: ExposureProfile,
    config_file: str | None,
    use_llm: bool,
    executor: ToolExecutor,
    plan: WorkflowPlan,
    execution_trace: list[ExecutionTraceEntry],
    warnings: list[str],
) -> WorkflowResult:
    risk_config = _execute_traced(
        executor,
        execution_trace,
        "load_risk_config",
        (
            f"Risk configuration file: {config_file}."
            if config_file is not None
            else "Default risk configuration."
        ),
        lambda output: "Loaded risk configuration for exposure analysis.",
        config_file,
    )
    _complete_step(
        plan,
        "load_risk_config",
        f"Loaded reporting configuration; VaR confidence is {risk_config.var.confidence_level:.0%}.",
    )

    pfe_result = _execute_traced(
        executor,
        execution_trace,
        "calculate_pfe_metrics",
        f"Exposure profile with {len(exposure_profile.exposures)} rows.",
        lambda output: (
            f"Calculated peak 95% PFE {output['peak_pfe_95']:.2f} and EPE "
            f"{output['epe']:.2f}."
        ),
        exposure_profile,
    )
    _complete_step(
        plan,
        "calculate_pfe_metrics",
        (
            f"Calculated peak 95% PFE, EPE, and netting-set exposure metrics; "
            f"largest set is {pfe_result['largest_netting_set_by_peak_pfe']}."
        ),
    )

    docs = [
        doc
        for doc in load_methodology_docs()
        if doc["title"] in PFE_METHODOLOGY_TITLES
    ]
    methodology_query = (
        f"{query} potential future exposure PFE exposure profile expected exposure "
        "expected positive exposure EPE netting set netting agreement counterparty "
        "exposure limitations Monte Carlo pricing engine"
    )
    methodology_notes = _execute_traced(
        executor,
        execution_trace,
        "retrieve_methodology",
        f"Counterparty methodology query across {len(docs)} local documents.",
        lambda output: f"Retrieved {len(output)} methodology notes.",
        methodology_query,
        docs,
        top_k=4,
    )
    _complete_step(
        plan,
        "retrieve_methodology",
        f"Retrieved methodology notes: {[doc['title'] for doc in methodology_notes]}.",
    )

    commentary = _execute_traced(
        executor,
        execution_trace,
        "generate_commentary",
        f"PFE result and {len(methodology_notes)} methodology notes; LLM enabled: {use_llm}.",
        lambda output: f"Generated commentary with {len(output)} characters.",
        query,
        None,
        methodology_notes,
        use_llm=use_llm,
        pfe_result=pfe_result,
    )
    if use_llm:
        commentary_summary = "Generated LLM commentary from calculated PFE metrics."
    else:
        warnings.append("LLM commentary disabled; returned deterministic fallback commentary.")
        commentary_summary = "Generated deterministic PFE commentary without calling the LLM."
    _complete_step(plan, "generate_commentary", commentary_summary)

    validation_result = _execute_traced(
        executor,
        execution_trace,
        "validate_report",
        "PFE metrics, methodology notes, and counterparty commentary.",
        lambda output: (
            f"Validation {'passed' if output.passed else 'failed'} with "
            f"{len(output.errors)} errors and {len(output.warnings)} warnings."
        ),
        None,
        None,
        methodology_notes,
        commentary,
        pfe_result=pfe_result,
    )

    if not validation_result.passed:
        commentary = _execute_traced(
            executor,
            execution_trace,
            "regenerate_commentary_with_validation_errors",
            f"PFE commentary with {len(validation_result.errors)} validation errors.",
            lambda output: f"Regenerated commentary with {len(output)} characters.",
            None,
            commentary,
            list(validation_result.errors),
            list(validation_result.warnings),
            methodology_notes,
            use_llm=use_llm,
            pfe_result=pfe_result,
        )
        warnings.append("Initial commentary failed validation; commentary was regenerated once.")
        validation_result = _execute_traced(
            executor,
            execution_trace,
            "validate_report",
            "Regenerated PFE commentary and original analytical inputs.",
            lambda output: (
                f"Validation {'passed' if output.passed else 'failed'} with "
                f"{len(output.errors)} errors and {len(output.warnings)} warnings."
            ),
            None,
            None,
            methodology_notes,
            commentary,
            pfe_result=pfe_result,
        )

    warnings.extend(validation_result.warnings)
    _complete_step(
        plan,
        "validate_report",
        (
            f"Report validation {'passed' if validation_result.passed else 'failed'}; "
            f"{len(validation_result.errors)} errors and "
            f"{len(validation_result.warnings)} warnings."
        ),
    )

    return WorkflowResult(
        query=query,
        plan=plan,
        execution_trace=execution_trace,
        active_modules=infer_active_modules(execution_trace),
        parsed_portfolio=None,
        risk_report=None,
        pfe_result=pfe_result,
        stress_test_results=[],
        methodology_notes=methodology_notes,
        llm_commentary=commentary,
        validation_result=validation_result,
        warnings=warnings,
    )


def _execute_traced(
    executor: ToolExecutor,
    execution_trace: list[ExecutionTraceEntry],
    tool_name: str,
    input_summary: str,
    output_summary_builder: Callable[[Any], str],
    *args,
    **kwargs,
):
    result = executor.execute(tool_name, *args, **kwargs)
    output_summary = (
        output_summary_builder(result.output)
        if result.status == "success"
        else "Tool execution produced no output."
    )
    execution_trace.append(
        ExecutionTraceEntry(
            step_number=len(execution_trace) + 1,
            tool_name=tool_name,
            status=result.status,
            input_summary=input_summary,
            output_summary=output_summary,
            error=result.error,
        )
    )
    if result.status != "success":
        error = RuntimeError(f"Tool '{result.tool_name}' failed: {result.error}")
        error.execution_trace = list(execution_trace)
        raise error

    return result.output
