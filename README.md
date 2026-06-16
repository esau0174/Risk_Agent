# RiskFlow Agent

RiskFlow Agent is an agentic financial risk workflow demo built around deterministic Python analytics. It combines LLM-assisted workflow planning, registered tool execution, runtime tracing, local methodology retrieval, LLM or deterministic commentary, and validation gates.

The project supports market-risk, counterparty-exposure, and regulatory-readiness workflows through one orchestration and presentation layer. LLMs may propose plans and write commentary, but deterministic Python tools calculate risk metrics and validators approve execution and output.

**LLM plans. Python tools calculate. Validators gate execution and output.**

This is an engineering and analytics demonstration, not a production risk platform or investment advisory system.

## Why It Is Agentic

RiskFlow Agent does more than call an LLM from a script. The workflow makes planning and execution explicit:

- The primary planner can use an LLM to propose a workflow from the user request, available schemas, and registered tools.
- A deterministic rule planner remains available as fallback/offline mode.
- A tool registry exposes named shared, market-risk, and credit-risk capabilities.
- `ToolExecutor` invokes registered handlers and returns structured results.
- An execution trace records actual tool calls, statuses, inputs, outputs, and errors.
- Data schema detection routes market portfolios and exposure profiles through different analytical paths.
- Commentary is grounded in calculated results and retrieved methodology.
- A deterministic plan validator must approve proposed tool sequences before execution.
- A report validation gate checks numerical consistency and policy guardrails, with one controlled commentary retry when required.

The LLM planner cannot execute tools, calculate VaR, ES, PFE, SA-CCR, SIMM, RegIM, capital, margin, or bypass validation. Unsupported or misordered tool plans are rejected before execution.

## Supported Workflows

### Market Risk

The market-risk path accepts ticker weights, loads historical market data, calculates portfolio returns, and produces:

- Annualized volatility
- Historical Value at Risk (VaR)
- Expected Shortfall (ES)
- Maximum drawdown
- Correlation matrix support in the calculation layer
- Largest-weight and ticker-composition concentration analysis
- Optional deterministic equity, technology, and rates stress scenarios

VaR, ES, and drawdown are reported as positive loss magnitudes.

### Credit Risk

The credit-risk path accepts a supplied counterparty exposure profile and calculates:

- Peak PFE at 95%
- Peak PFE at 99%, when available
- Time of peak PFE
- Average Expected Exposure / EPE
- Maximum expected exposure
- Expected exposure by netting set
- Largest netting set by peak PFE
- Optional limit utilization for the largest netting set when credit limits are configured

This path summarizes supplied exposure profiles. It does not generate exposures through a pricing or Monte Carlo engine.
When `credit_limits` are supplied by netting set, utilization is calculated as Peak 95% PFE divided by the configured limit. Limit status values are `PASSED`, `WARNING`, or `BREACHED`.

### Regulatory Risk

The regulatory-risk path is a readiness screen, not a capital calculator. It checks whether available inputs are sufficient for downstream SA-CCR and SIMM / RegIM workflows, reports missing fields, and explicitly avoids generating regulatory capital or margin numbers when inputs are insufficient.

## Input Model

The shared entry point is `run_risk_workflow()` from `src.workflow`:

- `query`: natural-language analysis instruction.
- `data_file`: optional CSV, XLSX, or JSON holdings or exposure-profile file.
- `config_file`: optional JSON calculation and reporting configuration.

Without `data_file`, the market portfolio can be parsed from the query. The legacy `portfolio_file` parameter remains available as a backward-compatible alias.

Supported file schemas:

```text
Market portfolio: ticker, weight
Exposure profile: netting_set, time_years, expected_exposure, pfe_95
Optional exposure fields: pfe_99, currency, counterparty
```

## Architecture

```text
query + data_file + config_file
              |
              v
 LLM or rule-based workflow plan
              |
              v
 deterministic plan validation
              |
              v
     registered tool execution
              |
       +------+------+------+
       |             |      |
       v             v      v
 market risk   credit risk regulatory
 analytics     exposure    readiness
               analytics
       |             |      |
       +------+------+------+
              v
   local methodology retrieval
              v
 LLM or deterministic commentary
              v
 validation and guardrail checks
              v
 structured AgentRunResult
  |       |       |       |
 report  trace  validation raw outputs
```

Canonical source packages:

- `src/core/`: tool registry, tool executor, and risk configuration.
- `src/data/`: file loading, natural-language portfolio parsing, portfolio calculations, and market data.
- `src/workflow/`: planner, engine, execution helpers, trace handling, and result types.
- `src/validators/`: market, stress, PFE, methodology, and commentary validation.
- `src/market_risk/`: market metrics, report assembly, and stress testing.
- `src/credit_risk/`: counterparty exposure and PFE analytics.
- `src/regulatory_risk/`: SA-CCR and SIMM / RegIM readiness screening.
- `src/knowledge/`: local methodology retrieval.
- `src/reporting/`: commentary generation and report formatting utilities.

Canonical imports use the package paths above. See [docs/architecture.md](docs/architecture.md) for implementation details.

## Structured Agent Output

The combined workflow returns an `AgentRunResult` that separates presentation from internal execution details:

