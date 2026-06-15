from __future__ import annotations

import json

from examples.failure_cases import (
    run_invalid_portfolio_demo,
    run_report_validation_failure_demo,
)


def test_invalid_portfolio_demo_prints_clean_validation_failure(capsys):
    run_invalid_portfolio_demo.main([])

    output = capsys.readouterr().out
    assert "Status: FAILED (expected)" in output
    assert "Weights must sum to 1.0" in output
    assert "received sum 1.20000000" in output
    assert (
        "Risk calculation was not run because portfolio validation failed." in output
    )


def test_invalid_portfolio_demo_can_save_failed_trace(tmp_path, capsys):
    trace_file = tmp_path / "invalid_portfolio_trace.json"

    run_invalid_portfolio_demo.main(["--trace-file", str(trace_file)])

    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace[0]["tool_name"] == "load_portfolio_file"
    assert trace[0]["status"] == "failed"
    assert "Weights must sum to 1.0" in trace[0]["error"]
    assert "Execution trace saved to:" in capsys.readouterr().out


def test_report_validation_failure_demo_prints_errors_and_warnings(capsys):
    run_report_validation_failure_demo.main()

    output = capsys.readouterr().out
    assert "Overall validation status: FAILED" in output
    assert "Historical VaR percentage mismatch: expected 2.00%, found 9.00%." in output
    assert "Warnings:" in output
    assert "Commentary should include assumptions or limitations." in output
