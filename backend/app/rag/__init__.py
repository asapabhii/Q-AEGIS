"""Agentic retrieval and Q&A, ``SPEC.md`` 3.12, implements ``PRD.md`` FR-11.

Four LangGraph nodes — Planner, Retriever, Reasoner, Verifier — answer
natural-language questions only when grounded in retrieved system records.
Vector store is pgvector (see ``docs/decisions.md``). Embeddings are a
deterministic local stub until a labelled embedding model is wired; the stub
is labelled as such in code and tests.

Owner: Abhinav (``WORK_DIVISION.md``).
"""

from app.rag.ingest import ingest_document_records
from app.rag.pipeline import ask_question
from app.rag.schemas import RagAnswer, RagIngestResult

__all__ = [
    "RagAnswer",
    "RagIngestResult",
    "ask_question",
    "ingest_document_records",
]
