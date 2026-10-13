"""Tests for FR-11 RAG embeddings and grounded ask pipeline.

The suite runs with the deterministic embedding backend (conftest sets
``RAG_EMBEDDING_BACKEND=deterministic``) so it stays offline and fast. The real
fastembed model is exercised by ``test_fastembed_backend_real_model``, which is
skipped unless ``RUN_REAL_EMBED_TESTS=1`` because it downloads model weights.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.config import get_settings
from app.db.enums import UserRole
from app.db.seed import seed_development_users
from app.rag.embeddings import DETERMINISTIC_MODEL_NAME, embed_text
from app.rag.pipeline import (
    _answer_grounded_in_hits,
    _verifier,
    ask_question,
)
from app.rag.store import effective_min_similarity, upsert_chunk


def test_deterministic_embed_is_normalized_and_stable() -> None:
    # Default width tracks RAG_EMBEDDING_DIMS (1024), matching the pgvector column.
    a = embed_text("confidential financial report")
    b = embed_text("confidential financial report")
    assert len(a) == get_settings().rag_embedding_dims
    assert a == b
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6
    # The width override still applies for the deterministic backend.
    assert len(embed_text("x", dims=64)) == 64


def test_rag_ingest_and_ask_verified(
    client: TestClient, db_session: Session, registered_document
) -> None:
    seed_development_users(db_session)
    db_session.flush()
    headers = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ADMIN.value}
    document_id = registered_document.id

    ingest = client.post(
        f"/api/v1/rag/ingest/{document_id}",
        headers=headers,
    )
    assert ingest.status_code == 201, ingest.text
    body = ingest.json()
    assert body["chunks_written"] >= 1
    assert body["embedding_model"] == DETERMINISTIC_MODEL_NAME

    ask = client.post(
        "/api/v1/rag/ask",
        headers=headers,
        json={
            "question": "What is the filename and status of this document?",
            "document_id": str(document_id),
        },
    )
    assert ask.status_code == 200, ask.text
    answer = ask.json()
    assert answer["embedding_model"] == DETERMINISTIC_MODEL_NAME
    # With inventory (+ maybe empty audit), verifier should ground.
    assert answer["verified"] is True
    assert answer["answer"]
    assert len(answer["citations"]) >= 1


def test_rag_ask_refuses_without_chunks(db_session: Session) -> None:
    # Direct pipeline call with empty store for a random id filter.
    answer = ask_question(
        db_session,
        question="What happened to this unknown document recently?",
        document_id=uuid4(),
    )
    assert answer.verified is False
    assert answer.refusal_reason


def test_upsert_chunk_roundtrip(db_session: Session, registered_document) -> None:
    chunk_id = upsert_chunk(
        db_session,
        document_id=registered_document.id,
        source_type="test",
        source_id="1",
        content="sensitivity confidential risk trust policy crypto",
    )
    db_session.flush()
    assert chunk_id


def test_effective_min_similarity_is_backend_aware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The floor is only active for the semantic fastembed backend."""
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "deterministic")
    monkeypatch.setenv("RAG_MIN_SIMILARITY", "0.42")
    get_settings.cache_clear()
    assert effective_min_similarity() == 0.0

    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "fastembed")
    get_settings.cache_clear()
    assert effective_min_similarity() == pytest.approx(0.42)
    get_settings.cache_clear()


def _hit(content: str, *, score: float, chunk_id=None) -> dict:
    return {
        "chunk_id": chunk_id or uuid4(),
        "document_id": None,
        "source_type": "inventory",
        "source_id": "1",
        "content": content,
        "embedding_model": DETERMINISTIC_MODEL_NAME,
        "score": score,
    }


def test_answer_grounded_in_hits_span_check() -> None:
    """Grounding requires a contiguous span shared with a retrieved chunk."""
    hit = _hit(
        "the quarterly report is classified confidential and restricted", score=0.9
    )
    grounded = (
        "Summary: the quarterly report is classified confidential and restricted."
    )
    fabricated = "The document is public and freely shareable with everyone today."
    assert _answer_grounded_in_hits(grounded, [hit]) is True
    assert _answer_grounded_in_hits(fabricated, [hit]) is False


def test_verifier_refuses_when_below_similarity_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A best hit under the grounding floor is refused, even with a draft."""
    monkeypatch.setattr("app.rag.pipeline.effective_min_similarity", lambda: 0.5)
    hit = _hit("alpha beta gamma delta epsilon zeta eta theta", score=0.2)
    state = {
        "hits": [hit],
        "draft_answer": "alpha beta gamma delta epsilon zeta eta theta",
        "citations": [hit],
    }
    result = _verifier(state)
    assert result["verified"] is False
    assert "below the grounding floor" in result["refusal_reason"]


def test_verifier_refuses_ungrounded_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relevant hit but a draft sharing no span with it is refused."""
    monkeypatch.setattr("app.rag.pipeline.effective_min_similarity", lambda: 0.3)
    hit = _hit("alpha beta gamma delta epsilon zeta eta theta", score=0.9)
    state = {
        "hits": [hit],
        "draft_answer": "completely unrelated fabricated statement about nothing",
        "citations": [hit],
    }
    result = _verifier(state)
    assert result["verified"] is False
    assert "did not reproduce any span" in result["refusal_reason"]


def test_verifier_accepts_grounded_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Floor cleared + citations valid + span reproduced -> verified."""
    monkeypatch.setattr("app.rag.pipeline.effective_min_similarity", lambda: 0.3)
    hit = _hit("alpha beta gamma delta epsilon zeta eta theta", score=0.8)
    state = {
        "hits": [hit],
        "draft_answer": "Record states: alpha beta gamma delta epsilon zeta eta.",
        "citations": [hit],
    }
    result = _verifier(state)
    assert result["verified"] is True
    assert result["refusal_reason"] is None


def test_verifier_rejects_foreign_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A citation not in the retrieved hit set is refused."""
    monkeypatch.setattr("app.rag.pipeline.effective_min_similarity", lambda: 0.0)
    hit = _hit("alpha beta gamma delta epsilon zeta", score=0.8)
    foreign = _hit("other content entirely", score=0.8)
    state = {
        "hits": [hit],
        "draft_answer": "alpha beta gamma delta epsilon zeta",
        "citations": [foreign],
    }
    result = _verifier(state)
    assert result["verified"] is False
    assert "not in the" in result["refusal_reason"]


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_EMBED_TESTS") != "1",
    reason="set RUN_REAL_EMBED_TESTS=1 to run the real fastembed model",
)
def test_fastembed_backend_real_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production backend yields normalized, semantically meaningful vectors."""
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "fastembed")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    monkeypatch.setenv("RAG_EMBEDDING_DIMS", "1024")
    get_settings.cache_clear()
    from app.rag import embeddings

    embeddings._fastembed_model.cache_clear()

    vec = embed_text("the quarterly report is classified confidential")
    assert len(vec) == 1024
    norm = sum(v * v for v in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6

    # A real semantic model ranks a related sentence above an unrelated one.
    def cosine(u: list[float], v: list[float]) -> float:
        return sum(a * b for a, b in zip(u, v))

    base = embed_text("the quarterly report is classified confidential")
    related = embed_text("this document is highly confidential")
    unrelated = embed_text("the weather today is sunny and warm")
    assert cosine(base, related) > cosine(base, unrelated)
