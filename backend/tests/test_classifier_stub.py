"""Tests for the classifier stub, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

The fail-safe default is the reason this file exists. ``PRD.md`` Risk R1 notes
that removing it produces no visible error, only a quieter failure mode, so it
is asserted directly and from several angles rather than being assumed to fall
out of a happy-path test.

Thresholds are passed explicitly in most tests rather than read from
configuration, so a change to the default threshold cannot quietly invalidate
what these tests claim to prove.
"""

from dataclasses import FrozenInstanceError

import pytest

from app.classifier.labels import SensitivityLabel, rank
from app.classifier.stub_classifier import (
    EVIDENCE_SATURATION,
    MODEL_VERSION,
    _confidence,
    classify,
)

# One keyword from a single tier: dominant but thin evidence, so confidence
# lands at 1/EVIDENCE_SATURATION and the fail-safe fires.
ONE_CONFIDENTIAL_TERM = "This document is confidential."

# Three keywords from a single tier: dominant and saturated, so confidence
# reaches 1.0 and the fail-safe does not fire.
THREE_RESTRICTED_TERMS = "Employee SSN, passport number, and CVV are on file."

# No keyword from any tier.
NO_KEYWORDS = "The quick brown fox jumps over the lazy dog."


# --------------------------------------------------------------------------
# The fail-safe default. PRD FR-1, PRD Risk R1.
# --------------------------------------------------------------------------


def test_low_confidence_escalates_to_the_more_sensitive_label() -> None:
    """Below the threshold, the label moves UP one step and is flagged.

    This is the single most important assertion in the classifier suite.
    """
    result = classify(ONE_CONFIDENTIAL_TERM, threshold=0.60)

    assert result.base_label is SensitivityLabel.CONFIDENTIAL
    assert result.sensitivity_label is SensitivityLabel.RESTRICTED
    assert result.is_defaulted is True
    assert result.confidence < 0.60
    assert rank(result.sensitivity_label) > rank(result.base_label)


def test_high_confidence_leaves_the_label_untouched() -> None:
    """At or above the threshold the rules stand, with no escalation.

    The non-escalating path is a correct, normal outcome, not a fallback.
    """
    result = classify(THREE_RESTRICTED_TERMS, threshold=0.60)

    assert result.base_label is SensitivityLabel.RESTRICTED
    assert result.sensitivity_label is SensitivityLabel.RESTRICTED
    assert result.is_defaulted is False
    assert result.confidence >= 0.60


def test_no_keyword_match_is_not_treated_as_public() -> None:
    """Absence of evidence is an unknown, and an unknown resolves upward.

    A document the rules cannot read anything into must not be labelled PUBLIC,
    which is the most consequential form of under-protection available here.
    """
    result = classify(NO_KEYWORDS, threshold=0.60)

    assert result.matched_keywords == ()
    assert result.confidence == 0.0
    assert result.base_label is SensitivityLabel.PUBLIC
    assert result.sensitivity_label is SensitivityLabel.INTERNAL
    assert result.sensitivity_label is not SensitivityLabel.PUBLIC
    assert result.is_defaulted is True


@pytest.mark.parametrize("content", ["", "   ", "\n\t  \n"])
def test_empty_content_escalates_rather_than_defaulting_public(content: str) -> None:
    """Empty input is handled as zero evidence, never as confidently public."""
    result = classify(content, threshold=0.60)
    assert result.sensitivity_label is SensitivityLabel.INTERNAL
    assert result.is_defaulted is True


def test_escalation_saturates_at_the_most_sensitive_label() -> None:
    """A low-confidence RESTRICTED result stays RESTRICTED, and never wraps.

    ``is_defaulted`` is still True here: the result was not trusted on its own
    evidence, even though there is no higher label to move to.
    """
    result = classify("Reference to a single private key.", threshold=0.60)

    assert result.base_label is SensitivityLabel.RESTRICTED
    assert result.sensitivity_label is SensitivityLabel.RESTRICTED
    assert result.is_defaulted is True
    assert result.confidence < 0.60


@pytest.mark.parametrize(
    "content",
    [
        ONE_CONFIDENTIAL_TERM,
        THREE_RESTRICTED_TERMS,
        NO_KEYWORDS,
        "",
        "internal memo about the team offsite",
        "press release for public distribution",
        "salary and payroll data with medical record attached",
        "Reference to a single private key.",
    ],
)
@pytest.mark.parametrize("threshold", [0.0, 0.25, 0.60, 0.95, 1.0])
def test_result_is_never_less_sensitive_than_the_rules_supported(
    content: str, threshold: float
) -> None:
    """The invariant, asserted across content and threshold combinations.

    No threshold setting, including the extremes, may produce a downgrade.
    """
    result = classify(content, threshold=threshold)
    assert rank(result.sensitivity_label) >= rank(result.base_label)


