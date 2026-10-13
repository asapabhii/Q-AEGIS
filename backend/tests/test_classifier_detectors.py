"""Tests for the high-precision content detectors, ``PRD.md`` FR-1.

These lock two things the trained model and keyword engine cannot guarantee on
their own: that a document carrying a *validated* hard identifier (SSN, card,
IBAN, key material, classification banner, PHI) escalates, and — just as load
bearing — that the near-misses (placeholder secrets, example numbers, the word
"secret" in prose) do NOT fire. A false RESTRICTED erodes operator trust, so the
precision assertions here are as important as the recall ones.
"""

from __future__ import annotations

import pytest

from app.classifier import stub_classifier
from app.classifier.detectors import apply_detectors, detect
from app.classifier.labels import SensitivityLabel

_R = SensitivityLabel.RESTRICTED
_C = SensitivityLabel.CONFIDENTIAL


def _label(content: str) -> SensitivityLabel | None:
    return detect(content)[0]


def _signals(content: str) -> tuple[str, ...]:
    return detect(content)[1]


# --- SSN ---------------------------------------------------------------------


def test_valid_dashed_ssn_is_restricted():
    assert _label("Employee SSN 123-45-6789 is on file.") is _R
    assert "ssn" in _signals("Employee SSN 123-45-6789 is on file.")


@pytest.mark.parametrize(
    "text",
    [
        "sample id 000-45-6789",  # area 000 is reserved/invalid
        "sample id 666-45-6789",  # area 666 is reserved/invalid
        "sample id 900-45-6789",  # area 900-999 is reserved/invalid
        "sample id 123-00-6789",  # group 00 is invalid
        "sample id 123-45-0000",  # serial 0000 is invalid
        "order 123456789 shipped",  # undashed run is intentionally not matched
    ],
)
def test_invalid_or_undashed_ssn_does_not_fire(text):
    assert _label(text) is None


# --- Payment cards -----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Card 4111 1111 1111 1111 on file",  # Visa
        "MC 5555555555554444 charged",  # Mastercard
        "Amex 3782 822463 10005",  # Amex (15 digits)
        "Discover 6011000990139424",  # Discover
    ],
)
def test_valid_cards_are_restricted(text):
    assert _label(text) is _R
    assert "credit_card_luhn" in _signals(text)


def test_luhn_passing_number_without_issuer_prefix_does_not_fire():
    # 1234567812345670 passes Luhn but no card network starts with "1".
    assert _label("Order reference number 1234567812345670 shipped.") is None


def test_non_luhn_card_length_number_does_not_fire():
    assert _label("Card 4111 1111 1111 1112 declined.") is None


def test_card_ending_a_sentence_still_fires():
    # A trailing sentence period must not hide the card (real prose ends here).
    assert _label("We charged card 4111 1111 1111 1111.") is _R


def test_sixteen_digit_decimal_amount_does_not_fire():
    # A 16-digit run that is really the integer part of a decimal is not a card.
    assert _label("The contract value was 4111111111111111.00 dollars.") is None


# --- IBAN --------------------------------------------------------------------


def test_valid_iban_is_confidential():
    text = "Wire to GB82 WEST 1234 5698 7654 32 by Friday."
    assert _label(text) is _C
    assert "iban_mod97" in _signals(text)


def test_iban_with_bad_checksum_does_not_fire():
    assert _label("Wire to GB99 WEST 1234 5698 7654 32 by Friday.") is None


# --- Keys and secrets --------------------------------------------------------


@pytest.mark.parametrize(
    "text,signal",
    [
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIB", "private_key_pem"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Blb", "private_key_pem"),
        ("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", "aws_access_key"),
        ("token ghp_" + "a" * 36, "github_token"),
        ("slack xoxb-1234567890-abcdefghij", "slack_token"),
        ("google AIza" + "A" * 35, "google_api_key"),
        ("stripe sk_live_" + "a" * 24, "stripe_key"),
    ],
)
def test_key_material_is_restricted(text, signal):
    assert _label(text) is _R
    assert signal in _signals(text)


def test_secret_assignment_with_real_value_fires():
    assert _label('password = "S3cur3P@ssw0rd!42x"') is _R
    assert "secret_assignment" in _signals('api_key: "aB3xZ9kLmNpQ7rTv"')


