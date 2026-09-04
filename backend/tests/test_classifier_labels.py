"""Tests for the sensitivity label ordering, ``app.classifier.labels``.

This ordering is what "default to the more sensitive label" resolves through,
so it is tested independently of the classifier that consumes it. ``PRD.md``
Risk R1 is specifically about this behavior being weakened without anyone
noticing, and a reordered ``SENSITIVITY_ORDER`` would do exactly that while
every classifier test still passed.
"""

import pytest

from app.classifier.labels import (
    LEAST_SENSITIVE,
    MOST_SENSITIVE,
    SENSITIVITY_ORDER,
    SensitivityLabel,
    escalate,
    is_more_sensitive,
    most_sensitive_of,
    rank,
)


def test_order_contains_every_label_exactly_once() -> None:
    """A label missing from the order would make rank() raise at runtime."""
    assert set(SENSITIVITY_ORDER) == set(SensitivityLabel)
    assert len(SENSITIVITY_ORDER) == len(set(SENSITIVITY_ORDER))


def test_order_runs_least_to_most_sensitive() -> None:
    """Pin the intended sequence explicitly, so a reordering fails here."""
    assert SENSITIVITY_ORDER == (
        SensitivityLabel.PUBLIC,
        SensitivityLabel.INTERNAL,
        SensitivityLabel.CONFIDENTIAL,
        SensitivityLabel.RESTRICTED,
    )
    assert LEAST_SENSITIVE is SensitivityLabel.PUBLIC
    assert MOST_SENSITIVE is SensitivityLabel.RESTRICTED


def test_rank_increases_with_sensitivity() -> None:
    """rank() must be strictly monotonic over the declared order."""
    ranks = [rank(label) for label in SENSITIVITY_ORDER]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)


def test_is_more_sensitive_is_strict() -> None:
    """A label is not more sensitive than itself."""
    assert is_more_sensitive(SensitivityLabel.RESTRICTED, SensitivityLabel.PUBLIC)
    assert not is_more_sensitive(SensitivityLabel.PUBLIC, SensitivityLabel.RESTRICTED)
    assert not is_more_sensitive(SensitivityLabel.INTERNAL, SensitivityLabel.INTERNAL)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        (SensitivityLabel.PUBLIC, SensitivityLabel.INTERNAL),
        (SensitivityLabel.INTERNAL, SensitivityLabel.CONFIDENTIAL),
        (SensitivityLabel.CONFIDENTIAL, SensitivityLabel.RESTRICTED),
        (SensitivityLabel.RESTRICTED, SensitivityLabel.RESTRICTED),
    ],
)
def test_escalate_moves_one_step_up(
    label: SensitivityLabel, expected: SensitivityLabel
) -> None:
    """Escalation advances exactly one step and stops at the top."""
    assert escalate(label) is expected


@pytest.mark.parametrize("label", list(SensitivityLabel))
def test_escalate_never_reduces_sensitivity(label: SensitivityLabel) -> None:
    """The core fail-safe guarantee, asserted over every label.

    Saturating at the top rather than wrapping around is what this catches: a
    wraparound implementation would turn RESTRICTED into PUBLIC and pass every
    other test in this file.
    """
    assert rank(escalate(label)) >= rank(label)


def test_most_sensitive_of_picks_the_highest() -> None:
    """Used wherever several signals must collapse to one label."""
    assert (
        most_sensitive_of(
            [
                SensitivityLabel.PUBLIC,
                SensitivityLabel.RESTRICTED,
                SensitivityLabel.INTERNAL,
            ]
        )
        is SensitivityLabel.RESTRICTED
    )


def test_most_sensitive_of_rejects_an_empty_list() -> None:
    """No defensible answer exists for an empty set, so it raises."""
    with pytest.raises(ValueError):
        most_sensitive_of([])
