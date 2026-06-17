from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from src.workflow import (
    AgentWorkflowResult,
    AGENT_SCENARIOS,
    WorkflowPlan,
    WorkflowStep,
    propose_autonomous_workflow_plan,
    run_agent_workflow,
    validate_workflow_plan,
)
import src.workflow.agent as agent_module
import src.workflow.llm_planner as llm_planner


class _FakeResponse:
    def __init__(self, output_text: str):
        self.output_text = output_text


class _FakeResponses:
    def __init__(self, output_text: str):
        self._output_text = output_text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self._output_text)


class _FakeLLMClient:
    def __init__(self, output_text: str):
        self.responses = _FakeResponses(output_text)


class _RaisingResponses:
    def create(self, **kwargs):
        raise RuntimeError("network unavailable")


class _RaisingLLMClient:
    responses = _RaisingResponses()


def _llm_payload(modules, tools):
    import json

    return json.dumps(
        {
            "detected_modules": modules,
            "proposed_tools": [
                {"tool_name": tool_name, "reason": f"Need {tool_name}."}
                for tool_name in tools
            ],
            "rationale": "Mocked LLM plan.",
            "planner_notes": [],
        }
    )


def test_llm_planner_loads_env_model_and_base_url(monkeypatch):
    captured_client_kwargs = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured_client_kwargs.update(kwargs)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "test-planner-model")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    client = llm_planner._create_openai_client()
    fake_client = _FakeLLMClient(
        _llm_payload(["Regulatory Risk"], ["assess_regulatory_readiness"])
    )
    llm_planner.propose_llm_workflow_plan(
        "Check SA-CCR readiness.",
        scenario="regulatory",
        available_input_schemas=[],
        registered_tools=agent_module.list_registered_tools(),
        client=fake_client,
    )

    assert client is not None
    assert captured_client_kwargs == {
        "api_key": "test-key",
        "base_url": "https://example.test/v1",
    }
    assert fake_client.responses.last_kwargs["model"] == "test-planner-model"


def test_autonomous_planner_proposes_all_requested_risk_modules():
    plan = propose_autonomous_workflow_plan(
        "Run Market Risk, Credit Risk, and Regulatory Risk with stress testing.",
        available_input_schemas=["market_portfolio", "exposure_profile"],
        requested_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
    )

    tool_names = [step.tool_name for step in plan.steps]

    assert "calculate_risk_metrics" in tool_names
    assert "run_stress_test" in tool_names
    assert "calculate_pfe_metrics" in tool_names
    assert "assess_regulatory_readiness" in tool_names
    assert set(tool_names) <= {
        "load_portfolio_file",
        "load_exposure_profile",
        "load_sensitivity_file",
        "validate_sensitivity_file",
        "aggregate_greeks",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "run_stress_test",
        "calculate_pfe_metrics",
        "assess_regulatory_readiness",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    }


def test_autonomous_planner_routes_greeks_query_to_sensitivity_tools():
    plan = propose_autonomous_workflow_plan(
        "Review Greeks exposure and check sensitivity concentration.",
        available_input_schemas=["sensitivity_file"],
    )

    assert [step.tool_name for step in plan.steps] == [
        "load_sensitivity_file",
        "validate_sensitivity_file",
        "aggregate_greeks",
    ]


def test_run_agent_workflow_sensitivity_query_returns_sensitivity_report():
    result = run_agent_workflow(
        query="Review Greeks exposure and check sensitivity concentration.",
        scenario="full",
        planner_mode="rule",
    )

    assert result.detected_modules == ["Sensitivity Risk"]
    assert result.orchestration_trace["execution_mode"] == "approved_plan_executor"
    assert result.orchestration_trace["selected_route"] == "sensitivity"
    assert result.orchestration_trace["executed_tools"] == [
        "load_sensitivity_file",
        "validate_sensitivity_file",
        "aggregate_greeks",
    ]
    assert "Sensitivity Risk" in result.user_report
    assert "precomputed sensitivities" in result.user_report
    assert "does not calculate pricing-model Greeks" in result.user_report
    assert result.validation_result["passed"] is True
    assert "sensitivity_risk" in result.raw_outputs