- `user_report`: clean user-facing market-risk, credit-risk, and regulatory-readiness summary.
- `execution_trace`: auditable workflow and tool execution records.
- `validation_result`: structured guardrail checks, errors, and warnings.
- `raw_outputs`: underlying market-risk and credit-risk analytics outputs.

The main demo prints only `user_report` by default. Internal trace data can be serialized separately for inspection without cluttering the user-facing report.

## Validation And Guardrails

Generated reports pass through deterministic validation covering:

- Portfolio weight consistency
- Positive-loss VaR, ES, and drawdown conventions
- Expected Shortfall greater than or equal to VaR
- Commentary percentages versus calculated market metrics
- Stress loss, stressed value, and contribution consistency
- PFE, peak-time, and EPE consistency
- Credit limit utilization status for configured netting-set limits
- Regulatory readiness missing-input reporting and no fabricated capital or margin numbers
- Citations limited to retrieved methodology notes
- Direct trade recommendations and guaranteed-outcome language
- Presence of assumptions or limitations

If commentary fails validation, the workflow permits one regeneration attempt and validates the revised output again. It does not retry indefinitely.

## Installation

Requires Python 3.10+.

```bash
pip install -e .
```

For local development and tests, install the `dev` extra:

```bash
pip install -e ".[dev]"
pytest -q
```

For LLM commentary, create a local `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
```

Do not commit `.env` or API keys. The credit-risk demo uses deterministic commentary and does not require an API key.

## Quick Start

Run the complete test suite:

```bash
pytest -q
```

Run the recommended policy-constrained autonomous planning demo:

```bash
python examples/run_riskflow_agent_demo.py
```

The primary demo is a thin wrapper around `src.workflow.run_agent_workflow()`.
It defaults to `--scenario full` and supports:

- `--planner auto | llm | rule`
- `--scenario full | market | credit | regulatory`
- `--query "custom user request"`
- `--show-plan` to display the approved tool sequence
- `--trace-file` to save the internal execution trace as JSON

```bash
python examples/run_riskflow_agent_demo.py --scenario market --show-plan
```

`--planner auto` uses LLM planning when an API key is available and otherwise falls back to the rule planner with an explicit message. Use `--planner rule` for deterministic offline demos.

The default full scenario fetches live historical market data for the fixed
window from `2023-01-01` through `2024-12-31`, as configured in
`examples/sample_risk_config.json`.

Older module-level demos are archived under `examples/legacy/` for reference.

## Failure-Case Demos

Demonstrate portfolio validation stopping execution before risk calculation:

```bash
python examples/failure_cases/run_invalid_portfolio_demo.py
```

Optionally save the partial failed trace:

```bash
python examples/failure_cases/run_invalid_portfolio_demo.py --trace-file
```

Demonstrate report/commentary validation with an intentionally inconsistent VaR value:

```bash
python examples/failure_cases/run_report_validation_failure_demo.py
```

## Example Output Snapshot

The full demo begins with a `Combined Executive Summary` covering the active modules: **Market Risk**, **Credit Risk**, and **Regulatory Risk**.

Representative market-risk results:

- Annualized volatility: 26.71%
- 95% historical VaR: 2.32%
- 95% Expected Shortfall: 3.47%
- Maximum drawdown: 23.77%
- Stress scenario loss: 22.50%
- Validation: PASSED

Representative Credit Risk results:

- Peak 95% PFE: USD 2,100,000
- Peak 99% PFE: USD 2,600,000
- EPE: USD 1,080,000
- Largest netting set: NS-001
- Validation: PASSED

Representative Regulatory Risk readiness output:

- SA-CCR readiness: WARNING
- SIMM / RegIM readiness: WARNING
- Regulatory capital calculation: Not performed
- SA-CCR missing inputs: trade_type, notional, maturity, asset_class, supervisory_category
- SIMM / RegIM missing inputs: risk_factor_sensitivities, margin_class, product_class, risk_factor_type, currency
- Guardrail: no regulatory capital number is generated from insufficient inputs
- Validation: PASSED

## Limitations

- Planning and routing are deterministic rather than LLM-directed.
- Market risk is historical and focused on simple equity/ETF portfolios.
- Only historical VaR is implemented; no parametric or Monte Carlo VaR is available.
- Concentration observations are based on weights and ticker composition, not a formal factor model.
- Stress testing uses deterministic ticker proxies rather than full revaluation.
- PFE analytics consume supplied profiles rather than generating exposures from trades.
- XVA, PD/LGD/EAD, SIMM, and RegIM are not implemented.
- SA-CCR readiness is screened, but SA-CCR capital is not calculated.
- Methodology retrieval is local and keyword-based, without embeddings or vector search.
- Tool execution is synchronous and in-process, with no durable workflow state.
- LLM commentary quality depends on the configured model despite deterministic validation controls.

## Future Extensions

- Improve retrieval with embeddings, vector search, and stronger ranking.
- Add formal factor exposure and richer scenario or full-revaluation stress models.
- Generate exposure profiles from pricing simulations and extend toward XVA analytics.
- Add SA-CCR exposure and capital calculations; SA-CCR is not currently implemented.
- Add durable execution state, richer observability, and PDF/HTML report export.

## Disclaimer

RiskFlow Agent is for analytical demonstration only and does not constitute investment advice.
