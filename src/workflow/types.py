from __future__ import annotations

from dataclasses import dataclass

from src.report_validator import ValidationResult


@dataclass
class AgentRunResult:
    user_report: str
    execution_trace: list[dict]
    validation_result: dict | None
    raw_outputs: dict


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
    active_modules: list[str]
    parsed_portfolio: dict | None
    risk_report: dict | None
    pfe_result: dict | None
    stress_test_results: list[dict]
    methodology_notes: list[dict]
    llm_commentary: str
    validation_result: ValidationResult
    warnings: list[str]
