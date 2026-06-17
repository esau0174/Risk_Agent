# RiskFlow Agent

Controlled LLM-assisted risk workflow agent for Market Risk, Credit Risk / PFE, Sensitivity Risk / Greeks aggregation, and Regulatory Readiness.

**LLM plans and comments. Python tools calculate. Validators gate execution and output.**

RiskFlow Agent is a prototype AI + Finance engineering demo designed to show controlled agentic workflow orchestration for financial risk analytics. It turns a natural-language request into an approved, auditable risk workflow while keeping risk calculations deterministic and guardrailed.

## Why This Is An Agent

RiskFlow Agent is not a single portfolio VaR script. It separates autonomous planning from controlled execution:

- A planner, rule-based or LLM-backed, proposes a tool sequence from the request and available inputs.
- A plan validator rejects unknown tools, unsupported regulatory-capital tools, and invalid ordering.
- A registered tool layer exposes deterministic capabilities for analytics, retrieval, commentary, and validation.
- An approved-plan executor runs supported tool steps sequentially with explicit context adapters.
- Deterministic Python modules calculate the metrics; the LLM does not invent risk numbers.
- Validators check numerical consistency, methodology grounding, policy guardrails, and unsupported recommendations.
- The run result preserves a user report, execution trace, validation result, and raw analytics outputs.

## Agent Architecture

```text
Natural-language request + input context
        |
        v
Planner: LLM planner or rule fallback
        |
        v
Plan validator
        |
        v
Approved tool registry + ToolExecutor
        |
        v
Deterministic execution
        |
        v
Risk analytics + methodology retrieval
        |
        v
Commentary generation
        |
        v
Report validation / guardrails
        |
        v
User report + execution trace + raw outputs
```

Canonical package structure:

- `src/core/`: tool registry, tool executor, risk configuration.
- `src/data/`: portfolio parsing, structured file loading, market data.
- `src/workflow/`: planners, plan validation, approved-plan executor, orchestration types.
- `src/market_risk/`: historical market-risk analytics and stress testing.
- `src/credit_risk/`: counterparty exposure / PFE analytics.
- `src/sensitivity_risk/`: precomputed Greeks loading, validation, and aggregation.
- `src/regulatory_risk/`: SA-CCR and SIMM / RegIM readiness checks.
- `src/knowledge/`: local methodology retrieval.
- `src/reporting/`: commentary and report formatting utilities.
- `src/validators/`: numerical, methodology, regulatory, and guardrail validation.

See [docs/architecture.md](docs/architecture.md) for more implementation detail.

## Implemented Workflows

**Market Risk**

- Portfolio metadata: portfolio ID, book, asset classes, risk buckets, region, total notional.
- Annualized volatility.
- Historical VaR and Expected Shortfall.
- Maximum drawdown.
- Dollarized VaR, Expected Shortfall, drawdown, and stress loss when notional is available.
- Deterministic stress testing with simple equity, technology, and rates shocks.

**Credit Risk / PFE**

- Counterparty exposure profile validation.
- Peak 95% and 99% PFE.
- EPE / average expected exposure.
- Netting set concentration.
- Optional limit utilization by netting set with `PASSED`, `WARNING`, or `BREACHED` status.

**Sensitivity Risk / Greeks**

- Consumes precomputed Greeks from an upstream pricing or risk engine.
- Validates sensitivity-file schema.
- Aggregates delta, gamma, vega, and theta.
- Identifies largest delta and vega risk-factor concentrations.
- Reports currency consistency warnings when applicable.
- Does not calculate pricing-model Greeks.

**Regulatory Readiness**

- SA-CCR and SIMM / RegIM input-completeness checks.
- Distinguishes portfolio-level metadata from missing trade-level SA-CCR inputs.
- Uses supplied sensitivity fields to improve SIMM / RegIM readiness.
- Explicit guardrails prevent fabricated regulatory capital or margin numbers.
- Does not calculate SA-CCR EAD, SIMM margin, or RegIM.

## Quickstart

Install and run tests:

```bash
pip install -e ".[dev]"
pytest -q
```

Run the finalized v1 demo with the deterministic rule planner:

```bash
python examples/run_riskflow_agent_demo.py --planner rule --scenario full --show-plan
```