def test_threshold_boundary_is_inclusive_at_the_threshold() -> None:
    """Confidence exactly equal to the threshold does NOT escalate.

    The comparison is strictly "below the threshold", per ``PRD.md`` FR-1.
    Pinning the boundary keeps a future ``<`` to ``<=`` edit from passing
    silently.
    """
    content = "This confidential file lists salary bands."
    measured = classify(content, threshold=0.0).confidence

    at_threshold = classify(content, threshold=measured)
    assert at_threshold.is_defaulted is False
    assert at_threshold.sensitivity_label is at_threshold.base_label

    just_above = classify(content, threshold=measured + 0.0001)
    assert just_above.is_defaulted is True


def test_raising_the_threshold_only_ever_increases_protection() -> None:
    """Monotonicity: a stricter threshold cannot yield a less sensitive label."""
    content = "This confidential file lists salary bands."
    lenient = classify(content, threshold=0.10)
    strict = classify(content, threshold=0.99)
    assert rank(strict.sensitivity_label) >= rank(lenient.sensitivity_label)


# --------------------------------------------------------------------------
# Scoring behavior
# --------------------------------------------------------------------------


def test_ties_break_toward_the_more_sensitive_label() -> None:
    """Equal evidence for two tiers resolves upward, not downward.

    Three PUBLIC terms at weight 1.0 exactly equal two INTERNAL terms at 1.5.
    With no basis to prefer either, the classifier takes the higher one.
    """
    content = (
        "press release and public announcement and marketing brochure, "
        "plus an internal memo with meeting notes"
    )
    result = classify(content, threshold=0.0)
    assert result.base_label is SensitivityLabel.INTERNAL


def test_a_strong_term_outweighs_several_weak_ones() -> None:
    """Tier weighting: one restricted term beats two internal ones.

    Without ascending weights, a document containing a private key alongside
    routine internal chatter could be labelled INTERNAL.
    """
    content = "internal memo with meeting notes, and the private key below"
    result = classify(content, threshold=0.0)
    assert result.base_label is SensitivityLabel.RESTRICTED


def test_evidence_volume_damps_confidence_below_saturation() -> None:
    """Fewer matches than EVIDENCE_SATURATION cannot reach full confidence."""
    one_term = classify("This document is confidential.", threshold=0.0)
    two_terms = classify("This confidential file lists salary bands.", threshold=0.0)

    assert one_term.confidence < two_terms.confidence
    assert one_term.confidence == pytest.approx(1 / EVIDENCE_SATURATION, abs=1e-4)


def test_split_evidence_lowers_confidence_below_a_single_tier() -> None:
    """Dominance: evidence spread across tiers is less trustworthy."""
    focused = classify(THREE_RESTRICTED_TERMS, threshold=0.0)
    split = classify(
        "press release and internal memo and confidential salary and ssn",
        threshold=0.0,
    )
    assert split.confidence < focused.confidence


@pytest.mark.parametrize(
    "content",
    [
        "",
        NO_KEYWORDS,
        ONE_CONFIDENTIAL_TERM,
        THREE_RESTRICTED_TERMS,
        "confidential ssn passport number cvv salary payroll biometric",
    ],
)
def test_confidence_stays_within_the_unit_interval(content: str) -> None:
    """Confidence is a probability-shaped value and must stay in [0, 1]."""
    result = classify(content, threshold=0.60)
    assert 0.0 <= result.confidence <= 1.0


def test_keywords_match_on_word_boundaries_only() -> None:
    """The token "ssn" must not match inside the word "lesson".

    A substring match here would label ordinary training material RESTRICTED,
    and the resulting noise is what erodes trust in the fail-safe.
    """
    result = classify("This lesson plan is a marketing brochure.", threshold=0.0)
    assert "ssn" not in result.matched_keywords
    assert result.base_label is SensitivityLabel.PUBLIC


def test_matching_is_case_insensitive() -> None:
    """Sensitive content is not less sensitive for being capitalized."""
    lower = classify("this document is confidential", threshold=0.60)
    upper = classify("THIS DOCUMENT IS CONFIDENTIAL", threshold=0.60)
    assert lower.base_label is upper.base_label
    assert lower.confidence == upper.confidence


def test_multi_word_keywords_match() -> None:
    """Phrase rules fire, not just single tokens."""
    result = classify("Attached is the patient diagnosis summary.", threshold=0.0)
    assert "patient diagnosis" in result.matched_keywords


# --------------------------------------------------------------------------
# Safety nets. These guard against regressions rather than normal input.
# --------------------------------------------------------------------------