@pytest.mark.parametrize(
    "text",
    [
        'api_key = "your_api_key_here"',
        'secret = "changeme"',
        'password = "xxxxxxxxxxxx"',
        'token = "REDACTED_TOKEN"',
        'api_key = "example_value"',
    ],
)
def test_placeholder_secret_does_not_fire(text):
    assert _label(text) is None


def test_high_entropy_token_fires_only_with_secret_context():
    with_ctx = "Set the api_key to aG9WbXR6c1FwWmtMc0RmM2dIeAxZ9Q1"
    without_ctx = "The payload was aG9WbXR6c1FwWmtMc0RmM2dIeAxZ9Q1 in transit."
    assert _label(with_ctx) is _R
    assert "high_entropy_secret" in _signals(with_ctx)
    assert _label(without_ctx) is None


# --- Classification markings -------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "TOP SECRET//SI//NOFORN",
        "Classification: SECRET",
        "TS//SCI briefing follows",
        "Handling: NOFORN",
    ],
)
def test_restricted_markings_fire(text):
    assert _label(text) is _R
    assert "classification_marking" in _signals(text)


@pytest.mark.parametrize(
    "text",
    [
        "Please keep this a secret between us.",  # lowercase prose
        "The Secretary of State spoke today.",  # 'Secretary' is not a marking
        "We run a secret santa every December.",
    ],
)
def test_secret_in_ordinary_prose_does_not_fire(text):
    assert _label(text) is None


def test_confidential_marking_is_confidential():
    assert _label("This document is Confidential.") is _C
    assert "confidential_marking" in _signals("CUI//FOUO cover sheet")


# --- PHI ---------------------------------------------------------------------


def test_medical_context_with_identifier_is_restricted():
    text = "Patient John Doe, MRN 88213, diagnosis hypertension, dosage 40mg."
    assert _label(text) is _R
    assert "phi_with_identifier" in _signals(text)


def test_two_medical_terms_without_identifier_is_confidential():
    assert _label("The treatment plan and prognosis were reviewed.") is _C


def test_single_medical_word_alone_does_not_fire():
    assert _label("The treatment was effective and morale improved.") is None


# --- PII cluster -------------------------------------------------------------


def test_email_and_phone_cluster_is_confidential():
    text = "Contact John at john.doe@acme.com or call (415) 555-0132."
    assert _label(text) is _C
    assert "pii_cluster" in _signals(text)


def test_lone_email_does_not_fire():
    assert _label("Questions? Email hello@example.com anytime.") is None


# --- Aggregation and the escalate-only contract ------------------------------


def test_detect_returns_most_sensitive_of_multiple_hits():
    text = "Confidential memo. Employee SSN 123-45-6789 enclosed."
    label, signals = detect(text)
    assert label is _R  # SSN (RESTRICTED) beats confidential marking
    assert {"ssn", "confidential_marking"} <= set(signals)


def test_empty_content_yields_no_detection():
    assert detect("") == (None, ())


def test_clean_prose_yields_no_detection():
    assert detect("The quick brown fox jumps over the lazy dog.") == (None, ())


def test_apply_detectors_never_lowers_a_label():
    # Already RESTRICTED; a CONFIDENTIAL detector must not pull it down.
    label, signals = apply_detectors(_R, "Wire to GB82 WEST 1234 5698 7654 32.")
    assert label is _R
    assert signals == ("detector:iban_mod97",)


def test_apply_detectors_escalates_and_prefixes_signals():
    label, signals = apply_detectors(
        SensitivityLabel.PUBLIC, "SSN 123-45-6789"
    )
    assert label is _R
    assert signals == ("detector:ssn",)


def test_apply_detectors_no_hit_returns_label_unchanged():
    label, signals = apply_detectors(SensitivityLabel.PUBLIC, "a plain sentence")
    assert label is SensitivityLabel.PUBLIC
    assert signals == ()


# --- Engine integration (keyword fallback path) ------------------------------


def test_stub_engine_escalates_on_a_bare_identifier_with_no_keywords():
    # A raw SSN with no keyword vocabulary at all must not read as PUBLIC.
    result = stub_classifier.classify("Reference: 123-45-6789.", threshold=0.6)
    assert result.sensitivity_label is _R
    assert "detector:ssn" in result.matched_keywords


def test_stub_engine_benign_document_is_unaffected_by_detectors():
    result = stub_classifier.classify(
        "The quick brown fox jumps over the lazy dog.", threshold=0.6
    )
    assert all(not k.startswith("detector:") for k in result.matched_keywords)
