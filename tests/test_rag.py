from src.rag import load_methodology_docs, retrieve_relevant_methodology


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