def test_run_agent_workflow_market_and_greeks_query_routes_both_modules():
    result = run_agent_workflow(
        query="Run market risk and Greeks review.",
        scenario="full",
        planner_mode="rule",
    )

    assert result.detected_modules == ["Market Risk", "Sensitivity Risk"]
    assert result.orchestration_trace["execution_mode"] == "approved_plan_executor"
    assert "calculate_risk_metrics" in result.orchestration_trace["executed_tools"]
    assert "aggregate_greeks" in result.orchestration_trace["executed_tools"]
    assert "Market Risk" in result.user_report
    assert "Sensitivity Risk" in result.user_report


def test_run_agent_workflow_market_greeks_and_regulatory_uses_sensitivity_readiness():
    result = run_agent_workflow(
        query="Run market risk, Greeks, and regulatory readiness.",
        scenario="full",
        planner_mode="rule",
    )

    assert result.detected_modules == [
        "Market Risk",
        "Regulatory Risk",
        "Sensitivity Risk",
    ]
    executed_tools = result.orchestration_trace["executed_tools"]
    assert executed_tools.index("aggregate_greeks") < executed_tools.index(
        "assess_regulatory_readiness"
    )
    assert "Market Risk" in result.user_report
    assert "Sensitivity Risk" in result.user_report
    assert "Regulatory Risk" in result.user_report
    assert "SIMM / RegIM readiness: PARTIAL" in result.user_report
    assert "SIMM / RegIM available inputs:" in result.user_report
    assert "risk_class" in result.user_report
    assert "delta" in result.user_report
    assert "product_class" in result.user_report
    assert "No SIMM margin amount is generated" in result.user_report
    assert "SIMM margin amount: USD" not in result.user_report
    assert result.raw_outputs["regulatory_risk"]["simm_regim"]["status"] == "PARTIAL"
    assert result.validation_result["sensitivity_risk"]["passed"] is True


def test_validation_summary_includes_sensitivity_risk_for_combined_workflow():
    module = _load_demo_module()
    result = run_agent_workflow(
        query="Run market risk, Greeks, and regulatory readiness.",
        scenario="full",
        planner_mode="rule",
    )

    summary = module._validation_summary(result.validation_result)

    assert "- Market Risk: PASSED" in summary
    assert "- Regulatory Risk: PASSED" in summary
    assert "- Sensitivity Risk: PASSED" in summary


