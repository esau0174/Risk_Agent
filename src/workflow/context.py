"""Shared mutable state for approved-plan execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowExecutionContext:
    """Carry loaded inputs, analytics outputs, commentary, and trace state."""

    user_query: str
    scenario: str
    market_data_file: str | None = None
    credit_data_file: str | None = None
    config_file: str | None = None
    sensitivity_data_file: str | None = None
    use_llm: bool = False
    selected_route: str | None = None
    loaded_portfolio: dict | None = None
    exposure_profile: Any = None
    risk_config: Any = None
    risk_report: dict | None = None
    stress_test_results: list[dict] = field(default_factory=list)
    pfe_result: dict | None = None
    regulatory_readiness: dict | None = None
    sensitivity_records: Any = None
    sensitivity_result: dict | None = None
    methodology_notes: list[dict] = field(default_factory=list)
    market_methodology_notes: list[dict] = field(default_factory=list)
    credit_methodology_notes: list[dict] = field(default_factory=list)
    commentary: str | None = None
    market_commentary: str | None = None
    credit_commentary: str | None = None
    regulatory_commentary: str | None = None
    combined_commentary: str | None = None
    report_validation_result: Any = None
    market_validation_result: Any = None
    credit_validation_result: Any = None
    regulatory_validation_result: Any = None
    execution_trace: list[dict] = field(default_factory=list)
    execution_artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
