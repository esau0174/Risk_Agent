from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.portfolio_loader import ExposureProfile
from src.core.tool_executor import ToolExecutor
from src.workflow.types import ExecutionTraceEntry, WorkflowPlan


def complete_step(plan: WorkflowPlan, step_name: str, output_summary: str) -> None:
    for step in plan.steps:
        if step.name == step_name:
            step.status = "completed"
            step.output_summary = output_summary
            return
    raise ValueError(f"Workflow step not found: {step_name}")


def execute_traced(
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


def data_file_input_summary(data_file: str) -> str:
    return f"Structured data file: {data_file}."


def loaded_data_output_summary(output) -> str:
    if isinstance(output, ExposureProfile):
        return f"Loaded {len(output.exposures)} exposure profile rows."
    return f"Loaded {len(output['tickers'])} tickers from file."


def config_input_summary(config_file: str | None) -> str:
    if config_file is not None:
        return f"Risk configuration file: {config_file}."
    return "Default risk configuration."


def validation_output_summary(output) -> str:
    return (
        f"Validation {'passed' if output.passed else 'failed'} with "
        f"{len(output.errors)} errors and {len(output.warnings)} warnings."
    )


def commentary_output_summary(output: str) -> str:
    return f"Generated commentary with {len(output)} characters."


def methodology_output_summary(output: list[dict]) -> str:
    return f"Retrieved {len(output)} methodology notes."
