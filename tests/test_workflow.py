from __future__ import annotations

import json
from dataclasses import replace

import pytest

from src.report_validator import ValidationResult
from src.tool_executor import ToolExecutor
from src.tool_registry import list_registered_tools
from src.workflow import WorkflowResult, build_risk_workflow_plan, run_risk_workflow


def _fake_generate_portfolio_risk_report(
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
        "correlation_matrix": {
            "SPY": {"SPY": 1.0, "QQQ": 0.8},
            "QQQ": {"SPY": 0.8, "QQQ": 1.0},
        },
        "latest_cumulative_return": 0.25,
        "number_of_observations": 10,
        "analysis_timestamp": "2026-01-01T00:00:00+00:00",
    }


def test_build_risk_workflow_plan_returns_expected_steps():
    plan = build_risk_workflow_plan("40% SPY, 60% QQQ")

    assert plan.objective == "Analyze portfolio risk from a natural-language query."
    assert [step.name for step in plan.steps] == [
        "parse_portfolio",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert [step.tool_name for step in plan.steps] == [
        "parse_portfolio",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert all(step.status == "pending" for step in plan.steps)


def test_run_risk_workflow_without_llm_returns_completed_result():
    tools = [
        replace(tool, handler=_fake_generate_portfolio_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]
    executor = ToolExecutor(tools)

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=executor,
    )

    assert isinstance(result, WorkflowResult)
    assert result.active_modules == ["shared", "market_risk"]
    assert all(step.status == "completed" for step in result.plan.steps)
    assert all(step.output_summary for step in result.plan.steps)
    assert result.parsed_portfolio == {
        "tickers": ["SPY", "QQQ"],
        "weights": [0.4, 0.6],
    }
    assert result.risk_report["risk_metrics"]["historical_var"] == 0.02
    assert result.pfe_result is None
    assert result.methodology_notes
    market_methodology_titles = {note["title"] for note in result.methodology_notes}
    assert {"Historical VaR", "Expected Shortfall", "Concentration Risk"}.issubset(
        market_methodology_titles
    )
    assert "Potential Future Exposure" not in market_methodology_titles
    assert "Expected Exposure and EPE" not in market_methodology_titles
    assert "does not constitute investment advice" in result.llm_commentary
    assert result.validation_result.passed is True
    validation_check_names = {
        check.name for check in result.validation_result.checks
    }
    assert "pfe_result_consistency" not in validation_check_names
    assert "stress_result_consistency" not in validation_check_names
    assert "commentary_metric_consistency" in validation_check_names
    assert any(step.name == "validate_report" for step in result.plan.steps)
    assert [entry.tool_name for entry in result.execution_trace] == [
        "parse_portfolio",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert [entry.step_number for entry in result.execution_trace] == [1, 2, 3, 4, 5, 6, 7]
    assert all(entry.status == "success" for entry in result.execution_trace)
    assert all(entry.input_summary for entry in result.execution_trace)
    assert all(entry.output_summary for entry in result.execution_trace)
    assert all(entry.error is None for entry in result.execution_trace)
    assert not any(
        entry.tool_name == "regenerate_commentary_with_validation_errors"
        for entry in result.execution_trace
    )
    assert result.warnings == [
        "LLM commentary disabled; returned deterministic fallback commentary."
    ]


def test_failed_tool_execution_is_recorded_before_workflow_raises():
    def failing_parser(query):
        raise ValueError("unable to parse portfolio")

    tools = [
        replace(tool, handler=failing_parser)
        if tool.name == "parse_portfolio"
        else tool
        for tool in list_registered_tools()
    ]
    executor = ToolExecutor(tools)

    with pytest.raises(RuntimeError, match="parse_portfolio") as exc_info:
        run_risk_workflow(
            "invalid portfolio query",
            use_llm=False,
            tool_executor=executor,
        )

    trace = exc_info.value.execution_trace
    assert len(trace) == 1
    assert trace[0].step_number == 1
    assert trace[0].tool_name == "parse_portfolio"
    assert trace[0].status == "failed"
    assert trace[0].input_summary == "Natural-language portfolio query."
    assert trace[0].output_summary == "Tool execution produced no output."
    assert trace[0].error == "ValueError: unable to parse portfolio"


def test_run_risk_workflow_uses_portfolio_file_and_skips_parser(tmp_path):
    portfolio_path = tmp_path / "portfolio.csv"
    portfolio_path.write_text("ticker,weight\nSPY,60%\nQQQ,40%\n", encoding="utf-8")

    def parser_must_not_run(query):
        raise AssertionError("parse_portfolio should be skipped for file input")

    replacements = {
        "parse_portfolio": parser_must_not_run,
        "calculate_risk_metrics": _fake_generate_portfolio_risk_report,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "Analyze the uploaded portfolio for downside risk.",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
        portfolio_file=str(portfolio_path),
    )

    assert [step.name for step in result.plan.steps] == [
        "load_portfolio_file",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert result.execution_trace[0].tool_name == "load_portfolio_file"
    assert not any(
        entry.tool_name == "parse_portfolio" for entry in result.execution_trace
    )
    assert result.parsed_portfolio == {
        "tickers": ["SPY", "QQQ"],
        "weights": [0.6, 0.4],
    }
    assert result.execution_trace[0].input_summary.startswith("Structured data file:")


def test_run_risk_workflow_accepts_preferred_data_file_name(tmp_path):
    portfolio_path = tmp_path / "portfolio.csv"
    portfolio_path.write_text("ticker,weight\nSPY,60%\nQQQ,40%\n", encoding="utf-8")
    tools = [
        replace(tool, handler=_fake_generate_portfolio_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "Analyze market risk.",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
        data_file=str(portfolio_path),
    )

    assert result.parsed_portfolio == {
        "tickers": ["SPY", "QQQ"],
        "weights": [0.6, 0.4],
    }
    assert result.execution_trace[0].tool_name == "load_portfolio_file"
    assert result.execution_trace[0].input_summary.startswith("Structured data file:")


def test_run_risk_workflow_rejects_both_file_parameter_names():
    with pytest.raises(
        ValueError,
        match="Provide either data_file or portfolio_file, not both",
    ):
        run_risk_workflow(
            "Analyze risk.",
            data_file="data.csv",
            portfolio_file="legacy.csv",
            use_llm=False,
        )


def test_natural_language_workflow_still_uses_parser():
    tools = [
        replace(tool, handler=_fake_generate_portfolio_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    assert result.plan.steps[0].name == "parse_portfolio"
    assert result.execution_trace[0].tool_name == "parse_portfolio"


def test_exposure_profile_workflow_uses_pfe_tools_and_skips_market_tools(tmp_path):
    exposure_path = tmp_path / "exposure_profile.csv"
    exposure_path.write_text(
        "netting_set,time_years,expected_exposure,pfe_95,pfe_99\n"
        "NS-001,0.0,100,150,180\n"
        "NS-001,1.0,140,220,280\n"
        "NS-002,2.0,120,200,260\n",
        encoding="utf-8",
    )

    def market_tool_must_not_run(*args, **kwargs):
        raise AssertionError("Market risk tool should be skipped for exposure profiles")

    replacements = {
        "validate_portfolio": market_tool_must_not_run,
        "calculate_risk_metrics": market_tool_must_not_run,
        "run_stress_test": market_tool_must_not_run,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "Analyze the counterparty exposure profile.",
        portfolio_file=str(exposure_path),
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    expected_tools = [
        "load_portfolio_file",
        "load_risk_config",
        "calculate_pfe_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert [step.name for step in result.plan.steps] == expected_tools
    assert [entry.tool_name for entry in result.execution_trace] == expected_tools
    assert all(step.status == "completed" for step in result.plan.steps)
    assert result.parsed_portfolio is None
    assert result.risk_report is None
    assert result.stress_test_results == []
    assert result.pfe_result["peak_pfe_95"] == 220.0
    assert result.pfe_result["peak_pfe_99"] == 280.0
    assert result.pfe_result["epe"] == pytest.approx(120.0)
    assert result.pfe_result["largest_netting_set_by_peak_pfe"] == "NS-001"
    assert result.active_modules == ["shared", "credit_risk"]
    methodology_titles = [note["title"] for note in result.methodology_notes]
    assert set(methodology_titles) == {
        "Potential Future Exposure",
        "Expected Exposure and EPE",
        "Netting Set Exposure",
        "Counterparty Exposure Limitations",
    }
    assert "Historical VaR" not in methodology_titles
    assert "Expected Shortfall" not in methodology_titles
    assert "Counterparty Exposure / PFE Analysis" in result.llm_commentary
    for title in methodology_titles:
        assert title in result.llm_commentary
    assert "not generated by a full Monte Carlo pricing engine" in result.llm_commentary
    assert result.validation_result.passed is True
    pfe_validation_check_names = {
        check.name for check in result.validation_result.checks
    }
    assert "pfe_result_consistency" in pfe_validation_check_names
    assert "stress_result_consistency" not in pfe_validation_check_names
    assert "commentary_metric_consistency" not in pfe_validation_check_names


def test_run_risk_workflow_loads_config_file_through_executor(tmp_path):
    config_path = tmp_path / "risk_config.json"
    config_path.write_text(
        json.dumps(
            {
                "market_data": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30",
                },
                "returns": {
                    "frequency": "daily",
                    "annualization_factor": 250,
                },
                "var": {
                    "confidence_level": 0.99,
                    "method": "historical",
                },
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def capture_configured_report(*args, **kwargs):
        captured["start_date"] = kwargs["start_date"]
        captured["risk_config"] = kwargs["risk_config"]
        return _fake_generate_portfolio_risk_report(*args, **kwargs)

    tools = [
        replace(tool, handler=capture_configured_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
        config_file=str(config_path),
    )

    assert "load_risk_config" in [
        entry.tool_name for entry in result.execution_trace
    ]
    assert captured["start_date"] == "2024-01-01"
    assert captured["risk_config"].market_data.end_date == "2024-06-30"
    assert captured["risk_config"].returns.annualization_factor == 250
    assert captured["risk_config"].var.confidence_level == 0.99


def test_workflow_runs_configured_stress_scenarios(tmp_path):
    config_path = tmp_path / "risk_config.json"
    config_path.write_text(
        json.dumps(
            {
                "stress_scenarios": [
                    {
                        "name": "Combined selloff",
                        "equity_selloff_pct": 0.10,
                        "tech_selloff_pct": 0.20,
                        "rates_shock_bps": 100,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    tools = [
        replace(tool, handler=_fake_generate_portfolio_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 30% QQQ, 20% NVDA, 10% TLT",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
        config_file=str(config_path),
    )

    plan_names = [step.name for step in result.plan.steps]
    trace_names = [entry.tool_name for entry in result.execution_trace]
    assert plan_names.index("run_stress_test") == plan_names.index(
        "calculate_risk_metrics"
    ) + 1
    assert trace_names.index("run_stress_test") == trace_names.index(
        "calculate_risk_metrics"
    ) + 1
    assert len(result.stress_test_results) == 1
    assert result.stress_test_results[0]["scenario_name"] == "Combined selloff"
    assert "Stress Scenario Analysis" in result.llm_commentary


def test_workflow_passes_stress_results_to_commentary_tool(tmp_path):
    config_path = tmp_path / "risk_config.json"
    config_path.write_text(
        json.dumps(
            {
                "stress_scenarios": [
                    {
                        "name": "Equity selloff",
                        "equity_selloff_pct": 0.10,
                        "tech_selloff_pct": 0.20,
                        "rates_shock_bps": 100,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def capture_commentary(*args, **kwargs):
        captured["stress_results"] = kwargs.get("stress_results")
        from src.agent import generate_risk_commentary

        return generate_risk_commentary(*args, **kwargs)

    replacements = {
        "calculate_risk_metrics": _fake_generate_portfolio_risk_report,
        "generate_commentary": capture_commentary,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
        config_file=str(config_path),
    )

    assert captured["stress_results"][0]["scenario_name"] == "Equity selloff"


def test_workflow_skips_stress_test_without_scenarios():
    tools = [
        replace(tool, handler=_fake_generate_portfolio_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    assert result.stress_test_results == []
    assert "run_stress_test" not in [step.name for step in result.plan.steps]
    assert "run_stress_test" not in [
        entry.tool_name for entry in result.execution_trace
    ]


def test_validation_failure_regenerates_commentary_once_and_revalidates():
    validation_results = iter(
        [
            ValidationResult(False, [], ["unsafe commentary"], []),
            ValidationResult(True, [], [], []),
        ]
    )
    regeneration_calls = []

    def validate_once_then_pass(*args):
        return next(validation_results)

    def regenerate(*args, **kwargs):
        regeneration_calls.append((args, kwargs))
        return "Regenerated commentary with assumptions and limitations; not investment advice."

    replacements = {
        "calculate_risk_metrics": _fake_generate_portfolio_risk_report,
        "generate_commentary": lambda *args, **kwargs: "Unsafe original commentary.",
        "validate_report": validate_once_then_pass,
        "regenerate_commentary_with_validation_errors": regenerate,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    assert len(regeneration_calls) == 1
    regeneration_args, regeneration_kwargs = regeneration_calls[0]
    assert regeneration_args[0]["risk_metrics"]["historical_var"] == 0.02
    assert regeneration_args[1] == "Unsafe original commentary."
    assert regeneration_args[2] == ["unsafe commentary"]
    assert regeneration_args[3] == []
    assert regeneration_args[4]
    assert regeneration_kwargs == {"use_llm": False}
    assert result.validation_result.passed is True
    assert result.llm_commentary.startswith("Regenerated commentary")
    assert [entry.tool_name for entry in result.execution_trace] == [
        "parse_portfolio",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
        "regenerate_commentary_with_validation_errors",
        "validate_report",
    ]


def test_validation_failure_after_retry_returns_final_failed_result():
    validation_calls = 0
    regeneration_calls = 0

    def always_fail_validation(*args):
        nonlocal validation_calls
        validation_calls += 1
        return ValidationResult(False, [], ["still invalid"], ["review commentary"])

    def regenerate(*args, **kwargs):
        nonlocal regeneration_calls
        regeneration_calls += 1
        return "Regenerated but still invalid commentary."

    replacements = {
        "calculate_risk_metrics": _fake_generate_portfolio_risk_report,
        "generate_commentary": lambda *args, **kwargs: "Initial invalid commentary.",
        "validate_report": always_fail_validation,
        "regenerate_commentary_with_validation_errors": regenerate,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    assert regeneration_calls == 1
    assert validation_calls == 2
    assert result.validation_result.passed is False
    assert result.validation_result.errors == ["still invalid"]
    assert [entry.tool_name for entry in result.execution_trace[-3:]] == [
        "validate_report",
        "regenerate_commentary_with_validation_errors",
        "validate_report",
    ]
