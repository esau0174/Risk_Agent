from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflow import run_risk_workflow


QUERY = "Analyze the uploaded portfolio for downside risk."
DATA_FILE = "examples/failure_cases/invalid_portfolio.csv"
DEFAULT_TRACE_FILE = "logs/invalid_portfolio_trace.json"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    print("Invalid Portfolio Validation Demo")
    print("=================================")
    try:
        run_risk_workflow(
            query=QUERY,
            data_file=DATA_FILE,
            use_llm=False,
        )
    except RuntimeError as exc:
        print("Status: FAILED (expected)")
        print(f"Validation error: {_clean_error_message(exc)}")
        print("Risk calculation was not run because portfolio validation failed.")
        if args.trace_file:
            path = save_execution_trace(exc, args.trace_file)
            print(f"Execution trace saved to: {path}")
        return

    raise RuntimeError("Expected invalid portfolio validation to fail.")


def save_execution_trace(error: RuntimeError, trace_file: str | Path) -> Path:
    """Save the partial workflow trace attached to a failed tool execution."""
    trace = [asdict(entry) for entry in getattr(error, "execution_trace", [])]
    path = Path(trace_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return path


def _clean_error_message(error: RuntimeError) -> str:
    message = str(error)
    if " failed: " in message:
        message = message.split(" failed: ", maxsplit=1)[1]
    return message.removeprefix("ValueError: ")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demonstrate invalid portfolio weight handling."
    )
    parser.add_argument(
        "--trace-file",
        nargs="?",
        const=DEFAULT_TRACE_FILE,
        help=(
            "Optionally save the failed execution trace as JSON. "
            f"Defaults to {DEFAULT_TRACE_FILE} when no path is supplied."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
