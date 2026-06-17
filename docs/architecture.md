# RiskFlow Agent Architecture

## Project Goal

RiskFlow Agent is a risk analytics application that combines LLM-assisted planning with deterministic Python calculations and controlled commentary. It accepts an analysis instruction, structured or natural-language portfolio input, and optional calculation configuration. The system proposes a workflow, validates the proposed tool sequence, executes deterministic analytics, retrieves local methodology notes, generates commentary, and validates the resulting report.

The calculations remain authoritative. The LLM may plan and explain, but it does not calculate or replace risk metrics.

## High-Level Design

RiskFlow Agent separates planning, deterministic workflow orchestration, domain analytics, and validation. The primary planner can use an LLM to propose registered tools from the user query and input context, while the rule planner remains the fallback/offline mode. Validated plans are executed sequentially through a lightweight approved-plan executor when their tools have explicit context adapters. Conservative deterministic route templates remain as a fallback for mappings that are not yet directly executable. Local methodology retrieval grounds commentary, and deterministic validators enforce numerical and policy guardrails. A presentation layer produces a clean user report while retaining raw analytics, validation results, and an auditable execution trace.

**LLM plans. Python tools calculate. Validators gate execution and output.**

## Why This Is an Agentic Workflow

The application is not a single prompt or linear script. `src/workflow/` provides an explicit planning and execution layer:

- `llm_planner.py` asks an LLM to propose a JSON-like workflow plan from the user query, input schemas, supported modules, and registered tools.
- `autonomous_planner.py` provides the deterministic rule planner used for fallback/offline mode.
- `plan_executor.py` executes approved registered tool steps sequentially through explicit context adapters.
- `context.py` stores typed workflow state passed between approved-plan execution steps.
- `planner.py` builds deterministic route plans, detects the loaded-data route, and infers active modules for the execution engine.
- `engine.py` retains deterministic route execution used by lower-level workflow APIs.
- `execution.py` invokes tools through `ToolExecutor` and records concise runtime trace entries.
- `types.py` defines plans, steps, route results, presentation results, and execution trace records.
- `presentation.py` combines route results into a clean user report while preserving trace, validation, and raw outputs.

Each capability is registered as a named tool. Planned steps and actual tool calls are separately inspectable through `WorkflowPlan` and `execution_trace`. Commentary is validated after generation, with one controlled regeneration attempt when validation fails.

LLM-proposed plans cannot bypass validation. `plan_validator.py` rejects unknown tools, unsupported regulatory capital/margin tools, and misordered plans before execution. The LLM is not allowed to calculate VaR, Expected Shortfall, PFE, SA-CCR, SIMM, RegIM, capital, margin, or any risk number.

The approved plan is preferably executed step by step by `ApprovedPlanExecutor`. If a step sequence is validated but not yet supported by direct context-based execution, the workflow falls back to constrained deterministic routes rather than executing an unrestricted dynamic DAG. The agent result includes an `orchestration_trace` with `execution_mode`, `proposed_plan_steps`, `approved_plan_steps`, `selected_route`, `executed_tools`, `skipped_or_unsupported_tools`, `validation_status`, and `route_mapping_note`. This makes the current control model explicit: the planner proposes scope, the validator approves supported tools, and the executor either runs approved steps sequentially or records a deterministic fallback.

The recommended project entry point is `examples/run_riskflow_agent_demo.py`. It is a thin wrapper around `src.workflow.run_agent_workflow()`, which supports `planner_mode="auto" | "llm" | "rule"`. In `auto` mode the workflow uses the LLM planner when available and otherwise falls back clearly to the rule planner. Older demos are archived under `examples/legacy/`.

## Input Model

The lower-level deterministic route API is `run_risk_workflow()` from `src.workflow`. It accepts:

- `query`: the natural-language analysis instruction.
- `data_file`: an optional CSV, XLSX, or JSON input file.
- `config_file`: an optional JSON risk configuration file.

`portfolio_file` remains a backward-compatible alias for `data_file`; supplying both raises an error.

