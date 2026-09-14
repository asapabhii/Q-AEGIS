"""Four-node LangGraph RAG pipeline, ``SPEC.md`` 3.12 / PRD FR-11.

Nodes: Planner → Retriever → Reasoner → Verifier. Answers are refused when
the Verifier cannot ground claims in retrieved records.
"""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.rag.embeddings import EMBEDDING_MODEL_STUB
from app.rag.schemas import RagAnswer, RagCitation
from app.rag.store import similarity_search


class RagState(TypedDict, total=False):
    question: str
    document_id: str | None
    plan: str
    hits: list[dict[str, Any]]
    draft_answer: str
    verified: bool
    refusal_reason: str | None
    citations: list[dict[str, Any]]


def _planner(state: RagState) -> dict[str, Any]:
    question = state["question"].strip()
    doc = state.get("document_id")
    if doc:
        plan = (
            f"Retrieve inventory and audit records for document {doc} that "
            f"answer: {question}"
        )
    else:
        plan = (
            f"Retrieve the most relevant stored decision records that answer: "
            f"{question}"
        )
    return {"plan": plan}


def _make_retriever(session: Session):
    def retriever(state: RagState) -> dict[str, Any]:
        doc_raw = state.get("document_id")
        document_id = UUID(doc_raw) if doc_raw else None
        hits = similarity_search(
            session,
            state["question"],
            document_id=document_id,
            limit=5,
        )
        return {"hits": hits}

    return retriever


def _reasoner(state: RagState) -> dict[str, Any]:
    hits = state.get("hits") or []
    if not hits:
        return {
            "draft_answer": "",
            "citations": [],
        }
    bullets = []
    citations: list[dict[str, Any]] = []
    for hit in hits:
        bullets.append(f"- ({hit['source_type']}) {hit['content'][:500]}")
        citations.append(hit)
    draft = (
        f"Based on {len(hits)} retrieved system record(s):\n"
        + "\n".join(bullets)
        + f"\n\nDirect answer to the question «{state['question']}»: "
        "the records above are the grounded evidence. Summarize only what they "
        "state; do not invent facts beyond them."
    )
    # Produce a concise grounded summary from the first hit + count.
    top = hits[0]["content"]
    draft = (
        f"Grounded summary for «{state['question']}»: "
        f"The strongest matching record ({hits[0]['source_type']}) states: "
        f"{top[:600]}"
    )
    if len(hits) > 1:
        draft += f" Additionally, {len(hits) - 1} related record(s) were retrieved."
    return {"draft_answer": draft, "citations": citations}


def _verifier(state: RagState) -> dict[str, Any]:
    hits = state.get("hits") or []
    draft = (state.get("draft_answer") or "").strip()
    if not hits or not draft:
        return {
            "verified": False,
            "refusal_reason": (
                "No grounded records were retrieved for this question. "
                "Ingest document records first (POST /api/v1/rag/ingest)."
            ),
            "draft_answer": "",
            "citations": [],
        }
    # Require every citation id to appear in hits (identity ground check).
    hit_ids = {str(h["chunk_id"]) for h in hits}
    for cite in state.get("citations") or []:
        if str(cite["chunk_id"]) not in hit_ids:
            return {
                "verified": False,
                "refusal_reason": (
                    "Verifier rejected the draft: a citation was not in the "
                    "retrieved set."
                ),
                "draft_answer": "",
                "citations": [],
            }
    # Require draft to share substantial tokens with at least one hit.
    draft_tokens = set(draft.lower().split())
    grounded = False
    for hit in hits:
        hit_tokens = set(str(hit["content"]).lower().split())
        if len(draft_tokens & hit_tokens) >= 3:
            grounded = True
            break
    if not grounded:
        return {
            "verified": False,
            "refusal_reason": (
                "Verifier rejected the draft: it was not sufficiently grounded "
                "in retrieved record text."
            ),
            "draft_answer": "",
            "citations": [],
        }
    return {"verified": True, "refusal_reason": None}


def build_rag_graph(session: Session):
    """Compile Planner → Retriever → Reasoner → Verifier."""
    builder: StateGraph = StateGraph(RagState)
    builder.add_node("planner", _planner)
    builder.add_node("retriever", _make_retriever(session))
    builder.add_node("reasoner", _reasoner)
    builder.add_node("verifier", _verifier)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "retriever")
    builder.add_edge("retriever", "reasoner")
    builder.add_edge("reasoner", "verifier")
    builder.add_edge("verifier", END)
    return builder.compile()


def ask_question(
    session: Session,
    *,
    question: str,
    document_id: UUID | None = None,
) -> RagAnswer:
    """Run the four-node pipeline and return a verified (or refused) answer."""
    cleaned = question.strip()
    if len(cleaned) < 3:
        raise ValueError("question must be at least 3 characters")
    graph = build_rag_graph(session)
    final: RagState = graph.invoke(
        {
            "question": cleaned,
            "document_id": str(document_id) if document_id else None,
        }
    )
    citations = [
        RagCitation(
            chunk_id=c["chunk_id"],
            source_type=c["source_type"],
            source_id=c.get("source_id"),
            document_id=c.get("document_id"),
            content=c["content"],
            score=float(c.get("score") or 0.0),
        )
        for c in (final.get("citations") or [])
    ]
    verified = bool(final.get("verified"))
    return RagAnswer(
        question=cleaned,
        answer=final.get("draft_answer") or "",
        verified=verified,
        plan=final.get("plan") or "",
        citations=citations if verified else [],
        embedding_model=EMBEDDING_MODEL_STUB,
        refusal_reason=final.get("refusal_reason"),
    )
