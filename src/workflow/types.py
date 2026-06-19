"""Workflow dataclasses shared by CLI, API, tests, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.report_validator import ValidationResult


@dataclass
class AgentRunResult:
    user_report: str
    execution_trace: list[dict]
    validation_result: dict | None
    raw_outputs: dict


@dataclass
class AgentWorkflowResult:
    """Structured result returned by the public autonomous workflow API."""

    query: str
    scenario: str
    detected_modules: list[str]
    proposed_plan: "WorkflowPlan"
    plan_validation_result: object
    approved_plan: "WorkflowPlan | None"
    user_report: str | None
    final_report_summary: str
    execution_trace: list[dict]
    validation_result: object | None
    raw_outputs: dict
    planner_mode: str = "rule"
    planner_message: str = "Rule-based planner with deterministic validation"
    planner_warnings: list[str] | None = None
    orchestration_trace: dict = field(default_factory=dict)


@dataclass
class WorkflowStep:
    """A planned tool step before or during workflow execution."""

    name: str
    description: str
    status: str
    tool_name: str
    output_summary: str | None = None


@dataclass
class WorkflowPlan:
    """Ordered plan proposed by a planner and checked by validators."""

    objective: str
    steps: list[WorkflowStep]


@dataclass
class ExecutionTraceEntry:
    """Runtime trace entry for deterministic workflow execution."""

    step_number: int
    tool_name: str
    status: str
    input_summary: str
    output_summary: str
    error: str | None


@dataclass
class WorkflowResult:
    """Domain workflow result used by the lower-level deterministic engine."""

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
