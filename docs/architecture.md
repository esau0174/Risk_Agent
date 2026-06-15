# RiskFlow Agent Architecture

## Project Goal

RiskFlow Agent is a risk analytics application that combines deterministic Python calculations with controlled LLM commentary. It accepts an analysis instruction, structured or natural-language portfolio input, and optional calculation configuration. The system produces market-risk or counterparty-exposure results, retrieves local methodology notes, generates commentary, and validates the resulting report.

The calculations remain authoritative. The LLM explains calculated results; it does not calculate or replace them.

## High-Level Design

RiskFlow Agent separates deterministic workflow orchestration from domain analytics. Shared tools route structured inputs into market-risk or credit-risk modules, local methodology retrieval grounds commentary, and deterministic validators enforce numerical and policy guardrails. A presentation layer produces a clean user report while retaining raw analytics, validation results, and an auditable execution trace.

## Why This Is an Agentic Workflow

The application is not a single prompt or linear script. `src/workflow/` provides an explicit planning and execution layer:

- `planner.py` builds deterministic workflow plans, detects the loaded-data route, and infers active modules.
- `engine.py` orchestrates the selected route and owns the high-level execution sequence.
- `execution.py` invokes tools through `ToolExecutor` and records concise runtime trace entries.
- `types.py` defines plans, steps, route results, presentation results, and execution trace records.
- `presentation.py` combines route results into a clean user report while preserving trace, validation, and raw outputs.

Each capability is registered as a named tool. Planned steps and actual tool calls are separately inspectable through `WorkflowPlan` and `execution_trace`. Commentary is validated after generation, with one controlled regeneration attempt when validation fails.

Planning is deterministic. The current workflow does not use an LLM to choose tools or dynamically create execution paths.

## Input Model

The primary entry point is `run_risk_workflow()` from `src.workflow`. It accepts:

- `query`: the natural-language analysis instruction.
- `data_file`: an optional CSV, XLSX, or JSON input file.
- `config_file`: an optional JSON risk configuration file.

`portfolio_file` remains a backward-compatible alias for `data_file`; supplying both raises an error.

Without `data_file`, the query is parsed for market portfolio tickers and weights. With `data_file`, `src/data/portfolio_loader.py` detects one of two supported schemas:

- Market portfolio: `ticker`, `weight`.
- Counterparty exposure profile: `netting_set`, `time_years`, `expected_exposure`, `pfe_95`, with optional `pfe_99`, `currency`, and `counterparty`.

`src/core/risk_config.py` supplies defaults or loads configured dates, return assumptions, VaR settings, enabled metrics, reporting options, and optional deterministic stress scenarios.

## Workflow Engine And Routing

The workflow begins by resolving the input source and constructing a plan. Structured files are loaded through the registered `load_portfolio_file` tool. The planner then routes by the returned data type.

Market-risk execution is:

```text
load or parse portfolio
  -> validate portfolio
  -> load risk configuration
  -> calculate risk metrics
  -> optionally run configured stress scenarios
  -> retrieve methodology
  -> generate commentary
  -> validate report
```

Credit Risk execution is:

```text
load exposure profile
  -> load risk configuration
  -> calculate PFE metrics
  -> retrieve PFE methodology
  -> generate commentary
  -> validate report
```

The market route skips PFE analytics. The credit route skips portfolio-weight validation, historical market-risk calculations, and market stress testing. Both routes return `WorkflowResult` and use the same orchestration engine, execution tracing, commentary generation, and validation gate.

The combined presentation workflow runs both routes and returns `AgentRunResult`:

- `user_report`: presentation-ready final risk summary.
- `execution_trace`: serialized, auditable tool and workflow steps.
- `validation_result`: combined market and credit validation outcomes.
- `raw_outputs`: complete underlying route results for further inspection.

This keeps internal workflow evidence available without printing it alongside the user-facing report.

## Shared Tool Infrastructure

The canonical implementation is organized into eight packages:

- `src/core/`: tool registry, tool execution, and risk configuration.
- `src/data/`: portfolio loading and parsing, portfolio calculations, and market data access.
- `src/workflow/`: planning, routing, orchestration, execution tracing, and workflow result types.
- `src/validators/`: market, stress, credit/PFE, methodology, and commentary guardrail validation.
- `src/market_risk/`: historical market-risk metrics, report assembly, and deterministic stress testing.
- `src/credit_risk/`: counterparty exposure and PFE summary analytics.
- `src/knowledge/`: local methodology loading and keyword-based retrieval.
- `src/reporting/`: LLM and fallback commentary generation plus report formatting utilities.

Within `src/core/`:

- `tool_registry.py` defines `RiskTool` metadata and registered handlers grouped as `shared`, `market_risk`, or `credit_risk`.
- `tool_executor.py` resolves tools by name and returns structured `ToolResult` objects with status, output, error, and metadata.
- `risk_config.py` loads and validates calculation configuration.

Supporting shared capabilities are separated by responsibility:

- `src/data/portfolio_loader.py` loads and validates supported structured data schemas.
- `src/data/portfolio_parser.py` parses natural-language market portfolios.
- `src/data/portfolio.py` validates weights and calculates asset, portfolio, and cumulative returns.
- `src/data/market_data.py` loads historical market data.
- `src/knowledge/rag.py` loads and ranks local methodology documents.
- `src/reporting/agent.py` builds prompts and produces LLM or deterministic fallback commentary.
- `src/reporting/report_generator.py` contains report formatting utilities.

