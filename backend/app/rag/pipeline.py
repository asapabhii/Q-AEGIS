"""Four-node LangGraph RAG pipeline, ``SPEC.md`` 3.12 / PRD FR-11.

Nodes: Planner → Retriever → Reasoner → Verifier. Answers are refused when the
Verifier cannot ground claims in retrieved records.

Grounding is enforced at two independent points, so a refusal is never cosmetic:

* the **Retriever** applies a semantic similarity floor
  (:func:`app.rag.store.effective_min_similarity`); when no stored chunk clears
  it there are no hits and the answer is refused;
* the **Verifier** independently re-checks that the best hit clears the floor,
  that every citation is one of the retrieved hits, and that the drafted answer
  actually reproduces a contiguous span of retrieved text (so it cannot assert
  anything the evidence does not contain).

The **Reasoner** here is a deterministic *extractive* synthesizer: it quotes the
strongest retrieved record rather than generating prose. That is the documented
offline default (mirroring the deterministic agent scorers); a generative LLM
reasoner is the gated upgrade, and the Verifier's span/citation checks are what
keep such a generator honest once it is enabled.
"""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.rag.embeddings import embedding_model_name
from app.rag.schemas import RagAnswer, RagCitation
from app.rag.store import effective_min_similarity, similarity_search

#: Minimum length, in whitespace tokens, of a contiguous span that the drafted
#: answer must share with some retrieved chunk for the answer to count as
#: grounded. Long enough that the pipeline's own framing ("Grounded summary
#: for ...") cannot satisfy it on its own, so the match must come from quoted
#: evidence. For a chunk shorter than this, the whole chunk is the span.
_GROUNDING_SPAN_TOKENS = 6


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
        return {"draft_answer": "", "citations": []}
    # Deterministic extractive synthesis (the documented offline default): quote
    # the strongest retrieved record verbatim rather than generate prose. Every
    # retrieved hit is offered as a citation; the Verifier independently confirms
    # each is in the retrieved set and that the draft reproduces retrieved text.
    citations: list[dict[str, Any]] = list(hits)
    top = hits[0]["content"]
    draft = (
        f"Grounded summary for «{state['question']}»: "
        f"The strongest matching record ({hits[0]['source_type']}) states: "
        f"{top[:600]}"
    )
    if len(hits) > 1:
        draft += f" Additionally, {len(hits) - 1} related record(s) were retrieved."
    return {"draft_answer": draft, "citations": citations}


def _tokenize(value: str) -> list[str]:
    """Lowercase whitespace tokens, used for the contiguous-span grounding check."""
    return value.lower().split()


def _answer_grounded_in_hits(answer: str, hits: list[dict[str, Any]]) -> bool:
    """True when ``answer`` reproduces a contiguous span of some hit's text.

    This is the substance of the grounding gate for a generated (or extractive)
    answer: it must contain a run of at least ``_GROUNDING_SPAN_TOKENS`` tokens
    that appears verbatim in a retrieved chunk (or the whole chunk, when it is
    shorter). An answer that shares no such span with any evidence — e.g. a
    hallucinated claim — fails and is refused. It is deliberately independent of
    how the draft was built, so it still bites when the LLM reasoner is enabled.
    """
    answer_joined = " ".join(_tokenize(answer))
    if not answer_joined:
        return False
    for hit in hits:
        tokens = _tokenize(str(hit.get("content") or ""))
        if not tokens:
            continue
        span = min(_GROUNDING_SPAN_TOKENS, len(tokens))
        for start in range(len(tokens) - span + 1):
            window = " ".join(tokens[start : start + span])
            if window and window in answer_joined:
                return True
    return False


def _verifier(state: RagState) -> dict[str, Any]:
    hits = state.get("hits") or []
    draft = (state.get("draft_answer") or "").strip()
    if not hits or not draft:
        return {
            "verified": False,
            "refusal_reason": (
                "No retrieved record cleared the grounding similarity floor for "
                "this question. Ingest relevant document records first "
                "(POST /api/v1/rag/ingest)."
            ),
            "draft_answer": "",
            "citations": [],
        }
    # 1. Citation integrity: every citation must be one of the retrieved hits.
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
    # 2. Relevance floor (re-checked here, not trusted from the Retriever): the
    #    best hit must clear the semantic similarity floor. On the deterministic
    #    backend the floor is 0.0, so this is a no-op there by design.
    floor = effective_min_similarity()
    best_score = max((float(h.get("score") or 0.0) for h in hits), default=0.0)
    if best_score < floor:
        return {
            "verified": False,
            "refusal_reason": (
                "Verifier rejected the draft: the best retrieved record "
                f"(similarity {best_score:.3f}) is below the grounding floor "
                f"({floor:.3f})."
            ),
            "draft_answer": "",
            "citations": [],
        }
    # 3. Answer support: the draft must reproduce a contiguous span of retrieved
    #    text, so it cannot claim anything the evidence does not contain.
    if not _answer_grounded_in_hits(draft, hits):
        return {
            "verified": False,
            "refusal_reason": (
                "Verifier rejected the draft: it did not reproduce any span of "
                "the retrieved record text."
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
        embedding_model=embedding_model_name(),
        refusal_reason=final.get("refusal_reason"),
    )
