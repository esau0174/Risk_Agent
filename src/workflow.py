from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.agent import (
    DEFAULT_START_DATE,
    _build_methodology_query,
)
from src.rag import load_methodology_docs
from src.report_validator import ValidationResult
from src.tool_executor import ToolExecutor, ToolResult
from src.tool_registry import get_tool


@dataclass
class WorkflowStep:
    name: str
    description: str
    status: str
    tool_name: str
    output_summary: str | None = None


@dataclass
class WorkflowPlan:
    objective: str
    steps: list[WorkflowStep]


@dataclass
class ExecutionTraceEntry:
    step_number: int
    tool_name: str
    status: str
    input_summary: str
    output_summary: str
    error: str | None


@dataclass
class WorkflowResult:
    query: str
    plan: WorkflowPlan
    execution_trace: list[ExecutionTraceEntry]
    parsed_portfolio: dict
    risk_report: dict
    methodology_notes: list[dict]
    llm_commentary: str
    validation_result: ValidationResult
    warnings: list[str]


def build_risk_workflow_plan(query: str) -> WorkflowPlan:
    """Build a deterministic, explicit plan for the risk analysis workflow."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string.")

    return WorkflowPlan(
        objective="Analyze portfolio risk from a natural-language query.",
        steps=[
            WorkflowStep(
                name="parse_portfolio",
                description=get_tool("parse_portfolio").description,
                status="pending",
                tool_name=get_tool("parse_portfolio").name,
            ),
            WorkflowStep(
                name="validate_portfolio",
                description=get_tool("validate_portfolio").description,
                status="pending",
                tool_name=get_tool("validate_portfolio").name,
            ),
            WorkflowStep(
                name="calculate_risk_metrics",
                description=get_tool("calculate_risk_metrics").description,
                status="pending",
                tool_name=get_tool("calculate_risk_metrics").name,
            ),
            WorkflowStep(
                name="retrieve_methodology",
                description=get_tool("retrieve_methodology").description,
                status="pending",
                tool_name=get_tool("retrieve_methodology").name,
            ),
            WorkflowStep(
                name="generate_commentary",
                description=get_tool("generate_commentary").description,
                status="pending",
                tool_name=get_tool("generate_commentary").name,
            ),
            WorkflowStep(
                name="validate_report",
                description=get_tool("validate_report").description,
                status="pending",
                tool_name=get_tool("validate_report").name,
            ),
        ],
    )


def run_risk_workflow(
    query: str,
    use_llm: bool = True,
    tool_executor: ToolExecutor | None = None,
) -> WorkflowResult:
    """Run the deterministic multi-step risk workflow."""
    plan = build_risk_workflow_plan(query)
    warnings: list[str] = []
    execution_trace: list[ExecutionTraceEntry] = []
    executor = tool_executor or ToolExecutor()

    parsed_portfolio = _execute_traced(
        executor,
        execution_trace,
        "parse_portfolio",
        "Natural-language portfolio query.",
        lambda output: (
            f"Parsed {len(output['tickers'])} holdings: {output['tickers']}."
        ),
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
        lambda output: (
            f"Validated {len(output)} weights with total {output.sum():.6f}."
        ),
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

    risk_report = _execute_traced(
        executor,
        execution_trace,
        "calculate_risk_metrics",
        (
            f"Portfolio with {len(tickers)} holdings from {DEFAULT_START_DATE}."
        ),
        lambda output: (
            "Calculated metrics: " + ", ".join(output["risk_metrics"].keys()) + "."
        ),
        tickers,
        weights,
        start_date=DEFAULT_START_DATE,
    )
    metric_names = ", ".join(risk_report["risk_metrics"].keys())
    _complete_step(
        plan,
        "calculate_risk_metrics",
        f"Calculated risk metrics: {metric_names}.",
    )

    docs = load_methodology_docs()
    methodology_query = _build_methodology_query(query, risk_report)
    methodology_notes = _execute_traced(
        executor,
        execution_trace,
        "retrieve_methodology",
        f"Methodology query across {len(docs)} local documents.",
        lambda output: (
            f"Retrieved {len(output)} notes: {[doc['title'] for doc in output]}."
        ),
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
        parsed_portfolio=parsed_portfolio,
        risk_report=risk_report,
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


def _require_tool_output(result: ToolResult):
    if result.status != "success":
        raise RuntimeError(f"Tool '{result.tool_name}' failed: {result.error}")

    return result.output


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
    return _require_tool_output(result)
