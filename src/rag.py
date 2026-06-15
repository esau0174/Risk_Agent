"""Compatibility wrapper for src.knowledge.rag. New code should import from src.knowledge.rag."""

from src.knowledge.rag import load_methodology_docs, retrieve_relevant_methodology

__all__ = ["load_methodology_docs", "retrieve_relevant_methodology"]
