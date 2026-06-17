from __future__ import annotations

from src.core.tool_executor import ToolExecutor
from src.data.portfolio_loader import ExposureProfile
from src.knowledge.rag import load_methodology_docs
from src.reporting.agent import _build_methodology_query
from src.workflow.execution import (
    commentary_output_summary,
    complete_step,
    config_input_summary,
    data_file_input_summary,
    execute_traced,
    loaded_data_output_summary,
    methodology_output_summary,
    validation_output_summary,
)
from src.workflow.planner import (
    build_exposure_profile_workflow_plan,
    build_file_portfolio_workflow_plan,
    build_risk_workflow_plan,
    detect_data_route,
    infer_active_modules,
    insert_step_after,
    resolve_data_file,
)
from src.workflow.types import (
    ExecutionTraceEntry,
    WorkflowPlan,
    WorkflowResult,
)


PFE_METHODOLOGY_TITLES = {
    "Potential Future Exposure",
    "Expected Exposure and EPE",
    "Netting Set Exposure",
    "Counterparty Exposure Limitations",
}


def run_risk_workflow(
    query: str,
    use_llm: bool = True,
    tool_executor: ToolExecutor | None = None,
    portfolio_file: str | None = None,
    config_file: str | None = None,
    data_file: str | None = None,
) -> WorkflowResult:
    """Run the deterministic multi-step risk workflow."""
    resolved_data_file = resolve_data_file(data_file, portfolio_file)

    plan = (
        build_file_portfolio_workflow_plan()
        if resolved_data_file is not None
        else build_risk_workflow_plan(query)
    )
    warnings: list[str] = []
    execution_trace: list[ExecutionTraceEntry] = []
    executor = tool_executor or ToolExecutor()

    if resolved_data_file is not None:
        loaded_portfolio = execute_traced(
            executor,
            execution_trace,
            "load_portfolio_file",
            data_file_input_summary(resolved_data_file),
            loaded_data_output_summary,
            resolved_data_file,
        )
        if detect_data_route(loaded_portfolio) == "credit_risk":
            execution_trace[-1].tool_name = "load_exposure_profile"
            plan = build_exposure_profile_workflow_plan()
            complete_step(
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
        complete_step(
            plan,
            "load_portfolio_file",
            (
                f"Loaded tickers {parsed_portfolio['tickers']} with weights "
                f"{parsed_portfolio['weights']}."
            ),
        )
    else:
        parsed_portfolio = execute_traced(
            executor,
            execution_trace,
            "parse_portfolio",
            "Natural-language portfolio query.",
            lambda output: f"Parsed {len(output['tickers'])} tickers.",
            query,
        )
        complete_step(
            plan,
            "parse_portfolio",
            (
                f"Parsed tickers {parsed_portfolio['tickers']} with weights "
                f"{parsed_portfolio['weights']}."
            ),
        )

    tickers = parsed_portfolio["tickers"]
    portfolio_metadata = parsed_portfolio.get("metadata")
    validated_weights = execute_traced(
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
    if portfolio_metadata:
        parsed_portfolio["metadata"] = portfolio_metadata
    complete_step(
        plan,
        "validate_portfolio",
        f"Validated {len(tickers)} holdings; weights sum to 1.0.",
    )

    risk_config = execute_traced(
        executor,
        execution_trace,
        "load_risk_config",
        config_input_summary(config_file),
        lambda output: (
            f"Loaded {output.var.method} VaR configuration at "
            f"{output.var.confidence_level:.0%} confidence."
        ),
        config_file,
    )
    complete_step(
        plan,
        "load_risk_config",
        (
            f"Loaded {risk_config.returns.frequency} return assumptions with "
            f"annualization factor {risk_config.returns.annualization_factor}."
        ),
    )
    if risk_config.stress_scenarios:
        insert_step_after(plan, "calculate_risk_metrics", "run_stress_test")

    risk_report_kwargs = {}
    if portfolio_metadata:
        risk_report_kwargs["portfolio_metadata"] = portfolio_metadata

    risk_report = execute_traced(
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
        end_date=risk_config.market_data.end_date,
        risk_config=risk_config,
        **risk_report_kwargs,
    )
    metric_names = ", ".join(risk_report["risk_metrics"].keys())
    complete_step(
        plan,
        "calculate_risk_metrics",
        f"Calculated risk metrics: {metric_names}.",
    )

    stress_test_results = []
    if risk_config.stress_scenarios:
        stress_kwargs = {}
        if portfolio_metadata and portfolio_metadata.get("total_notional_usd") is not None:
            stress_kwargs["portfolio_notional_usd"] = portfolio_metadata[
                "total_notional_usd"
            ]
        stress_test_results = execute_traced(
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
            **stress_kwargs,
        )
        complete_step(
            plan,
            "run_stress_test",
            f"Calculated {len(stress_test_results)} deterministic stress scenarios.",
        )

    # TODO: Consider moving methodology loading behind a registered tool or provider.
    docs = load_methodology_docs()
    methodology_query = _build_methodology_query(query, risk_report)
    methodology_notes = execute_traced(
        executor,
        execution_trace,
        "retrieve_methodology",
        f"Methodology query across {len(docs)} local documents.",
        methodology_output_summary,
        methodology_query,
        docs,
        top_k=4,
    )
    methodology_titles = [doc["title"] for doc in methodology_notes]
    complete_step(
        plan,
        "retrieve_methodology",
        f"Retrieved methodology notes: {methodology_titles}.",
    )

    commentary = execute_traced(
        executor,
        execution_trace,
        "generate_commentary",
        (
            f"Calculated risk report and {len(methodology_notes)} methodology notes; "
            f"LLM enabled: {use_llm}."
        ),
        commentary_output_summary,
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

    complete_step(plan, "generate_commentary", commentary_summary)

    validation_result = execute_traced(
        executor,
        execution_trace,
        "validate_report",
        "Parsed portfolio, risk report, methodology notes, and commentary.",
        validation_output_summary,
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
        commentary = execute_traced(
            executor,
            execution_trace,
            "regenerate_commentary_with_validation_errors",
            (
                f"Original commentary with {len(initial_errors)} validation errors and "
                f"{len(initial_warnings)} warnings."
            ),
            commentary_output_summary,
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
        validation_result = execute_traced(
            executor,
            execution_trace,
            "validate_report",
            "Regenerated commentary and original analytical report inputs.",
            validation_output_summary,
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
    complete_step(
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
    risk_config = execute_traced(
        executor,
        execution_trace,
        "load_risk_config",
        config_input_summary(config_file),
        lambda output: "Loaded risk configuration for exposure analysis.",
        config_file,
    )
    complete_step(
        plan,
        "load_risk_config",
        "Loaded reporting configuration for exposure analysis.",
    )

    pfe_result = execute_traced(
        executor,
        execution_trace,
        "calculate_pfe_metrics",
        f"Exposure profile with {len(exposure_profile.exposures)} rows.",
        lambda output: (
            f"Calculated peak 95% PFE {output['peak_pfe_95']:.2f} and EPE "
            f"{output['epe']:.2f}."
        ),
        exposure_profile,
        credit_limits=risk_config.credit_limits,
    )
    complete_step(
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
    methodology_notes = execute_traced(
        executor,
        execution_trace,
        "retrieve_methodology",
        f"Counterparty methodology query across {len(docs)} local documents.",
        methodology_output_summary,
        methodology_query,
        docs,
        top_k=4,
    )
    complete_step(
        plan,
        "retrieve_methodology",
        f"Retrieved methodology notes: {[doc['title'] for doc in methodology_notes]}.",
    )

    commentary = execute_traced(
        executor,
        execution_trace,
        "generate_commentary",
        f"PFE result and {len(methodology_notes)} methodology notes; LLM enabled: {use_llm}.",
        commentary_output_summary,
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
    complete_step(plan, "generate_commentary", commentary_summary)

    validation_result = execute_traced(
        executor,
        execution_trace,
        "validate_report",
        "PFE metrics, methodology notes, and counterparty commentary.",
        validation_output_summary,
        None,
        None,
        methodology_notes,
        commentary,
        pfe_result=pfe_result,
    )

    if not validation_result.passed:
        commentary = execute_traced(
            executor,
            execution_trace,
            "regenerate_commentary_with_validation_errors",
            f"PFE commentary with {len(validation_result.errors)} validation errors.",
            commentary_output_summary,
            None,
            commentary,
            list(validation_result.errors),
            list(validation_result.warnings),
            methodology_notes,
            use_llm=use_llm,
            pfe_result=pfe_result,
        )
        warnings.append("Initial commentary failed validation; commentary was regenerated once.")
        validation_result = execute_traced(
            executor,
            execution_trace,
            "validate_report",
            "Regenerated PFE commentary and original analytical inputs.",
            validation_output_summary,
            None,
            None,
            methodology_notes,
            commentary,
            pfe_result=pfe_result,
        )

    warnings.extend(validation_result.warnings)
    complete_step(
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
