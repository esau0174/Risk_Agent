# FinRisk Agent

FinRisk Agent is an agentic financial risk workflow demo built around deterministic Python analytics. It combines explicit workflow planning, registered tool execution, runtime tracing, local methodology retrieval, LLM or deterministic commentary, and a validation gate.

The project supports market-risk and counterparty-exposure workflows through one orchestration engine. Risk calculations remain authoritative; generated commentary explains supplied results and is checked against them before the workflow returns.

This is an engineering and analytics demonstration, not a production risk platform or investment advisory system.

## Why It Is Agentic

FinRisk Agent does more than call an LLM from a script. The workflow makes planning and execution explicit:

- A deterministic planner builds the expected sequence of steps.
- A tool registry exposes named shared, market-risk, and credit-risk capabilities.
- `ToolExecutor` invokes registered handlers and returns structured results.
- An execution trace records actual tool calls, statuses, inputs, outputs, and errors.
- Data schema detection routes market portfolios and exposure profiles through different analytical paths.
- Commentary is grounded in calculated results and retrieved methodology.
- A validation gate checks numerical consistency and policy guardrails, with one controlled commentary retry when required.

The current planner is rule-based. The LLM does not autonomously select tools or calculate risk metrics.

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

### Credit Risk / PFE

The credit-risk path accepts a supplied counterparty exposure profile and calculates:

- Peak PFE at 95%
- Peak PFE at 99%, when available
- Time of peak PFE
- Average Expected Exposure / EPE
- Maximum expected exposure
- Expected exposure by netting set
- Largest netting set by peak PFE

This path summarizes supplied exposure profiles. It does not generate exposures through a pricing or Monte Carlo engine.

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
     deterministic workflow plan
              |
              v
     registered tool execution
              |
       +------+------+
       |             |
       v             v
 market risk     credit risk / PFE
 analytics       exposure analytics
       |             |
       +------+------+
              v
   local methodology retrieval
              v
 LLM or deterministic commentary
              v
 validation and guardrail checks
              v
 WorkflowResult + execution trace
```

Canonical source packages:

- `src/core/`: tool registry, tool executor, and risk configuration.
- `src/data/`: file loading, natural-language portfolio parsing, portfolio calculations, and market data.
- `src/workflow/`: planner, engine, execution helpers, trace handling, and result types.
- `src/validators/`: market, stress, PFE, methodology, and commentary validation.
- `src/market_risk/`: market metrics, report assembly, and stress testing.
- `src/credit_risk/`: counterparty exposure and PFE analytics.
- `src/knowledge/`: local methodology retrieval.
- `src/reporting/`: commentary generation and report formatting utilities.

Canonical imports use the package paths above. See [docs/architecture.md](docs/architecture.md) for implementation details.

## Validation And Guardrails

Generated reports pass through deterministic validation covering:

- Portfolio weight consistency
- Positive-loss VaR, ES, and drawdown conventions
- Expected Shortfall greater than or equal to VaR
- Commentary percentages versus calculated market metrics
- Stress loss, stressed value, and contribution consistency
- PFE, peak-time, and EPE consistency
- Citations limited to retrieved methodology notes
- Direct trade recommendations and guaranteed-outcome language
- Presence of assumptions or limitations

If commentary fails validation, the workflow permits one regeneration attempt and validates the revised output again. It does not retry indefinitely.

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

For LLM commentary, create a local `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
```

Do not commit `.env` or API keys. The credit-risk demo uses deterministic commentary and does not require an API key.

## Run

Run the complete test suite:

```bash
pytest -q
```

Run the market-risk workflow demo:

```bash
python examples/run_llm_agent_demo.py
```

Run the deterministic counterparty exposure / PFE demo:

```bash
python examples/run_credit_risk_demo.py
```

The demos display registered tools, the planned workflow, the runtime execution trace, analytical results, retrieved methodology, commentary, and validation status.

## Example Output Snapshot

Representative market-risk demo output:

- Annualized volatility: 26.71%
- 95% historical VaR: 2.32%
- 95% Expected Shortfall: 3.47%
- Maximum drawdown: 23.77%
- Stress scenario loss: 22.50%
- Validation: PASSED

Representative credit-risk / PFE demo output:

- Peak 95% PFE: 2,100,000
- Peak 99% PFE: 2,600,000
- EPE: 1,080,000
- Largest netting set: NS-001
- Validation: PASSED

## Limitations

- Planning and routing are deterministic rather than LLM-directed.
- Market risk is historical and focused on simple equity/ETF portfolios.
- Only historical VaR is implemented; no parametric or Monte Carlo VaR is available.
- Concentration observations are based on weights and ticker composition, not a formal factor model.
- Stress testing uses deterministic ticker proxies rather than full revaluation.
- PFE analytics consume supplied profiles rather than generating exposures from trades.
- XVA, PD/LGD/EAD, SIMM, and RegIM are not implemented.
- Methodology retrieval is local and keyword-based, without embeddings or vector search.
- Tool execution is synchronous and in-process, with no durable workflow state.
- LLM commentary quality depends on the configured model despite deterministic validation controls.

## Future Extensions

- Improve retrieval with embeddings, vector search, and stronger ranking.
- Add formal factor exposure and richer scenario or full-revaluation stress models.
- Generate exposure profiles from pricing simulations and extend toward XVA analytics.
- Add durable execution state, richer observability, and PDF/HTML report export.

## Disclaimer

FinRisk Agent is for analytical demonstration only and does not constitute investment advice.
