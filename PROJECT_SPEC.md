# RiskFlow Agent v1 Project Spec

RiskFlow Agent is a controlled LLM-assisted risk workflow agent for Market Risk,
Credit Risk / PFE, Sensitivity Risk / Greeks aggregation, and Regulatory Readiness.

**LLM plans and comments. Python tools calculate. Validators gate execution and output.**

Historical Phase 1 planning notes have been moved to
`docs/legacy/project_history.md`. This file describes the current v1 implementation scope.

## Goal

Demonstrate controlled agentic workflow orchestration for financial risk analytics:

- Convert a natural-language request into an approved tool plan.
- Validate that plan before execution.
- Execute deterministic Python analytics tools.
- Retrieve local methodology notes.
- Generate LLM or deterministic commentary grounded in calculated outputs.
- Validate generated reports for numerical consistency and guardrails.
- Preserve execution trace, validation results, and raw analytics outputs.

## Current Workflows

### Market Risk

Inputs:

- Structured market portfolio file with `ticker` and `weight`.
- Optional metadata: `portfolio_id`, `book`, `asset_class`, `risk_bucket`,
  `region`, and `notional_usd`.
- Risk configuration including market data dates, VaR confidence level, enabled
  metrics, stress scenarios, and reporting settings.

Outputs:

- Portfolio metadata and total notional when supplied.
- Annualized volatility.
- Historical VaR.
- Expected Shortfall.
- Maximum drawdown.
- Dollarized VaR, Expected Shortfall, drawdown, and stress loss when notional is available.
- Deterministic stress scenario loss and stressed portfolio value.

### Credit Risk / PFE

Inputs:

- Exposure profile file with `netting_set`, `time_years`,
  `expected_exposure`, and `pfe_95`.
- Optional `pfe_99`, `currency`, and `counterparty`.
- Optional configured credit limits by netting set.

Outputs:

- Peak 95% PFE and time of peak.
- Peak 99% PFE when supplied.
- EPE / average expected exposure.
- Maximum expected exposure.
- Largest netting set by peak PFE.
- Limit utilization and status: `PASSED`, `WARNING`, or `BREACHED`.

### Sensitivity Risk / Greeks

Inputs:

- Precomputed sensitivity file with `portfolio_id`, `book`, `trade_id`,
  `instrument_type`, `risk_class`, `risk_factor`, `bucket`, `delta`, `gamma`,
  `vega`, `theta`, and `currency`.

Outputs:

- Schema validation for supplied sensitivities.
- Total delta, gamma, vega, and theta.
- Absolute delta by risk class.
- Absolute vega by bucket.
- Largest delta and vega risk-factor concentrations.
- Currency consistency warnings when multiple currencies are present.

Boundary:

- RiskFlow Agent consumes Greeks from an upstream pricing or risk engine.
- It does not calculate pricing-model Greeks.

### Regulatory Readiness

Inputs:

- Available workflow context from market portfolios, exposure profiles, and
  sensitivity files.

Outputs:

- SA-CCR readiness status and missing trade-level inputs.
- Available portfolio-level metadata such as portfolio notional and asset class.
- SIMM / RegIM readiness status, available inputs, and missing inputs.
- Explicit guardrail that no regulatory capital or margin number is generated.

Boundary:

- No real SA-CCR EAD calculation.
- No SIMM or RegIM margin calculation.
- No regulatory capital stack.

## Agent Architecture

```text
natural-language request
  -> planner
  -> plan validator
  -> approved tool registry
  -> approved-plan executor
  -> deterministic analytics tools
  -> methodology retrieval
  -> commentary generation
  -> report validation
  -> user report + execution trace
```

The approved-plan executor is the preferred execution path. It runs validated
registered tools sequentially using explicit context adapters. If a validated
plan cannot be directly mapped, the system can fall back to conservative
deterministic routes and records that fallback in the orchestration trace.

## Tool And Validation Model

Registered tools cover:

- Data loading and parsing.
- Portfolio validation.
- Market risk calculation.
- Stress testing.
- PFE calculation.
- Sensitivity file loading, validation, and aggregation.
- Regulatory readiness assessment.
- Methodology retrieval.
- Commentary generation and regeneration.
- Report validation.

Validators enforce:

- Portfolio weight validity.
- Positive-loss conventions for VaR, Expected Shortfall, and drawdown.
- Dollar metric consistency against notional.
- Stress and PFE numerical consistency.
- Sensitivity workflow status in combined validation summaries.
- Regulatory readiness structure and no fabricated capital or margin numbers.
- No direct investment recommendations.
- Methodology grounding.

## Primary Demo

Use the primary entry point:

```bash
python examples/run_riskflow_agent_demo.py --planner rule --scenario full --show-plan
```

Additional supported demo paths:

```bash
python examples/run_riskflow_agent_demo.py --planner rule --query "Run market risk, Greeks review, and regulatory readiness." --show-plan
python examples/run_riskflow_agent_demo.py --planner rule --query "Check SIMM readiness using Greeks sensitivities." --show-plan
python examples/failure_cases/run_invalid_portfolio_demo.py
python examples/failure_cases/run_report_validation_failure_demo.py
```

Older focused demos are archived under `examples/legacy/` and are not the
recommended review entry point.

## Scope Boundaries

- No real SA-CCR EAD calculation.
- No real SIMM or RegIM margin calculation.
- No Monte Carlo PFE generation.
- No pricing-model Greeks calculation.
- No XVA valuation, PD/LGD/EAD modeling, or regulatory capital stack.
- No investment advice.
- No unrestricted autonomous tool execution.
- No production deployment or distributed scheduler.
