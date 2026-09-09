"""Tests for the crypto-shredding stub module and endpoint (SPEC 3.9, PRD FR-8).

This tests a stub implementation.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.
"""

from uuid import uuid4

import pytest
from fastapi import status

from app.crypto.shredding import ShredResult, shred_document_key
from app.db.enums import AuditEventType, DocumentStatus


def test_shredding_is_stub():
    import app.crypto.shredding as mod
    assert "stub" in mod.__doc__.lower()


def test_liboqs_caveat_present_in_all_crypto_modules():
    import app.crypto as pkg
    import app.crypto.selector as sel
    import app.crypto.shredding as shred

    for m in (pkg, sel, shred):
        assert "SECURITY CAVEAT: liboqs is NOT independently audited" in m.__doc__


def test_shred_document_key_pure_function():
    doc_id = uuid4()
    actor_id = uuid4()
    res = shred_document_key(doc_id, actor_id)
    assert isinstance(res, ShredResult)
    assert res.document_id == doc_id
    assert res.actor_id == actor_id
    assert res.shredded_at is not None