The registry includes input adapters, market and credit calculations, methodology retrieval, commentary generation/regeneration, and report validation. It is an in-process Python registry, not a remote tool protocol or OpenAI tool-calling implementation.

## Market Risk Module

`src/market_risk/` contains the canonical market-risk implementation:

- `risk_metrics.py`: annualized volatility, historical VaR, Expected Shortfall, maximum drawdown, and correlation matrix.
- `risk_report.py`: market-data retrieval, return calculations, configured metric calculation, and report assembly.
- `stress_testing.py`: deterministic ticker-based equity, technology, and rates proxy scenarios.

Market prices are downloaded by `src/data/market_data.py`; portfolio return calculations and weight validation live in `src/data/portfolio.py`.

## Credit Risk Module

`src/credit_risk/counterparty_risk.py` calculates summary analytics from a supplied exposure profile:

- Peak PFE at 95% and, when supplied, 99%.
- Time of peak PFE.
- Average expected exposure / EPE.
- Maximum expected exposure.
- Expected exposure totals by netting set.
- Largest netting set by peak PFE.
- Optional credit limit utilization for the largest netting set.

The module consumes supplied profile data; it does not generate exposures from trade pricing or Monte Carlo simulation.
When `credit_limits` are configured by netting set, utilization is calculated as Peak 95% PFE divided by the configured limit. Limit status values are `PASSED`, `WARNING`, or `BREACHED`.

## Methodology Retrieval

`src/knowledge/rag.py` loads Markdown notes from `docs/` and applies deterministic keyword scoring. Market workflows build a query from the user instruction and calculated report. PFE workflows restrict retrieval to counterparty-relevant note titles and use PFE, EPE, exposure-profile, and netting-set terms.

The current retrieval layer uses no embeddings, vector database, external web source, or learned reranker. Retrieved note titles and content are passed to commentary generation and later checked by methodology-grounding validation.

## Commentary Generation

`src/reporting/agent.py` generates analyst-style commentary from calculated outputs, portfolio composition, stress results, PFE results, and retrieved methodology notes. When LLM use is disabled, deterministic fallback commentary supports offline execution and tests.

The prompt instructs the model to use only supplied calculations, avoid invented figures and recommendations, state assumptions and limitations, and include an investment-advice disclaimer. If report validation fails, the workflow can invoke a registered regeneration tool once with the validation findings.

## Validation And Guardrails

`report_validator.py` is the public validation facade. Domain-specific checks live in `src/validators/`:

- `market.py`: portfolio and market-metric consistency.
- `stress.py`: stress-result consistency and missing-analysis warnings.
- `credit.py`: PFE, EPE, and credit limit utilization consistency.
- `guardrails.py`: direct recommendation, assumptions/limitations, and guaranteed-outcome checks.
- `methodology.py`: cited-note grounding.
- `common.py`: shared validation result types and helpers.

Validation preserves deterministic check ordering and returns structured checks, errors, and warnings. Optional analytics are validated only when corresponding results exist. A failed first validation triggers at most one commentary regeneration and one second validation; there is no unbounded retry loop.

## Presentation And Trace Serialization

`src/workflow/presentation.py` converts the market and credit `WorkflowResult` objects into an `AgentRunResult`. The full demo prints only `user_report` by default. Passing `--trace-file` to `examples/run_full_risk_agent_demo.py` writes the internal `execution_trace` to `logs/full_demo_trace.json`, or to a supplied path.

Failure behavior is demonstrated separately under `examples/failure_cases/`:

- `run_invalid_portfolio_demo.py` shows portfolio validation preventing risk calculation and can save the partial failed trace with `--trace-file`.
- `run_report_validation_failure_demo.py` passes intentionally inconsistent commentary to the report validator and displays its errors and warnings.

These presentation scripts call existing workflow and validation APIs; they do not duplicate analytics or orchestration logic.

## Current Limitations

- Workflow planning and routing are deterministic, not LLM-directed.
- Market risk relies on historical price data and currently supports equity/ETF-style holdings.
- VaR uses the historical method; no parametric or Monte Carlo VaR is implemented.
- Stress testing uses simple ticker-specific proxy shocks, not a formal factor or full revaluation model.
- PFE analytics summarize supplied exposure profiles rather than producing them from a pricing engine.
- No XVA, PD/LGD/EAD, SIMM, or RegIM calculations are implemented.
- Methodology retrieval is keyword-based and local.
- LLM output quality depends on the configured model, although deterministic validation constrains key numerical and policy risks.
- Tool execution is synchronous and in-process; there is no distributed execution, persistence, or durable workflow state.

## Planned Cleanup / Future Architecture Direction

Possible cleanup and extensions, not part of the current architecture, include:

- Strengthen methodology retrieval with embeddings, vector search, or improved ranking while retaining source grounding.
- Expand risk analytics with formal factor exposure, richer stress and revaluation models, pricing-engine-derived exposure profiles, and XVA extensions.
- Add SA-CCR exposure and capital calculations; SA-CCR is not part of the current implementation.

These items describe direction only. The implemented system remains the deterministic, in-process workflow documented above.
