from __future__ import annotations

from dataclasses import replace

from src.tool_executor import ToolExecutor
from src.tool_registry import list_registered_tools
from src.workflow import WorkflowPlan, WorkflowResult, run_risk_workflow


def _fake_market_risk_report(
    tickers,
    weights,
    start_date,
    end_date=None,
    confidence_level=0.95,
    risk_config=None,
):
    return {
        "metadata": {
            "tickers": list(tickers),
            "weights": list(weights),
            "start_date": start_date,
            "end_date": end_date,
            "confidence_level": confidence_level,
        },
        "risk_metrics": {
            "annualized_volatility": 0.20,
            "historical_var": 0.02,
            "expected_shortfall": 0.03,
            "max_drawdown": 0.15,
        },
        "correlation_matrix": {},
        "latest_cumulative_return": 0.10,
        "number_of_observations": 10,
        "analysis_timestamp": "2026-01-01T00:00:00+00:00",
    }


def test_market_and_pfe_files_use_the_same_workflow_engine(tmp_path):
    market_path = tmp_path / "market_portfolio.csv"
    market_path.write_text(
        "ticker,weight\nSPY,60%\nQQQ,40%\n",
        encoding="utf-8",
    )
    exposure_path = tmp_path / "exposure_profile.csv"
    exposure_path.write_text(
        "netting_set,time_years,expected_exposure,pfe_95,pfe_99\n"
        "NS-001,0.0,100,150,180\n"
        "NS-001,1.0,140,220,280\n",
        encoding="utf-8",
    )
    tools = [
        replace(tool, handler=_fake_market_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]
    executor = ToolExecutor(tools)

    market_result = run_risk_workflow(
        "Analyze market downside and concentration risk.",
        portfolio_file=str(market_path),
        use_llm=False,
        tool_executor=executor,
    )
    pfe_result = run_risk_workflow(
        "Analyze counterparty PFE and netting-set exposure.",
        portfolio_file=str(exposure_path),
        use_llm=False,
        tool_executor=executor,
    )

    assert isinstance(market_result, WorkflowResult)
    assert isinstance(pfe_result, WorkflowResult)
    assert isinstance(market_result.plan, WorkflowPlan)
    assert isinstance(pfe_result.plan, WorkflowPlan)
    assert market_result.execution_trace
    assert pfe_result.execution_trace

    market_tools = [entry.tool_name for entry in market_result.execution_trace]
    pfe_tools = [entry.tool_name for entry in pfe_result.execution_trace]

    assert "calculate_risk_metrics" in market_tools
    assert "calculate_pfe_metrics" in pfe_tools
    assert "calculate_risk_metrics" not in pfe_tools
    assert "validate_report" in market_tools
    assert "validate_report" in pfe_tools
