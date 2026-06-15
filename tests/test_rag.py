from src.rag import load_methodology_docs, retrieve_relevant_methodology


REQUIRED_MINI_SPEC_SECTIONS = (
    "## Purpose",
    "## Inputs",
    "## Calculation",
    "## Outputs",
    "## Assumptions",
    "## Limitations",
    "## Validation Rules",
    "## Related Tools",
)


def test_load_methodology_docs_reads_markdown_titles(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "historical_var.md").write_text(
        "# Historical VaR\n\nValue at Risk methodology.",
        encoding="utf-8",
    )
    (docs_dir / "model_limitations.md").write_text(
        "Historical data limitations.",
        encoding="utf-8",
    )

    docs = load_methodology_docs(str(docs_dir))

    assert [doc["title"] for doc in docs] == ["Historical VaR", "Model Limitations"]
    assert docs[0]["path"].endswith("historical_var.md")
    assert "Value at Risk" in docs[0]["content"]


def test_load_methodology_docs_excludes_architecture_document(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "historical_var.md").write_text(
        "# Historical VaR\n\nValue at Risk methodology.",
        encoding="utf-8",
    )
    (docs_dir / "architecture.md").write_text(
        "# System Architecture\n\nApplication structure.",
        encoding="utf-8",
    )

    docs = load_methodology_docs(str(docs_dir))

    assert [doc["title"] for doc in docs] == ["Historical VaR"]


def test_retrieve_relevant_methodology_scores_keyword_matches():
    docs = [
        {
            "title": "Historical VaR",
            "path": "docs/historical_var.md",
            "content": "VaR estimates a percentile loss threshold.",
        },
        {
            "title": "Concentration Risk",
            "path": "docs/concentration_risk.md",
            "content": "Concentration can include overlapping technology exposure.",
        },
        {
            "title": "Maximum Drawdown",
            "path": "docs/max_drawdown.md",
            "content": "Drawdown is a peak-to-trough decline.",
        },
    ]

    results = retrieve_relevant_methodology(
        "Explain VaR and technology concentration risk",
        docs,
        top_k=2,
    )

    assert [result["title"] for result in results] == [
        "Concentration Risk",
        "Historical VaR",
    ]
    assert all("score" in result for result in results)


def test_retrieve_relevant_methodology_returns_empty_list_for_no_matches():
    docs = [
        {
            "title": "Maximum Drawdown",
            "path": "docs/max_drawdown.md",
            "content": "Peak-to-trough decline.",
        }
    ]

    assert retrieve_relevant_methodology("unrelated cashflow topic", docs) == []


def test_pfe_methodology_keywords_prioritize_counterparty_notes():
    docs = [
        {
            "title": "Potential Future Exposure",
            "path": "docs/potential_future_exposure.md",
            "content": "PFE is a future exposure quantile across a time profile.",
        },
        {
            "title": "Expected Exposure and EPE",
            "path": "docs/expected_exposure_and_epe.md",
            "content": "Expected exposure and EPE summarize positive exposure.",
        },
        {
            "title": "Netting Set Exposure",
            "path": "docs/netting_set_exposure.md",
            "content": "A netting set aggregates transactions under a netting agreement.",
        },
        {
            "title": "Historical VaR",
            "path": "docs/historical_var.md",
            "content": "Historical VaR estimates a market loss percentile.",
        },
    ]

    results = retrieve_relevant_methodology(
        "potential future exposure PFE expected exposure EPE netting set counterparty exposure",
        docs,
        top_k=3,
    )

    assert {result["title"] for result in results} == {
        "Potential Future Exposure",
        "Expected Exposure and EPE",
        "Netting Set Exposure",
    }
    assert "Historical VaR" not in [result["title"] for result in results]


def test_project_methodology_docs_follow_mini_spec_structure():
    docs = load_methodology_docs()
    required_titles = {
        "Historical VaR",
        "Expected Shortfall",
        "Maximum Drawdown",
        "Concentration Risk",
        "Stress Testing",
        "Potential Future Exposure",
        "Expected Exposure and EPE",
        "Netting Set Exposure",
        "Model Limitations",
    }

    assert required_titles.issubset({doc["title"] for doc in docs})
    for doc in docs:
        for section in REQUIRED_MINI_SPEC_SECTIONS:
            assert section in doc["content"], f"{doc['title']} is missing {section}"


def test_market_risk_query_prioritizes_market_methodology_notes():
    results = retrieve_relevant_methodology(
        "downside risk annualized volatility historical var expected shortfall "
        "max drawdown concentration risk model limitations SPY QQQ",
        load_methodology_docs(),
        top_k=4,
    )
    titles = {result["title"] for result in results}

    assert {"Historical VaR", "Expected Shortfall", "Concentration Risk"}.issubset(
        titles
    )
    assert "Potential Future Exposure" not in titles
    assert "Expected Exposure and EPE" not in titles
    assert "Netting Set Exposure" not in titles