Without `data_file`, the query is parsed for market portfolio tickers and weights. With `data_file`, `src/data/portfolio_loader.py` detects market portfolio and exposure profile schemas. Sensitivity files are loaded separately through `src/sensitivity_risk/loader.py`.

- Market portfolio: `ticker`, `weight`.
- Counterparty exposure profile: `netting_set`, `time_years`, `expected_exposure`, `pfe_95`, with optional `pfe_99`, `currency`, and `counterparty`.

`src/core/risk_config.py` supplies defaults or loads configured dates, return assumptions, VaR settings, enabled metrics, reporting options, optional deterministic stress scenarios, and credit limits.

## Workflow Engine And Routing

The workflow begins by resolving the input source and constructing a plan. Structured files are loaded through registered data-loading tools. The planner then routes by requested modules and available schemas.

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

Sensitivity Risk execution is:

```text
load sensitivity file
  -> validate sensitivity file
  -> aggregate Greeks
```

The sensitivity workflow consumes precomputed delta, gamma, vega, and theta values from an upstream pricing or risk engine. It does not calculate pricing-model Greeks.

Regulatory Readiness execution is:

```text
assess regulatory readiness
  -> validate regulatory readiness report
```

When sensitivity data is available, SIMM / RegIM readiness recognizes supplied fields such as risk class, risk factor, bucket, Greeks, and currency. Missing inputs still include items outside the current scope, such as product class, margin class, risk-weight mappings, correlation parameters, and margin currency.

The primary agent workflow can combine Market Risk, Credit Risk, Sensitivity Risk, and Regulatory Readiness sections and returns `AgentWorkflowResult`:

- `user_report`: presentation-ready final risk summary.
- `execution_trace`: serialized, auditable tool and workflow steps.
- `validation_result`: combined domain validation outcomes.
- `raw_outputs`: complete underlying route results for further inspection.

The presentation layer keeps internal workflow evidence available without printing every raw intermediate artifact alongside the user-facing report.

## Shared Tool Infrastructure

The canonical implementation is organized into the following packages:

- `src/core/`: tool registry, tool execution, and risk configuration.
- `src/data/`: portfolio loading and parsing, portfolio calculations, and market data access.
- `src/workflow/`: planning, routing, orchestration, execution tracing, and workflow result types.
- `src/validators/`: market, stress, credit/PFE, regulatory, methodology, and commentary guardrail validation.
- `src/market_risk/`: historical market-risk metrics, report assembly, and deterministic stress testing.
- `src/credit_risk/`: counterparty exposure and PFE summary analytics.
- `src/sensitivity_risk/`: supplied Greeks validation and aggregation.
- `src/regulatory_risk/`: SA-CCR and SIMM / RegIM readiness screening.
- `src/knowledge/`: local methodology loading and keyword-based retrieval.
- `src/reporting/`: LLM and fallback commentary generation plus report formatting utilities.

Within `src/core/`:

- `tool_registry.py` defines `RiskTool` metadata and registered handlers grouped as `shared`, `market_risk`, `credit_risk`, or `regulatory_risk`.
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

The registry includes input adapters, market calculations, credit/PFE calculations, sensitivity aggregation, regulatory readiness, methodology retrieval, commentary generation/regeneration, and report validation. It is an in-process Python registry, not a remote tool protocol or OpenAI tool-calling implementation.

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

## Sensitivity Risk Module

`src/sensitivity_risk/` consumes precomputed sensitivities from an upstream pricing or risk engine:

- `loader.py`: loads sensitivity CSV files with portfolio, trade, risk-factor, Greeks, and currency fields.
- `validator.py`: validates required schema and supplied records.
- `analytics.py`: aggregates delta, gamma, vega, and theta; computes concentration by risk class, bucket, and risk factor; and reports currency consistency warnings.

The module does not calculate Black-Scholes Greeks, Monte Carlo Greeks, or any pricing-model sensitivities.

## Regulatory Risk Module

