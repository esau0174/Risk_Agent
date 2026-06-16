# RiskFlow Agent

Controlled LLM-assisted risk workflow agent for Market Risk, Credit Risk / PFE, and regulatory-readiness analysis.

**LLM plans. Python tools calculate. Validators gate execution and output.**

RiskFlow Agent is an interview-grade AI + Finance engineering demo. It shows how a natural-language request can be converted into an auditable, validated risk workflow without allowing an LLM to invent metrics, execute arbitrary tools, or fabricate regulatory capital numbers.

## Why This Is An Agent

This project is not just a portfolio VaR script wrapped in a chatbot. It separates planning, execution, analytics, reporting, and validation:

- The planner proposes a workflow from the user query, input context, and registered tools.
- The plan validator rejects unknown tools, unsupported regulatory capital/margin tools, and misordered workflows.
- The tool registry exposes explicit deterministic capabilities for shared infrastructure, market risk, credit risk, and regulatory readiness.
- The approved-plan executor runs validated tool steps sequentially when the mapping is supported.
- A deterministic route fallback remains available for conservative, reproducible execution.
- Risk metrics are calculated by Python modules, not by the LLM.
- Commentary is grounded in calculated outputs and local methodology notes.
- Report validators check numerical consistency, guardrails, and unsupported advice.
- Execution trace and raw outputs remain available for audit.

## Architecture Overview

```text
User query + input context
        |
        v
LLM planner or rule fallback planner
        |
        v
Deterministic plan validator
        |
        v
Tool registry -> ToolExecutor
        |
        v
Approved-plan executor
        |
        v
Deterministic risk tools
        |
        v
Methodology retrieval
        |
        v
Commentary generation
        |
        v
Report validation / guardrails
        |
        v
User report + execution trace + validation result + raw outputs
```

Canonical package structure:

- `src/core/`: tool registry, tool executor, risk configuration.
- `src/data/`: portfolio parsing, file loading, portfolio utilities, market data.
- `src/workflow/`: LLM planner, rule fallback planner, plan validator, approved-plan executor, engine, presentation types.
- `src/market_risk/`: volatility, historical VaR, Expected Shortfall, drawdown, stress testing.
- `src/credit_risk/`: counterparty exposure profile and PFE analytics.
- `src/regulatory_risk/`: SA-CCR and SIMM / RegIM readiness screening.
- `src/knowledge/`: local methodology retrieval.
- `src/reporting/`: commentary generation and report formatting utilities.
- `src/validators/`: market, stress, credit/PFE, regulatory, methodology, and guardrail checks.

See [docs/architecture.md](docs/architecture.md) for the detailed implementation architecture.

## What The Demo Supports

**Market Risk**

- Annualized volatility
- Historical VaR
- Expected Shortfall
- Maximum drawdown
- Deterministic stress scenario loss
- Concentration observations from weights and ticker composition

**Credit Risk / PFE**

- Exposure profile validation
- Peak PFE
- EPE / average expected exposure
- Netting set concentration
- Optional limit utilization against configured netting-set limits

**Regulatory Readiness**

- SA-CCR readiness screening
- SIMM / RegIM readiness screening
- Missing-input reporting
- Explicit guardrail that no regulatory capital or margin number is generated from insufficient inputs

**Guardrails And Failure Demos**

- Invalid portfolio rejection before risk calculation
- Unsupported tool rejection before execution
- Commentary/report validation failure demo
- Direct recommendation and fabricated metric guardrails

## Quickstart

Install and test:

```bash
pip install -e ".[dev]"
pytest -q
```

Run the primary deterministic/offline demo:

```bash
python examples/run_riskflow_agent_demo.py --planner rule --scenario full --show-plan
```

Run the LLM planner path when an API key is configured:

```bash
python examples/run_riskflow_agent_demo.py --planner llm --query "Check SA-CCR and SIMM readiness only." --show-plan
```

Run failure-case demos:

```bash
python examples/failure_cases/run_invalid_portfolio_demo.py
python examples/failure_cases/run_report_validation_failure_demo.py
```

