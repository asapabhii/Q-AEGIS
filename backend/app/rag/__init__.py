"""Agentic retrieval and Q&A, ``SPEC.md`` 3.12, implements ``PRD.md`` FR-11.

Four LangGraph nodes — Planner, Retriever, Reasoner, Verifier — answer
natural-language questions only when grounded in retrieved system records.
Vector store is pgvector (see ``docs/decisions.md``). Embeddings are real
transformer vectors via ``fastembed`` (default ``BAAI/bge-large-en-v1.5``,
1024-dim); a deterministic offline backend is used only for hermetic tests. See
``app.rag.embeddings``.
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
