from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflow import run_risk_workflow
from src.tool_registry import list_registered_tools
from examples.demo_utils import (
    print_execution_trace,
    print_input_summary,
    print_methodology_notes,
    print_registered_tools_by_module,
    print_validation_result,
    print_workflow_plan,
)


def main() -> None:
    query = "Analyze the counterparty exposure profile and summarize PFE concentration."
    portfolio_file = "examples/sample_exposure_profile.csv"
    result = run_risk_workflow(
        query,
        portfolio_file=portfolio_file,
        use_llm=False,
    )

    print("FinRisk Agent - Credit Risk Workflow Demo")
    print("==========================================")
    print("Counterparty Exposure / PFE Analysis")
    print()
    print_input_summary(
        query,
        portfolio_file,
        active_modules=result.active_modules,
    )
    print_registered_tools_by_module(list_registered_tools())
    print_workflow_plan(result.plan)
    print_execution_trace(result.execution_trace)
    print("Credit Risk Results / PFE Metrics")
    for name, value in result.pfe_result.items():
        print(f"- {name}: {value}")
    print()
    print_methodology_notes(result.methodology_notes)
    print("Commentary")
    print(result.llm_commentary)
    print()
    print_validation_result(result.validation_result)


if __name__ == "__main__":
    main()
