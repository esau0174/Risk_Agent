from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.workflow import run_risk_workflow


def main() -> None:
    result = run_risk_workflow(
        "Analyze the counterparty exposure profile and summarize PFE concentration.",
        portfolio_file="examples/sample_exposure_profile.csv",
        use_llm=False,
    )

    print("FinRisk Agent - Counterparty PFE Workflow Demo")
    print("================================================")
    print("Workflow Plan")
    for step in result.plan.steps:
        print(f"- {step.name}: {step.status} - {step.output_summary}")

    print("\nExecution Trace")
    for entry in result.execution_trace:
        print(f"- {entry.step_number}. {entry.tool_name}: {entry.status}")

    print("\nPFE Metrics")
    for name, value in result.pfe_result.items():
        print(f"- {name}: {value}")

    print("\nCommentary")
    print(result.llm_commentary)
    print(f"\nValidation: {'PASSED' if result.validation_result.passed else 'FAILED'}")


if __name__ == "__main__":
    main()
