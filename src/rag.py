from __future__ import annotations

import re
from pathlib import Path


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def load_methodology_docs(docs_dir: str = "docs") -> list[dict]:
    """Load local markdown methodology documents."""
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        raise ValueError(f"Methodology docs directory does not exist: {docs_dir}")

    documents = []
    for path in sorted(docs_path.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        documents.append(
            {
                "title": _extract_title(content, path),
                "path": str(path),
                "content": content,
            }
        )

    if not documents:
        raise ValueError(f"No markdown methodology docs found in: {docs_dir}")

    return documents


def retrieve_relevant_methodology(
    query: str,
    docs: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """Retrieve methodology docs with deterministic keyword scoring."""
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    query_tokens = _tokenize(query)
    scored_docs = []

    for index, doc in enumerate(docs):
        title = doc.get("title", "")
        content = doc.get("content", "")
        title_tokens = _tokenize(title)
        content_tokens = _tokenize(content)

        title_score = len(query_tokens & title_tokens) * 3
        content_score = len(query_tokens & content_tokens)
        phrase_score = _phrase_score(query.lower(), title.lower(), content.lower())
        score = title_score + content_score + phrase_score

        if score > 0:
            scored_docs.append(
                {
                    "title": title,
                    "path": doc.get("path", ""),
                    "content": content,
                    "score": score,
                    "_index": index,
                }
            )

    scored_docs.sort(key=lambda doc: (-doc["score"], doc["title"], doc["_index"]))

    results = []
    for doc in scored_docs[:top_k]:
        doc = dict(doc)
        doc.pop("_index", None)
        results.append(doc)

    return results


def _extract_title(content: str, path: Path) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()

    return path.stem.replace("_", " ").title()


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def _phrase_score(query: str, title: str, content: str) -> int:
    score = 0
    combined = f"{title}\n{content}"

    phrases = {
        "var": ("var", "value at risk", "historical var"),
        "expected shortfall": ("expected shortfall", "tail loss"),
        "potential future exposure": (
            "potential future exposure",
            "pfe",
            "exposure profile",
        ),
        "pfe": ("potential future exposure", "pfe", "exposure profile"),
        "expected exposure": (
            "expected exposure",
            "expected positive exposure",
            "epe",
        ),
        "epe": ("expected exposure", "expected positive exposure", "epe"),
        "netting set": ("netting set", "netting agreement", "netted exposure"),
        "counterparty exposure": (
            "counterparty exposure",
            "counterparty risk",
            "monte carlo pricing engine",
        ),
        "drawdown": ("drawdown", "maximum drawdown"),
        "concentration": ("concentration", "sector", "factor", "technology", "growth"),
        "limitations": ("limitation", "limitations", "not investment advice"),
    }

    for query_phrase, doc_phrases in phrases.items():
        if query_phrase in query and any(doc_phrase in combined for doc_phrase in doc_phrases):
            score += 5

    return score
