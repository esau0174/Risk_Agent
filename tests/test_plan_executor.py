from __future__ import annotations

from types import SimpleNamespace

from src.core.tool_executor import ToolResult
from src.core.risk_config import RiskConfig
from src.workflow.context import WorkflowExecutionContext
from src.workflow.plan_executor import ApprovedPlanExecutor
from src.workflow.types import WorkflowPlan, WorkflowStep


class FakeToolExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, tool_name, *args, **kwargs):
        self.calls.append(tool_name)
        output = {
            "load_portfolio_file": {"tickers": ["SPY", "QQQ"], "weights": [0.6, 0.4]},
            "validate_portfolio": [0.6, 0.4],
            "load_risk_config": RiskConfig(),
            "calculate_risk_metrics": {
                "metadata": {"tickers": ["SPY", "QQQ"]},
                "risk_metrics": {
                    "annualized_volatility": 0.20,
                    "historical_var": 0.02,
                    "expected_shortfall": 0.03,
                    "max_drawdown": 0.10,
                }
            },
            "retrieve_methodology": [],
            "generate_commentary": "Market commentary.",
            "validate_report": SimpleNamespace(passed=True, errors=[], warnings=[]),
            "assess_regulatory_readiness": {
                "overall_status": "WARNING",
                "missing_inputs": ["trade_type"],
                "sa_ccr": {
                    "status": "WARNING",
                    "missing_required_fields": ["trade_type"],
                },
                "simm_regim": {
                    "status": "WARNING",
                    "missing_required_fields": ["risk_factor_sensitivities"],
                },
                "regulatory_capital_calculation": "Not performed",
                "guardrail": "No regulatory capital number was generated from insufficient inputs",
            },
        }[tool_name]
        return ToolResult(tool_name=tool_name, status="success", output=output)


def test_approved_plan_executor_runs_market_tools_sequentially():
    plan = _plan(
        [
            "load_portfolio_file",
            "validate_portfolio",
            "load_risk_config",
            "calculate_risk_metrics",
            "retrieve_methodology",
            "generate_commentary",
            "validate_report",
        ]
    )
    context = WorkflowExecutionContext(
        user_query="Run Market Risk.",
        scenario="market",
        selected_route="market",
        market_data_file="examples/sample_portfolio.csv",
        use_llm=False,
    )
    executor = ApprovedPlanExecutor(tool_executor=FakeToolExecutor())

    result = executor.execute(plan, context)

    assert [entry["tool_name"] for entry in result.execution_trace] == [
        "load_portfolio_file",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert result.risk_report is not None
    assert result.report_validation_result.passed is True


def test_approved_plan_executor_runs_regulatory_tool_directly():
    plan = _plan(["assess_regulatory_readiness"])
    context = WorkflowExecutionContext(
        user_query="Check SA-CCR readiness.",
        scenario="regulatory",
        selected_route="regulatory",
    )
    executor = ApprovedPlanExecutor(tool_executor=FakeToolExecutor())

    result = executor.execute(plan, context)

    assert result.regulatory_readiness["overall_status"] == "WARNING"
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"
    assert result.execution_trace[0]["status"] == "success"


def test_approved_plan_executor_rejects_unsupported_direct_execution():
    plan = _plan(["parse_portfolio"])
    context = WorkflowExecutionContext(
        user_query="40% SPY, 60% QQQ",
        scenario="market",
        selected_route="market",
    )

    assert ApprovedPlanExecutor(tool_executor=FakeToolExecutor()).can_execute(plan, context) is False


def _plan(tool_names: list[str]) -> WorkflowPlan:
    return WorkflowPlan(
        objective="Test plan.",
        steps=[
            WorkflowStep(
                name=tool_name,
                description=f"Run {tool_name}.",
                status="approved",
                tool_name=tool_name,
            )
            for tool_name in tool_names
        ],
    )
