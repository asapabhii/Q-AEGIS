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
from app.rag.pipeline import ask_question
from app.rag.store import upsert_chunk


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