Run a Market Risk + Greeks + Regulatory Readiness workflow:

```bash
python examples/run_riskflow_agent_demo.py --planner rule --query "Run market risk, Greeks review, and regulatory readiness." --show-plan
```

Run a SIMM readiness workflow using Greeks sensitivities:

```bash
python examples/run_riskflow_agent_demo.py --planner rule --query "Check SIMM readiness using Greeks sensitivities." --show-plan
```

Run failure-case demos:

```bash
python examples/failure_cases/run_invalid_portfolio_demo.py
python examples/failure_cases/run_report_validation_failure_demo.py
```

The primary entry point is `examples/run_riskflow_agent_demo.py`. Older focused demos are archived under `examples/legacy/`; reviewers should use the primary entry point rather than the archived legacy demos.

## Optional LLM Usage

The project works offline with `--planner rule`. With `--planner auto`, RiskFlow Agent uses the LLM planner when an API key is available and falls back clearly to the rule planner when it is not. With `--planner llm`, missing or malformed LLM planning fails safely before execution.

Project-root `.env` example:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
# Optional:
# OPENAI_BASE_URL=https://your-compatible-endpoint/v1
```

Temporary PowerShell setup:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
$env:OPENAI_MODEL="gpt-4o-mini"
```

Do not commit API keys. `.env` is ignored by `.gitignore`.

## Demo Inputs

The v1 demo uses sample files under `examples/`:

- `sample_portfolio.csv`: institutional-style market holdings with metadata and notional.
- `sample_exposure_profile.csv`: counterparty exposure profile for PFE analytics.
- `sample_sensitivities.csv`: precomputed Greeks for sensitivity aggregation and SIMM / RegIM readiness.
- `sample_risk_config.json`: fixed market data window, VaR settings, stress scenario, and credit limits.

The market-data lookback window is fixed from `2023-01-01` to `2024-12-31` for more reproducible demo output. Prices are still fetched live, so small data-source revisions may slightly change reported metrics.

## Structured Output

`run_agent_workflow()` returns a structured result with:

- `user_report`: clean user-facing report.
- `execution_trace`: ordered tool execution trace.
- `validation_result`: domain validation and guardrail status.
- `raw_outputs`: underlying analytics outputs.
- `orchestration_trace`: proposed plan, approved plan, selected route, executed tools, skipped tools, and execution mode.

The demo can save trace JSON with `--trace-file`.

## Failure Demos And Guardrails

RiskFlow Agent includes expected failure paths:

- Invalid portfolio weights are rejected before market risk calculation.
- Unsupported or misordered tools are rejected before execution.
- Report validation catches inconsistent commentary, fabricated metrics, and missing assumptions.
- Regulatory readiness reports missing inputs rather than fabricating capital or margin numbers.
- Commentary must not provide investment advice.

## Interview Framing

Use this project to discuss controlled autonomy in financial risk systems:

- The planner provides agentic workflow selection.
- The tool registry defines the allowed action space.
- The executor runs deterministic Python tools, not arbitrary model-generated code.
- Validators act as gates before and after execution.
- The execution trace makes the workflow auditable and reproducible.
- Regulatory workflows are readiness screens only, intentionally avoiding false claims of capital or margin calculation.

This maps well to AI-enabled quant developer work: orchestration, tool use, deterministic analytics, validation guardrails, and explainable risk reporting.

## Scope Boundaries

- No real SA-CCR EAD calculation.
- No real SIMM or RegIM margin calculation.
- No Monte Carlo PFE generation.
- No pricing-model Greeks calculation.
- No production pricing engine.
- No XVA valuation, PD/LGD/EAD modeling, or regulatory capital stack.
- No investment advice.
- No unrestricted autonomous tool execution.
- No production deployment, persistence, or distributed scheduler.

## Next Extensions

- Typed execution graph compiled from the approved plan.
- Richer notional attribution and limit-monitoring views.
- Richer regulatory input schema.
- Optional vector-based methodology retrieval.
- More formal factor exposure and stress scenario libraries.
- PDF or HTML report export.

## Disclaimer

RiskFlow Agent is for analytical demonstration only and does not constitute investment advice.
