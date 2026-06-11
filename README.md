# FinRisk Agent: LLM-Powered Portfolio Risk Analyst

FinRisk Agent is a financial risk copilot that parses natural-language portfolio queries, computes risk metrics using Python tools, retrieves local methodology notes with simple RAG, and generates analyst-style risk commentary.

The project is designed to demonstrate practical financial risk analytics, clean Python engineering, lightweight retrieval-augmented generation, and guardrails against unsupported investment advice.

## Key Features

- Natural language portfolio parsing
- Historical market data download
- Portfolio return calculation
- Annualized volatility
- Historical VaR
- Expected Shortfall
- Maximum drawdown
- Correlation matrix
- LLM-generated risk commentary
- Local RAG methodology retrieval
- Finance-aware concentration analysis
- Guardrails against investment advice

## Current Status

The project currently includes the Python risk analytics backend, rule-based portfolio parsing, explicit agentic workflow orchestration, a minimal OpenAI-powered commentary agent, simple local RAG over methodology notes, and a Streamlit UI. Vector search and formal tool-calling workflows are planned future improvements.

## Architecture

```text
User query
  -> portfolio parser
  -> risk report engine
  -> local RAG retrieval
  -> LLM commentary generation
```

At a high level, the rule-based parser extracts tickers and weights from plain English. The risk report engine downloads historical prices, calculates returns, and computes risk metrics. The local RAG layer retrieves relevant methodology notes from `docs/`. The LLM then generates commentary grounded in the calculated report and retrieved methodology snippets.

## Agentic Workflow Orchestration

FinRisk Agent now uses an explicit multi-step workflow that makes planning and execution traceable:

```text
natural-language query
  -> portfolio parsing
  -> input validation
  -> risk metric calculation
  -> methodology retrieval
  -> commentary generation
```

The workflow layer records each step, status, and output summary, making the agent behavior easier to test, audit, and extend.

### Tool Registry

The workflow exposes deterministic risk analytics capabilities as registered tools. The current registry includes portfolio parsing, input validation, risk metric calculation, methodology retrieval, commentary generation, and report validation. This keeps tool availability explicit, documented, and inspectable without changing the underlying risk calculation logic.

### Report Validation Gate

After commentary generation, the workflow runs deterministic validation checks before accepting the final report. The validation gate checks risk metric sign conventions, Expected Shortfall versus VaR consistency, portfolio weight consistency, unsupported investment advice, assumptions and limitations, and methodology grounding against retrieved notes.

## Project Structure

```text
Risk_Agent/
|-- docs/
|   |-- concentration_risk.md
|   |-- expected_shortfall.md
|   |-- historical_var.md
|   |-- max_drawdown.md
|   `-- model_limitations.md
|-- examples/
|   |-- run_llm_agent_demo.py
|   |-- run_phase1_demo.py
|   `-- run_text_query_demo.py
|-- src/
|   |-- agent.py
|   |-- market_data.py
|   |-- portfolio.py
|   |-- portfolio_parser.py
|   |-- rag.py
|   |-- report_validator.py
|   |-- risk_metrics.py
|   |-- risk_report.py
|   |-- stress_testing.py
|   |-- tool_registry.py
|   `-- workflow.py
|-- tests/
|   |-- test_agent.py
|   |-- test_portfolio.py
|   |-- test_portfolio_parser.py
|   |-- test_rag.py
|   |-- test_report_validator.py
|   |-- test_risk_metrics.py
|   |-- test_risk_report.py
|   |-- test_tool_registry.py
|   `-- test_workflow.py
|-- app.py
|-- .env.example
|-- pytest.ini
|-- requirements.txt
`-- README.md
```

## Installation

Requires Python 3.10+.

Install the project dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

Create a local `.env` file with your OpenAI API key:

```text
OPENAI_API_KEY=your_api_key_here
```

Do not commit `.env` or any real API keys to version control. Use `.env.example` as the template for required environment variables.

## How To Run

Run the test suite:

```bash
pytest
```

Run the Phase 1 risk analytics demo:

```bash
python examples/run_phase1_demo.py
```

Run the rule-based natural language query demo:

```bash
python examples/run_text_query_demo.py
```

Run the LLM agent demo:

```bash
python examples/run_llm_agent_demo.py
```

The LLM demo requires `OPENAI_API_KEY` to be set. If no key is available, the demo exits without calling the OpenAI API.

## Example Query

```text
Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT. Focus on downside risk and concentration risk.
```

## Example Output Summary

For a query like the one above, FinRisk Agent parses the portfolio into tickers and weights, downloads historical adjusted close prices, and calculates metrics such as:

- Annualized volatility: 26.62%
- 95% historical VaR: 2.31%
- 95% Expected Shortfall: 3.44%
- Maximum drawdown: 23.77%
- Latest cumulative return
- Correlation matrix

The generated commentary highlights downside risk using VaR and Expected Shortfall, discusses realized drawdown, identifies the largest single position, and flags overlapping growth / technology / AI-related exposure where relevant. It also notes that bond exposure such as TLT may diversify equity risk, but hedge effectiveness depends on the rate and inflation regime.

## Methodology Notes

Local methodology notes live in `docs/` and are retrieved with deterministic keyword-based RAG:

- Historical VaR
- Expected Shortfall
- Maximum Drawdown
- Concentration Risk
- Model Limitations

The LLM commentary is instructed to cite only retrieved local methodology titles, such as `Methodology reference: Historical VaR`.

## Limitations

- Uses historical data only
- Focused on simple equity and ETF portfolios
- No formal factor model yet
- Does not provide personalized investment advice
- RAG is keyword-based for now, not embedding-based

## Future Improvements

- Enhanced Streamlit workflow UI
- Formal OpenAI tool/function calling workflow
- Chroma or FAISS vector search
- Factor exposure model
- Stress scenario library
- PDF/HTML report export

## Disclaimer

FinRisk Agent provides risk analytics, methodology context, and explanatory commentary. It does not provide personalized financial, investment, tax, or legal advice.
