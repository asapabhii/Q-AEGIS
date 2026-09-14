"""Tests for FR-11 RAG embeddings and grounded ask pipeline."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.db.enums import UserRole
from app.db.seed import seed_development_users
from app.rag.embeddings import EMBEDDING_MODEL_STUB, embed_text
from app.rag.pipeline import ask_question
from app.rag.store import upsert_chunk


def test_embed_text_stub_is_normalized_and_stable() -> None:
    a = embed_text("confidential financial report", dims=64)
    b = embed_text("confidential financial report", dims=64)
    assert len(a) == 64
    assert a == b
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


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
    assert body["embedding_model"] == EMBEDDING_MODEL_STUB

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
    assert answer["embedding_model"] == EMBEDDING_MODEL_STUB
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
