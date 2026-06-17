from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from riskflow_agent import run_agent_workflow
from riskflow_agent.cli import (
    _available_input_schemas,
    _available_input_schemas_text,
    _display_steps,
    _parse_args,
    _print_execution_trace_summary,
    _print_plan,
    _requested_modules_text,
    _validation_summary,
    run_cli,
    save_execution_trace,
)


def main(argv: list[str] | None = None) -> None:
    run_cli(argv, workflow_runner=run_agent_workflow)


if __name__ == "__main__":
    main()
