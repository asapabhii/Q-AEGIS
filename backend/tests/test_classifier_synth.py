"""Tests for the synthetic generator and corpus builder, ``PRD.md`` FR-1.

These lock the two properties the training pipeline relies on: the synthetic
documents are *deterministic* (a corpus rebuild is reproducible) and every
sensitive template carries a *structurally valid* identifier, so the production
detectors validate it exactly as they would a real one — the synthetic documents
are real in format, not fake signals. They also lock the weak-supervision
contract in :mod:`app.classifier.build_corpus`: the final label is the source
prior escalated by the detectors and is never lowered below the prior.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.classifier import build_corpus, synth
from app.classifier.detectors import _iban_valid, _luhn_ok, detect
from app.classifier.labels import SensitivityLabel, rank

_R = SensitivityLabel.RESTRICTED
_C = SensitivityLabel.CONFIDENTIAL
_P = SensitivityLabel.PUBLIC


def test_generation_is_deterministic_in_seed():
    a = list(synth.iter_documents(per_tier=50, seed=7))
    b = list(synth.iter_documents(per_tier=50, seed=7))
    assert a == b
    c = list(synth.iter_documents(per_tier=50, seed=8))
    assert a != c  # a different seed yields a different corpus


def test_per_tier_count_and_tiers():
    docs = list(synth.iter_documents(per_tier=30, seed=1))
    assert len(docs) == 90  # three tiers
    tiers = {tier for _, tier, _ in docs}
    assert tiers == {_R, _C, _P}


def test_public_templates_never_trip_a_detector():
    for content, tier, _ in synth.iter_documents(per_tier=200, seed=3):
        if tier is _P:
            assert detect(content)[0] is None, content[:80]


def test_sensitive_templates_are_confirmed_by_detectors():
    # Every non-public document must carry a validated identifier that the
    # detector escalates to at least its intended tier — no bare-keyword bluffs.
    for content, tier, _ in synth.iter_documents(per_tier=200, seed=5):
        if tier is _P:
            continue
        label, _signals = detect(content)
        assert label is not None and rank(label) >= rank(tier), content[:80]


def test_identifier_generators_are_structurally_valid():
    import random

    rng = random.Random(0)
    for _ in range(200):
        card = synth._card(rng).replace(" ", "")
        assert _luhn_ok(card)
        assert _iban_valid(synth._iban(rng))
        area = int(synth._ssn(rng)[:3])
        assert area not in (0, 666) and not (900 <= area <= 999)


def test_final_label_escalates_but_never_lowers():
    # Detector present and higher → escalates.
    assert build_corpus._final_label("SSN 123-45-6789", _P) is _R
    # Detector present but lower than prior → prior wins (no downgrade).
    assert build_corpus._final_label("SSN 123-45-6789", _R) is _R
    # No detector → prior unchanged.
    assert build_corpus._final_label("a plain sentence", _C) is _C


def test_build_writes_parseable_ml_labelled_csv(tmp_path: Path):
    out = tmp_path / "corpus.csv"
    counts = build_corpus.build(
        out,
        cables=None,
        synth_per_tier=40,
        newsgroups_limit=0,
        code_root=None,
        max_code=0,
        cap_per_majority=0,
        seed=2,
    )
    assert sum(counts.values()) > 0
    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["content", "label", "source_id"]
        rows = list(reader)
    assert rows
    # INTERNAL is policy-only and must never appear in training data.
    labels = {row["label"] for row in rows}
    assert labels <= {"PUBLIC", "CONFIDENTIAL", "RESTRICTED"}
    assert all(row["content"].strip() for row in rows)