## Optional LLM Configuration

The project works offline with `--planner rule`. In `--planner auto`, RiskFlow Agent uses the LLM planner when available and otherwise falls back clearly to the deterministic rule planner.

For a project-root `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
# Optional, only for compatible gateways or custom endpoints:
# OPENAI_BASE_URL=https://your-compatible-endpoint/v1
```

For a temporary PowerShell session:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
$env:OPENAI_MODEL="gpt-4o-mini"
# Optional:
# $env:OPENAI_BASE_URL="https://your-compatible-endpoint/v1"
```

Do not commit API keys. `.env` is ignored by `.gitignore`.

## Primary Demo

The official entry point is:

```bash
python examples/run_riskflow_agent_demo.py
```

Useful flags:

- `--planner auto | llm | rule`
- `--scenario full | market | credit | regulatory`
- `--query "custom request"`
- `--show-plan`
- `--trace-file`

The default full scenario uses sample market and credit inputs under `examples/` and a fixed market data window from `2023-01-01` through `2024-12-31` via `examples/sample_risk_config.json`.

Older module-level demos are archived under `examples/legacy/` for reference. They are not the main project entry point.

## Structured Output

The workflow returns a structured result containing:

- `user_report`: clean user-facing report.
- `execution_trace`: auditable internal workflow/tool trace.
- `validation_result`: deterministic guardrail checks, errors, and warnings.
- `raw_outputs`: underlying analytics results.
- `orchestration_trace`: plan and execution summary with `execution_mode`, `proposed_plan_steps`, `approved_plan_steps`, `selected_route`, `executed_tools`, `skipped_or_unsupported_tools`, `validation_status`, and `route_mapping_note`.

This separation keeps stdout readable while preserving enough detail for inspection, testing, and audit-style review.

The preferred execution path is a lightweight approved-plan executor that runs validated registered tools sequentially with explicit context adapters. When a validated plan cannot yet be mapped directly, RiskFlow Agent falls back to constrained deterministic routes such as `market`, `credit`, `regulatory`, or `full` and records that fallback in the orchestration trace. RiskFlow Agent is not a fully dynamic DAG executor; this design is deliberate for financial risk control, reproducibility, and easier validation.

## Interview Framing

When discussing the project, frame it as a controlled agentic risk workflow:

- The LLM is used for workflow planning and analyst-style explanation, not for risk math.
- Python tools own deterministic market-risk, credit-risk/PFE, and regulatory-readiness calculations.
- The plan validator is the execution gate: unsupported tools and invalid ordering do not run.
- The approved-plan executor is intentionally lightweight: supported tool steps execute sequentially, while unsupported mappings fall back to audited deterministic routes.
- Report validators are the output gate: commentary must match calculated metrics and stay within guardrails.
- Execution trace makes the workflow inspectable, which is critical for risk analytics governance.
- Regulatory work is intentionally readiness-focused; the project does not pretend to implement SA-CCR or SIMM capital.

This aligns with AI-enabled quant developer work: agentic coding, tool orchestration, controlled autonomy, explainability, and financial risk analytics.

## Limitations / Intentional Scope Boundaries

- No production pricing engine.
- No Monte Carlo path generation.
- No real SA-CCR capital calculation.
- No real SIMM / RegIM margin calculation.
- No XVA, PD/LGD/EAD, or regulatory capital stack.
- No production deployment, persistence, or distributed execution.
- No unrestricted autonomous tool execution.
- Market risk focuses on historical equity/ETF-style portfolios.
- Methodology retrieval is local and keyword-based, not vector-based.

## Next Extensions

- Typed execution graph compiled from the approved plan.
- Dollar VaR / ES reporting with portfolio notional.
- Richer regulatory input schema and readiness coverage.
- Optional vector-based methodology retrieval.
- More formal factor exposure and stress scenario libraries.
- Report export to PDF or HTML.

## Disclaimer

RiskFlow Agent is for analytical demonstration only and does not constitute investment advice.
