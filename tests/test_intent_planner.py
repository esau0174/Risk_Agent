import pytest

from src.workflow import Intent, build_workflow_plan_for_intent, classify_intent


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("Run a stress scenario for an equity selloff", Intent.STRESS_TEST),
        ("Apply a 10% shock to technology holdings", Intent.STRESS_TEST),
        ("Explain the methodology for historical VaR", Intent.METHODOLOGY_EXPLANATION),
        ("How is Expected Shortfall calculated?", Intent.METHODOLOGY_EXPLANATION),
        ("Give me a definition of maximum drawdown", Intent.METHODOLOGY_EXPLANATION),
        ("Validate this generated risk report", Intent.REPORT_VALIDATION),
        ("Please check report output", Intent.REPORT_VALIDATION),
        ("Review report guardrails", Intent.REPORT_VALIDATION),
        ("Analyze 60% SPY and 40% QQQ", Intent.PORTFOLIO_RISK),
    ],
)
def test_classify_intent_uses_deterministic_rules(query, expected_intent):
    assert classify_intent(query) is expected_intent


def test_portfolio_risk_plan_matches_existing_full_workflow():
    plan = build_workflow_plan_for_intent(Intent.PORTFOLIO_RISK)

    assert [step.name for step in plan.steps] == [
        "parse_portfolio",
        "validate_portfolio",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]


def test_methodology_explanation_plan_is_planning_only():
    plan = build_workflow_plan_for_intent(Intent.METHODOLOGY_EXPLANATION)

    assert [step.name for step in plan.steps] == [
        "retrieve_methodology",
        "generate_commentary",
    ]
    assert all(step.status == "pending" for step in plan.steps)


def test_stress_test_plan_contains_unregistered_placeholder_only():
    plan = build_workflow_plan_for_intent(Intent.STRESS_TEST)

    assert [step.name for step in plan.steps] == ["stress_test"]
    assert plan.steps[0].tool_name == "stress_test"
    assert "Placeholder" in plan.steps[0].description


def test_report_validation_plan_contains_validation_step_only():
    plan = build_workflow_plan_for_intent(Intent.REPORT_VALIDATION)

    assert [step.name for step in plan.steps] == ["validate_report"]