def test_plan_validator_accepts_valid_autonomous_plan():
    plan = propose_autonomous_workflow_plan(
        "Run Market Risk, Credit Risk, and Regulatory Risk with stress testing.",
        available_input_schemas=["market_portfolio", "exposure_profile"],
        requested_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is True
    assert result.errors == []


def test_plan_validator_rejects_unsupported_regulatory_capital_tool():
    plan = WorkflowPlan(
        objective="Invalid regulatory capital request.",
        steps=[
            WorkflowStep(
                name="calculate_sa_ccr_capital",
                description="Unsupported SA-CCR capital calculation.",
                status="proposed",
                tool_name="calculate_sa_ccr_capital",
            )
        ],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is False
    assert any("Unsupported regulatory capital" in error for error in result.errors)


def test_plan_validator_rejects_misordered_tools():
    plan = WorkflowPlan(
        objective="Invalid market order.",
        steps=[
            WorkflowStep(
                name="calculate_risk_metrics",
                description="Calculate risk before validation.",
                status="proposed",
                tool_name="calculate_risk_metrics",
            ),
            WorkflowStep(
                name="validate_portfolio",
                description="Validate portfolio too late.",
                status="proposed",
                tool_name="validate_portfolio",
            ),
            WorkflowStep(
                name="generate_commentary",
                description="Generate commentary.",
                status="proposed",
                tool_name="generate_commentary",
            ),
            WorkflowStep(
                name="validate_report",
                description="Validate report.",
                status="proposed",
                tool_name="validate_report",
            ),
        ],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is False
    assert "validate_portfolio must occur before calculate_risk_metrics." in (
        result.errors
    )


def test_plan_validator_requires_sensitivity_aggregation_before_regulatory_readiness():
    plan = WorkflowPlan(
        objective="Invalid sensitivity regulatory order.",
        steps=[
            WorkflowStep(
                name="assess_regulatory_readiness",
                description="Assess readiness too early.",
                status="proposed",
                tool_name="assess_regulatory_readiness",
            ),
            WorkflowStep(
                name="aggregate_greeks",
                description="Aggregate sensitivities too late.",
                status="proposed",
                tool_name="aggregate_greeks",
            ),
        ],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is False
    assert "aggregate_greeks must occur before assess_regulatory_readiness." in (
        result.errors
    )


def test_run_agent_workflow_full_scenario(monkeypatch):
    class FakeApprovedPlanExecutor:
        def can_execute(self, plan, context):
            return True

        def execute(self, plan, context):
            context.risk_report = {
                "risk_metrics": {
                    "annualized_volatility": 0.2671,
                    "historical_var": 0.0232,
                    "expected_shortfall": 0.0347,
                    "max_drawdown": 0.2377,
                }
            }
            context.stress_test_results = [{"portfolio_loss_pct": 0.225}]
            context.pfe_result = {
                "peak_pfe_95": 2_100_000.0,
                "peak_pfe_99": 2_600_000.0,
                "epe": 1_080_000.0,
                "largest_netting_set_by_peak_pfe": "NS-001",
                "configured_limit": 2_500_000.0,
                "limit_utilization": 0.84,
                "limit_status": "PASSED",
            }
            context.regulatory_readiness = {
                "overall_status": "WARNING",
                "missing_inputs": [
                    "trade_type",
                    "trade_notional",
                    "maturity",
                    "supervisory_category",
                    "netting_agreement_details",
                    "supervisory_factor_category_mapping",
                    "risk_class",
                    "margin_class",
                    "product_class",
                    "risk_weight_mapping",
                    "correlation_parameters",
                    "margin_currency",
                    "currency",
                ],
                "sa_ccr": {
                    "status": "WARNING",
                    "available_portfolio_metadata": [],
                    "missing_trade_level_inputs": [
                        "trade_type",
                        "trade_notional",
                        "maturity",
                        "supervisory_category",
                        "netting_agreement_details",
                        "supervisory_factor_category_mapping",
                    ],
                    "missing_required_fields": [
                        "trade_type",
                        "trade_notional",
                        "maturity",
                        "supervisory_category",
                        "netting_agreement_details",
                        "supervisory_factor_category_mapping",
                    ],
                    "guardrail_note": "Portfolio-level metadata is useful context.",
                },
                "simm_regim": {
                    "status": "WARNING",
                    "available_inputs": [],
                    "missing_inputs": [
                        "risk_class",
                        "risk_factor",
                        "bucket",
                        "delta",
                        "gamma",
                        "vega",
                        "theta",
                        "currency",
                        "product_class",
                        "margin_class",
                        "risk_weight_mapping",
                        "correlation_parameters",
                        "margin_currency",
                    ],
                    "missing_required_fields": [
                        "risk_class",
                        "risk_factor",
                        "bucket",
                        "delta",
                        "gamma",
                        "vega",
                        "theta",
                        "currency",
                        "product_class",
                        "margin_class",
                        "risk_weight_mapping",
                        "correlation_parameters",
                        "margin_currency",
                    ],
                    "guardrail_note": "No SIMM margin amount is generated.",
                },
                "regulatory_capital_calculation": "Not performed",
                "guardrail": "No regulatory capital or margin number was generated from insufficient inputs.",
            }
            context.market_commentary = (
                "Historical VaR and Expected Shortfall describe downside risk for "
                "SPY, QQQ, NVDA, and TLT. Stress Testing and Concentration Risk "
                "methodology references apply."
            )
            context.credit_commentary = (
                "Counterparty Exposure / PFE Analysis: Peak 95% PFE and EPE "
                "summarize the exposure profile and netting set limit utilization."
            )
            context.market_validation_result = SimpleNamespace(passed=True)
            context.credit_validation_result = SimpleNamespace(passed=True)
            context.report_validation_result = SimpleNamespace(passed=True)
            context.execution_trace = [
                {
                    "step_number": index,
                    "tool_name": step.tool_name,
                    "status": "success",
                    "input_summary": "fake input",
                    "output_summary": "fake output",
                    "error": None,
                }
                for index, step in enumerate(plan.steps, start=1)
            ]
            return context

    monkeypatch.setattr(
        agent_module,
        "ApprovedPlanExecutor",
        lambda: FakeApprovedPlanExecutor(),
    )

    result = run_agent_workflow(scenario="full", planner_mode="rule")

    assert isinstance(result, AgentWorkflowResult)
    assert result.scenario == "full"
    assert result.detected_modules == ["Market Risk", "Credit Risk", "Regulatory Risk"]
    assert result.plan_validation_result.passed is True
    assert result.approved_plan is not None
    assert "Market Risk" in result.user_report
    assert "Credit Risk" in result.user_report
    assert "Regulatory Risk" in result.user_report
    assert "RiskFlow Agent - Full Risk Workflow Demo" not in result.user_report
    assert result.execution_trace[0]["tool_name"] == "load_portfolio_file"
    assert "load_exposure_profile" in result.orchestration_trace["executed_tools"]
    assert result.validation_result["passed"] is True
    assert "market_risk" in result.raw_outputs
    assert result.orchestration_trace["execution_mode"] == "approved_plan_executor"
    market_section = result.user_report.split("Credit Risk", 1)[0]
    credit_section = result.user_report.split("Credit Risk", 1)[1]
    assert "Historical VaR" in market_section
    assert "Expected Shortfall" in market_section
    assert "Peak 95% PFE" not in market_section
    assert "Peak 95% PFE" in credit_section
    assert "EPE" in credit_section


def _market_result():
    return SimpleNamespace(
        risk_report={
            "risk_metrics": {
                "annualized_volatility": 0.2671,
                "historical_var": 0.0232,
                "expected_shortfall": 0.0347,
                "max_drawdown": 0.2377,
            }
        },
        stress_test_results=[{"portfolio_loss_pct": 0.225}],
        execution_trace=[
            SimpleNamespace(
                step_number=1,
                tool_name="calculate_risk_metrics",
                status="success",
                input_summary="Market inputs.",
                output_summary="Market metrics.",
                error=None,
            )
        ],
        validation_result=SimpleNamespace(passed=True),
        llm_commentary="Market risk commentary.",
    )


def _credit_result():
    return SimpleNamespace(
        pfe_result={
            "peak_pfe_95": 2_100_000.0,
            "peak_pfe_99": 2_600_000.0,
            "epe": 1_080_000.0,
            "largest_netting_set_by_peak_pfe": "NS-001",
            "configured_limit": 2_500_000.0,
            "limit_utilization": 0.84,
            "limit_status": "PASSED",
        },
        execution_trace=[
            SimpleNamespace(
                step_number=1,
                tool_name="calculate_pfe_metrics",
                status="success",
                input_summary="Credit inputs.",
                output_summary="PFE metrics.",
                error=None,
            )
        ],
        validation_result=SimpleNamespace(passed=True),
        llm_commentary="Credit risk commentary.",
    )


def test_run_agent_workflow_market_only_scenario(monkeypatch):
    result = run_agent_workflow(scenario="market", planner_mode="rule")

    assert result.detected_modules == ["Market Risk"]
    assert "Annualized volatility:" in result.user_report
    assert "95% historical VaR:" in result.user_report
    assert "Market Risk" in result.final_report_summary
    assert result.execution_trace[0]["tool_name"] == "load_portfolio_file"
    assert "calculate_risk_metrics" in [
        entry["tool_name"] for entry in result.execution_trace
    ]
    assert "market_risk" in result.raw_outputs
    assert result.orchestration_trace["proposed_plan_steps"]
    assert result.orchestration_trace["approved_plan_steps"]
    assert result.orchestration_trace["selected_route"] == "market"
    assert result.orchestration_trace["execution_mode"] == "approved_plan_executor"
    assert "calculate_risk_metrics" in result.orchestration_trace["executed_tools"]
    assert result.orchestration_trace["skipped_or_unsupported_tools"] == []
    assert result.orchestration_trace["validation_status"] == "PASSED"


def test_run_agent_workflow_credit_only_scenario(monkeypatch):
    result = run_agent_workflow(scenario="credit", planner_mode="rule")

    assert result.detected_modules == ["Credit Risk"]
    assert "Peak 95% PFE: USD 2,100,000.00" in result.user_report
    assert "Limit utilization: 84.00% of USD 2,500,000.00" in result.user_report
    assert "Credit Risk" in result.final_report_summary
    assert result.execution_trace[0]["tool_name"] == "load_exposure_profile"
    assert "calculate_pfe_metrics" in [
        entry["tool_name"] for entry in result.execution_trace
    ]
    assert "credit_risk" in result.raw_outputs


def test_run_agent_workflow_regulatory_only_scenario():
    result = run_agent_workflow(scenario="regulatory", planner_mode="rule")

    assert result.detected_modules == ["Regulatory Risk"]
    assert "Regulatory Risk" in result.final_report_summary
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"
    assert result.validation_result.passed is True
    assert "regulatory_risk" in result.raw_outputs


def test_run_agent_workflow_custom_regulatory_query_overrides_full_scenario():
    result = run_agent_workflow(
        query="Check SA-CCR and SIMM readiness only.",
        scenario="full",
        planner_mode="rule",
    )

    assert result.detected_modules == ["Regulatory Risk"]
    assert "Market Risk" not in result.detected_modules
    assert "Credit Risk" not in result.detected_modules
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"
    assert "SA-CCR readiness" in result.user_report


def test_run_agent_workflow_invalid_plan_does_not_execute(monkeypatch):
    def fail_if_executed(*args, **kwargs):
        raise AssertionError("Execution should not start for an invalid plan.")

    monkeypatch.setattr(agent_module, "run_full_risk_agent_workflow", fail_if_executed)
    monkeypatch.setattr(agent_module, "run_risk_workflow", fail_if_executed)
    invalid_plan = WorkflowPlan(
        objective="Invalid autonomous plan.",
        steps=[
            WorkflowStep(
                name="calculate_sa_ccr_capital",
                description="Unsupported capital calculation.",
                status="proposed",
                tool_name="calculate_sa_ccr_capital",
            )
        ],
    )

    result = run_agent_workflow(scenario="full", proposed_plan=invalid_plan)

    assert result.plan_validation_result.passed is False
    assert result.approved_plan is None
    assert result.execution_trace == []
    assert result.raw_outputs == {}
    assert result.final_report_summary == "Approved Plan: none; execution was not started."
    assert result.orchestration_trace["approved_plan_steps"] == []
    assert result.orchestration_trace["selected_route"] is None
    assert result.orchestration_trace["executed_tools"] == []
    assert result.orchestration_trace["skipped_or_unsupported_tools"] == [
        "calculate_sa_ccr_capital"
    ]
    assert result.orchestration_trace["validation_status"] == "FAILED"
    assert result.orchestration_trace["execution_mode"] == "not_executed"


def test_llm_planner_valid_market_plan(monkeypatch):
    monkeypatch.setattr(agent_module, "run_risk_workflow", lambda *args, **kwargs: _market_result())
    client = _FakeLLMClient(
        _llm_payload(
            ["Market Risk"],
            [
                "load_portfolio_file",
                "validate_portfolio",
                "load_risk_config",
                "calculate_risk_metrics",
                "retrieve_methodology",
                "generate_commentary",
                "validate_report",
            ],
        )
    )

    result = run_agent_workflow(scenario="market", planner_mode="llm", planner_client=client)

    assert result.planner_mode == "llm"
    assert result.planner_message == "LLM planner with deterministic validation"
    assert result.detected_modules == ["Market Risk"]
    assert result.plan_validation_result.passed is True
    assert "Annualized volatility" in result.user_report


def test_llm_planner_valid_credit_plan(monkeypatch):
    monkeypatch.setattr(agent_module, "run_risk_workflow", lambda *args, **kwargs: _credit_result())
    client = _FakeLLMClient(
        _llm_payload(
            ["Credit Risk"],
            [
                "load_portfolio_file",
                "load_risk_config",
                "calculate_pfe_metrics",
                "retrieve_methodology",
                "generate_commentary",
                "validate_report",
            ],
        )
    )

    result = run_agent_workflow(scenario="credit", planner_mode="llm", planner_client=client)

    assert result.planner_mode == "llm"
    assert result.detected_modules == ["Credit Risk"]
    assert result.plan_validation_result.passed is True
    assert "Peak 95% PFE" in result.user_report


def test_llm_planner_valid_regulatory_plan():
    client = _FakeLLMClient(
        _llm_payload(
            ["Regulatory Risk"],
            ["assess_regulatory_readiness"],
        )
    )

    result = run_agent_workflow(
        scenario="regulatory",
        planner_mode="llm",
        planner_client=client,
    )

    assert result.planner_mode == "llm"
    assert result.detected_modules == ["Regulatory Risk"]
    assert result.plan_validation_result.passed is True
    assert "SA-CCR readiness" in result.user_report


def test_llm_planner_accepts_markdown_fenced_json():
    client = _FakeLLMClient(
        "```json\n"
        + _llm_payload(
            ["Regulatory Risk"],
            ["assess_regulatory_readiness"],
        )
        + "\n```"
    )

    result = run_agent_workflow(
        scenario="regulatory",
        planner_mode="llm",
        planner_client=client,
    )

    assert result.plan_validation_result.passed is True
    assert result.detected_modules == ["Regulatory Risk"]
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"


def test_llm_planner_missing_required_fields_fails_safely():
    client = _FakeLLMClient('{"detected_modules":["Regulatory Risk"]}')

    result = run_agent_workflow(
        scenario="regulatory",
        planner_mode="llm",
        planner_client=client,
    )

    assert result.plan_validation_result.passed is False
    assert result.execution_trace == []
    assert "missing required field" in result.planner_message


def test_llm_planner_valid_full_plan(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "run_full_risk_agent_workflow",
        lambda *args, **kwargs: SimpleNamespace(
            user_report="Combined Executive Summary\nMarket Risk\nCredit Risk\nRegulatory Risk",
            execution_trace=[],
            validation_result={"passed": True},
            raw_outputs={},
        ),
    )
    client = _FakeLLMClient(
        _llm_payload(
            ["Market Risk", "Credit Risk", "Regulatory Risk"],
            [
                "load_portfolio_file",
                "validate_portfolio",
                "load_risk_config",
                "calculate_risk_metrics",
                "run_stress_test",
                "calculate_pfe_metrics",
                "assess_regulatory_readiness",
                "retrieve_methodology",
                "generate_commentary",
                "validate_report",
            ],
        )
    )

    result = run_agent_workflow(scenario="full", planner_mode="llm", planner_client=client)

    assert result.detected_modules == ["Market Risk", "Credit Risk", "Regulatory Risk"]
    assert result.plan_validation_result.passed is True
    assert "Combined Executive Summary" in result.user_report


def test_llm_planner_rejects_unsupported_regulatory_capital_tool():
    client = _FakeLLMClient(
        _llm_payload(
            ["Regulatory Risk"],
            ["assess_regulatory_readiness", "calculate_saccr_capital"],
        )
    )

    result = run_agent_workflow(scenario="regulatory", planner_mode="llm", planner_client=client)

    assert result.plan_validation_result.passed is False
    assert result.approved_plan is None
    assert result.execution_trace == []
    assert any(
        "Unsupported regulatory capital" in error
        for error in result.plan_validation_result.errors
    )


def test_llm_planner_rejects_unregistered_tool():
    client = _FakeLLMClient(
        _llm_payload(
            ["Market Risk"],
            ["load_portfolio_file", "calculate_magic_metric"],
        )
    )

    result = run_agent_workflow(scenario="market", planner_mode="llm", planner_client=client)

    assert result.plan_validation_result.passed is False
    assert result.execution_trace == []
    assert any("Unknown or unregistered tool" in error for error in result.plan_validation_result.errors)


def test_malformed_llm_response_fails_safely_in_llm_mode():
    result = run_agent_workflow(
        scenario="market",
        planner_mode="llm",
        planner_client=_FakeLLMClient("not-json"),
    )

    assert result.planner_mode == "llm"
    assert result.plan_validation_result.passed is False
    assert result.execution_trace == []
    assert "LLM planner failed before execution" in result.planner_message
    assert result.detected_modules == []


def test_llm_mode_failure_does_not_execute_tools(monkeypatch):
    def fail_if_executed(*args, **kwargs):
        raise AssertionError("Execution should not start after LLM planning failure.")

    monkeypatch.setattr(agent_module, "run_full_risk_agent_workflow", fail_if_executed)
    monkeypatch.setattr(agent_module, "run_risk_workflow", fail_if_executed)

    result = run_agent_workflow(
        scenario="full",
        planner_mode="llm",
        planner_client=_FakeLLMClient("not-json"),
    )

    assert result.plan_validation_result.passed is False
    assert result.approved_plan is None
    assert result.execution_trace == []


def test_llm_client_exception_fails_safely_without_execution(monkeypatch):
    def fail_if_executed(*args, **kwargs):
        raise AssertionError("Execution should not start after LLM client failure.")

    monkeypatch.setattr(agent_module, "run_full_risk_agent_workflow", fail_if_executed)
    monkeypatch.setattr(agent_module, "run_risk_workflow", fail_if_executed)

    result = run_agent_workflow(
        scenario="full",
        planner_mode="llm",
        planner_client=_RaisingLLMClient(),
    )

    assert result.plan_validation_result.passed is False
    assert result.approved_plan is None
    assert result.execution_trace == []
    assert result.detected_modules == []
    assert "LLM planner failed before execution" in result.planner_message


def test_auto_mode_falls_back_to_rule_planner_without_llm(monkeypatch):
    monkeypatch.setattr(agent_module, "is_llm_planner_available", lambda: False)
    monkeypatch.setattr(agent_module, "run_risk_workflow", lambda *args, **kwargs: _market_result())

    result = run_agent_workflow(scenario="market", planner_mode="auto")

    assert result.planner_mode == "rule"
    assert "Rule-based fallback planner" in result.planner_message
    assert result.planner_warnings == [
        "LLM planner unavailable; used rule-based fallback planner."
    ]


def test_auto_mode_malformed_llm_fallback_uses_query_for_regulatory_route():
    result = run_agent_workflow(
        query="Check SA-CCR and SIMM readiness only.",
        scenario="full",
        planner_mode="auto",
        planner_client=_FakeLLMClient("not-json"),
    )

    assert result.planner_mode == "rule"
    assert result.detected_modules == ["Regulatory Risk"]
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"
    assert result.planner_warnings
    assert result.planner_warnings[0].startswith(
        "LLM planner failed; used rule-based fallback planner. Reason:"
    )


def test_query_overrides_scenario_in_llm_planner_mode():
    client = _FakeLLMClient(
        _llm_payload(
            ["Regulatory Risk"],
            ["assess_regulatory_readiness"],
        )
    )

    result = run_agent_workflow(
        query="Check SA-CCR and SIMM readiness only.",
        scenario="full",
        planner_mode="llm",
        planner_client=client,
    )

    assert result.query == "Check SA-CCR and SIMM readiness only."
    assert result.detected_modules == ["Regulatory Risk"]
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"


def _load_demo_module():
    demo_path = Path("examples/run_riskflow_agent_demo.py")
    spec = importlib.util.spec_from_file_location("run_riskflow_agent_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_autonomous_demo_scenarios_detect_distinct_modules(monkeypatch, capsys):
    module = _load_demo_module()
    monkeypatch.setattr(module, "run_agent_workflow", _fake_run_agent_workflow)

    expected_modules = {
        "market": "Requested modules: Market Risk",
        "credit": "Requested modules: Credit Risk",
        "regulatory": "Requested modules: Regulatory Risk",
        "full": "Requested modules: Market Risk, Credit Risk, Regulatory Risk",
    }
    for scenario, expected_line in expected_modules.items():
        module.main(["--scenario", scenario])
        output = capsys.readouterr().out
        assert expected_line in output
        assert "Approved Tool Sequence" not in output
        assert "Risk Report" in output
        assert "Validation / Guardrail Summary" in output


def test_autonomous_demo_custom_query_and_show_plan(monkeypatch, capsys):
    module = _load_demo_module()
    monkeypatch.setattr(module, "run_agent_workflow", _fake_run_agent_workflow)

    module.main(
        [
            "--scenario",
            "market",
            "--query",
            "Custom market risk request",
            "--show-plan",
        ]
    )

    output = capsys.readouterr().out
    assert "User Request\nCustom market risk request" in output
    assert "Approved Tool Sequence" in output
    assert "calculate_risk_metrics" in output


def test_autonomous_demo_full_plan_displays_credit_exposure_loading(
    monkeypatch,
    capsys,
):
    module = _load_demo_module()
    monkeypatch.setattr(module, "run_agent_workflow", _fake_run_agent_workflow)

    module.main(["--scenario", "full", "--show-plan"])

    output = capsys.readouterr().out
    assert "load_exposure_profile - Load and validate a counterparty exposure profile" in output
    assert output.index("load_exposure_profile") < output.index("calculate_pfe_metrics")
    assert "- Approved tool count: 11" in output
    assert "Execution Trace" in output
    assert "- Execution mode:" in output
    assert "- Executed tools:" in output
    assert "- Skipped / unsupported tools:" in output
    assert "  - none" in output
    displayed_steps = [
        line for line in output.splitlines() if line[:1].isdigit() and ". " in line
    ]
    assert len(displayed_steps) == 11


def test_execution_trace_summary_keeps_executed_and_skipped_labels_on_separate_lines(
    capsys,
):
    module = _load_demo_module()

    module._print_execution_trace_summary(
        {
            "execution_mode": "approved_plan_executor",
            "selected_route": "full",
            "executed_tools": [
                "load_portfolio_file",
                "validate_portfolio",
                "calculate_risk_metrics",
                "validate_report",
            ],
            "skipped_or_unsupported_tools": [],
            "route_mapping_note": "Approved plan executed directly.",
        }
    )

    output = capsys.readouterr().out
    assert "validate_report\n- Skipped / unsupported tools:" in output
    assert "validate_report- Skipped / unsupported tools" not in output


def test_primary_demo_llm_failure_does_not_display_stale_market_context(
    monkeypatch,
    capsys,
):
    module = _load_demo_module()
    failed_plan = WorkflowPlan(
        objective="Failed LLM-planned RiskFlow Agent workflow.",
        steps=[],
    )
    failed_result = AgentWorkflowResult(
        query="Check SA-CCR and SIMM readiness only.",
        scenario="full",
        detected_modules=[],
        proposed_plan=failed_plan,
        plan_validation_result=SimpleNamespace(
            passed=False,
            errors=["LLM planner failed before execution: malformed JSON."],
            warnings=[],
        ),
        approved_plan=None,
        user_report=None,
        final_report_summary="Approved Plan: none; execution was not started.",
        execution_trace=[],
        validation_result=None,
        raw_outputs={},
        planner_mode="llm",
        planner_message="LLM planner failed before execution: malformed JSON.",
        planner_warnings=[],
    )
    monkeypatch.setattr(module, "run_agent_workflow", lambda **kwargs: failed_result)

    module.main(
        [
            "--planner",
            "llm",
            "--query",
            "Check SA-CCR and SIMM readiness only.",
            "--show-plan",
        ]
    )

    output = capsys.readouterr().out
    assert "Requested modules: unavailable because planning failed" in output
    assert "Available input schemas: unavailable because planning failed" in output
    assert "Plan validation: FAILED" in output
    assert "Approved Plan: none; execution was not started." in output
    assert "Requested modules: Market Risk" not in output
    assert "Available input schemas: market_portfolio" not in output


def _fake_run_agent_workflow(
    query=None,
    scenario="full",
    proposed_plan=None,
    planner_mode="auto",
    planner_client=None,
):
    scenario_config = AGENT_SCENARIOS[scenario]
    effective_query = query or scenario_config.query
    plan = proposed_plan or propose_autonomous_workflow_plan(
        effective_query,
        available_input_schemas=scenario_config.available_input_schemas,
        requested_modules=scenario_config.requested_modules,
    )
    validation_result = validate_workflow_plan(plan)
    return AgentWorkflowResult(
        query=effective_query,
        scenario=scenario,
        detected_modules=scenario_config.requested_modules,
        proposed_plan=plan,
        plan_validation_result=validation_result,
        approved_plan=plan if validation_result.passed else None,
        user_report=_fake_user_report(scenario),
        final_report_summary=f"- Final report sections: {scenario}",
        execution_trace=[{"step_number": 1, "tool_name": "fake_tool"}],
        validation_result={"passed": validation_result.passed},
        raw_outputs={},
    )


def _fake_user_report(scenario: str) -> str:
    if scenario == "market":
        return "Market Risk\n- Annualized volatility: 26.71%"
    if scenario == "credit":
        return "Credit Risk\n- Peak 95% PFE: USD 2,100,000.00"
    if scenario == "regulatory":
        return "Regulatory Risk\n- SA-CCR readiness: WARNING"
    return "Combined Executive Summary\nMarket Risk\nCredit Risk\nRegulatory Risk"