`src/regulatory_risk/readiness.py` screens whether available inputs are sufficient for downstream SA-CCR and SIMM / RegIM workflows. It reports structured readiness status, available inputs, and missing inputs.

For SA-CCR, the readiness screen distinguishes portfolio-level metadata, such as portfolio notional and asset class, from missing trade-level regulatory inputs, such as trade type, trade notional, maturity, supervisory category, netting agreement details, and supervisory factor/category mapping.

For SIMM / RegIM, the readiness screen can use supplied sensitivity fields from the Greeks workflow, while still reporting missing model and regulatory inputs such as product class, margin class, risk-weight mapping, correlation parameters, and margin currency.

It does not calculate SA-CCR EAD, SA-CCR capital, SIMM margin, or RegIM margin.

The full demo includes this readiness screen as a third high-level section and validates that no regulatory capital or margin number is fabricated when required inputs are missing.

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
- `regulatory.py`: regulatory readiness status, available/missing input reporting, and no fabricated capital or margin numbers.
- `guardrails.py`: direct recommendation, assumptions/limitations, and guaranteed-outcome checks.
- `methodology.py`: cited-note grounding.
- `common.py`: shared validation result types and helpers.

Validation preserves deterministic check ordering and returns structured checks, errors, and warnings. Optional analytics are validated only when corresponding results exist. A failed first validation triggers at most one commentary regeneration and one second validation; there is no unbounded retry loop.

## Presentation And Trace Serialization

`src/workflow/presentation.py` converts the market and credit `WorkflowResult` objects into an `AgentRunResult`. The primary user-facing demo is `examples/run_riskflow_agent_demo.py`, which calls `run_agent_workflow()` and supports `--planner auto|llm|rule`, `--scenario full|market|credit|regulatory`, `--query`, `--show-plan`, and `--trace-file`. Passing `--trace-file` writes the internal `execution_trace` to JSON while stdout remains presentation-oriented.

Failure behavior is demonstrated separately under `examples/failure_cases/`:

- `run_invalid_portfolio_demo.py` shows portfolio validation preventing risk calculation and can save the partial failed trace with `--trace-file`.
- `run_report_validation_failure_demo.py` passes intentionally inconsistent commentary to the report validator and displays its errors and warnings.

These presentation scripts call existing workflow and validation APIs; they do not duplicate analytics or orchestration logic. Archived module-level examples remain under `examples/legacy/` for historical reference.

## Current Limitations

- LLM planning is constrained to proposing registered tools and depends on API availability; rule planning remains the offline fallback.
- Market risk relies on historical price data and currently supports equity/ETF-style holdings.
- VaR uses the historical method; no parametric or Monte Carlo VaR is implemented.
- Stress testing uses simple ticker-specific proxy shocks, not a formal factor or full revaluation model.
- PFE analytics summarize supplied exposure profiles rather than producing them from a pricing engine or Monte Carlo path generation.
- Sensitivity analytics consume supplied Greeks rather than calculating pricing-model Greeks.
- No real SA-CCR EAD calculation is implemented.
- No SIMM or RegIM margin calculation is implemented.
- No XVA valuation, PD/LGD/EAD modeling, or regulatory capital stack is implemented.
- Methodology retrieval is keyword-based and local.
- LLM output quality depends on the configured model, although deterministic validation constrains key numerical and policy risks.
- Tool execution is synchronous and in-process; there is no distributed execution, persistence, or durable workflow state.

## Planned Cleanup / Future Architecture Direction

Possible cleanup and extensions, not part of the current architecture, include:

- Strengthen methodology retrieval with embeddings, vector search, or improved ranking while retaining source grounding.
- Expand risk analytics with formal factor exposure, richer stress and revaluation models, pricing-engine-derived exposure profiles, and XVA extensions.
- Add richer regulatory schemas and optional SA-CCR/SIMM calculations in a future phase; these calculations are not part of the current implementation.

These items describe direction only. The implemented system remains the deterministic, in-process workflow documented above.
