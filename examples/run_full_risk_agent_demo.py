from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflow import AgentRunResult, run_full_risk_agent_workflow


MARKET_QUERY = "Analyze the uploaded portfolio for downside risk and concentration risk."
CREDIT_QUERY = (
    "Analyze the counterparty exposure profile and summarize PFE concentration."
)
MARKET_DATA_FILE = "examples/sample_portfolio.csv"
CREDIT_DATA_FILE = "examples/sample_exposure_profile.csv"
CONFIG_FILE = "examples/sample_risk_config.json"
DEFAULT_TRACE_FILE = "logs/full_demo_trace.json"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    result = run_full_risk_agent_workflow(
        market_query=MARKET_QUERY,
        market_data_file=MARKET_DATA_FILE,
        credit_query=CREDIT_QUERY,
        credit_data_file=CREDIT_DATA_FILE,
        config_file=CONFIG_FILE,
        use_llm=False,
    )

    print(result.user_report)
    if args.trace_file:
        save_execution_trace(result, args.trace_file)


def save_execution_trace(result: AgentRunResult, trace_file: str | Path) -> Path:
    """Write the structured execution trace to a JSON file."""
    path = Path(trace_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.execution_trace, indent=2),
        encoding="utf-8",
    )
    return path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the combined FinRisk Agent demo.")
    parser.add_argument(
        "--trace-file",
        nargs="?",
        const=DEFAULT_TRACE_FILE,
        help=(
            "Optionally save the internal execution trace as JSON. "
            f"Defaults to {DEFAULT_TRACE_FILE} when no path is supplied."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