def test_invariant_check_catches_an_escalation_that_downgrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken escalate() must raise, not silently return a weaker label.

    This is ``PRD.md`` Risk R1 simulated directly: the fail-safe is weakened in
    a way that produces no error of its own, only quieter under-protection.
    The runtime invariant check in ``classify`` is what turns that silent
    regression into a loud failure, and this test is what proves the check
    works. Without it, the check is untested code claiming to be a safety net.
    """
    monkeypatch.setattr(
        "app.classifier.stub_classifier.escalate",
        lambda label: SensitivityLabel.PUBLIC,
    )
    with pytest.raises(RuntimeError, match="fail-safe invariant violated"):
        classify(ONE_CONFIDENTIAL_TERM, threshold=0.60)


@pytest.mark.parametrize(
    "scores",
    [
        {},
        {SensitivityLabel.PUBLIC: 0.0},
        {SensitivityLabel.CONFIDENTIAL: -1.0},
    ],
)
def test_confidence_guard_returns_zero_for_non_positive_evidence(
    scores: dict[SensitivityLabel, float],
) -> None:
    """Zero or negative total weight yields zero confidence, never a divide.

    Unreachable through ``classify`` today, which never calls this with an
    empty score map. Tested directly because a future scoring change could
    reach it, and the failure mode would otherwise be a ZeroDivisionError or a
    nonsensical confidence value.
    """
    assert _confidence(scores, match_count=1) == 0.0


def test_confidence_is_zero_when_no_keywords_matched() -> None:
    """Positive weights with a zero match count still yields zero confidence."""
    assert _confidence({SensitivityLabel.RESTRICTED: 4.0}, match_count=0) == 0.0


# --------------------------------------------------------------------------
# Provenance and explainability
# --------------------------------------------------------------------------


def test_every_classification_records_its_model_version() -> None:
    """``PRD.md`` FR-1 requires the producing version on every classification."""
    result = classify(THREE_RESTRICTED_TERMS, threshold=0.60)
    assert result.model_version == MODEL_VERSION


def test_model_version_is_marked_as_a_stub() -> None:
    """Stored classifications must be identifiable as stub-produced.

    Without this, rows written by the keyword heuristic become indistinguishable
    from rows written by the real model once it lands, and there is no way to
    find and re-run them.
    """
    assert MODEL_VERSION.startswith("stub-")


def test_result_records_the_threshold_that_was_applied() -> None:
    """The threshold is part of the decision, so it is recorded with it."""
    assert classify(NO_KEYWORDS, threshold=0.42).confidence_threshold == 0.42


def test_rationale_explains_an_escalation() -> None:
    """An escalated result states why, for the analyst review screen (FR-12)."""
    rationale = classify(ONE_CONFIDENTIAL_TERM, threshold=0.60).rationale
    assert "Escalated to RESTRICTED" in rationale
    assert "confidential" in rationale
    assert "0.60" in rationale


def test_rationale_explains_a_non_escalated_result() -> None:
    """The normal path is explained too, not left blank."""
    rationale = classify(THREE_RESTRICTED_TERMS, threshold=0.60).rationale
    assert "No escalation applied" in rationale
    assert "RESTRICTED" in rationale


def test_rationale_states_when_no_rule_matched() -> None:
    """Zero evidence is described as such, not reported as an empty match set."""
    assert "zero evidence" in classify(NO_KEYWORDS, threshold=0.60).rationale


def test_matched_keywords_are_reported_for_explainability() -> None:
    """Analysts need to see which terms fired, per FR-12 and FR-16."""
    matched = classify(THREE_RESTRICTED_TERMS, threshold=0.60).matched_keywords
    assert set(matched) == {"ssn", "passport number", "cvv"}


def test_result_is_immutable() -> None:
    """A classification is a historical fact; the record cannot be edited.

    ``classification_metadata`` is append-only (``SPEC.md`` Section 5), so a
    result object that could be mutated would misrepresent the storage model.
    """
    result = classify(NO_KEYWORDS, threshold=0.60)
    with pytest.raises(FrozenInstanceError):
        result.sensitivity_label = SensitivityLabel.PUBLIC  # type: ignore[misc]


def test_classification_is_deterministic() -> None:
    """Same input, same output. Required for a reproducible audit trail."""
    first = classify(ONE_CONFIDENTIAL_TERM, threshold=0.60)
    second = classify(ONE_CONFIDENTIAL_TERM, threshold=0.60)
    assert first == second


def test_threshold_defaults_to_configuration_when_omitted() -> None:
    """Omitting the threshold reads it from settings rather than hardcoding."""
    from app.config import get_settings

    result = classify(NO_KEYWORDS)
    assert result.confidence_threshold == (
        get_settings().classifier_confidence_threshold
    )
