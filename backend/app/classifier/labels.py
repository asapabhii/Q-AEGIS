"""Sensitivity labels and their ordering.

The ordering defined here is what makes "default to the more sensitive label"
(``PRD.md`` FR-1, ``SPEC.md`` 3.2) a well-defined operation. Every comparison of
"more" or "less" sensitive in this codebase resolves through this module, so
there is exactly one place where that ordering is defined.

Do not reorder ``SENSITIVITY_ORDER`` without reading ``PRD.md`` Risk R1 first:
the classifier's fail-safe escalation is derived from this sequence, and
silently reversing or reordering it would weaken the fail-safe without raising
any error.
"""

from enum import Enum


class SensitivityLabel(str, Enum):
    """A document's sensitivity label.

    ``str`` subclass so the value serializes directly in API responses and
    persists as a readable string rather than an opaque integer.
    """

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class SensitivitySource(str, Enum):
    """Which persisted row supplied the effective sensitivity label.

    The policy gate and the override write path share this vocabulary so an
    auditor can tell a human relabel from an AI classification without
    inferring it from timestamps.
    """

    CLASSIFICATION = "classification"
    MANUAL_OVERRIDE = "manual_override"


#: Labels from least to most sensitive. Index position is the sensitivity rank.
SENSITIVITY_ORDER: tuple[SensitivityLabel, ...] = (
    SensitivityLabel.PUBLIC,
    SensitivityLabel.INTERNAL,
    SensitivityLabel.CONFIDENTIAL,
    SensitivityLabel.RESTRICTED,
)

#: The least sensitive label. The starting point when no rule matches at all.
LEAST_SENSITIVE: SensitivityLabel = SENSITIVITY_ORDER[0]

#: The most sensitive label. Escalation saturates here.
MOST_SENSITIVE: SensitivityLabel = SENSITIVITY_ORDER[-1]


def rank(label: SensitivityLabel) -> int:
    """Return the sensitivity rank of ``label``, higher meaning more sensitive."""
    return SENSITIVITY_ORDER.index(label)


def is_more_sensitive(left: SensitivityLabel, right: SensitivityLabel) -> bool:
    """Return True if ``left`` is strictly more sensitive than ``right``."""
    return rank(left) > rank(right)


def escalate(label: SensitivityLabel) -> SensitivityLabel:
    """Return the next more sensitive label, saturating at ``MOST_SENSITIVE``.

    Saturation rather than wraparound is deliberate. Wrapping ``RESTRICTED``
    back around to ``PUBLIC`` would turn the fail-safe into a downgrade, which
    is the exact failure mode ``PRD.md`` Risk R1 warns about.
    """
    current = rank(label)
    if current >= rank(MOST_SENSITIVE):
        return MOST_SENSITIVE
    return SENSITIVITY_ORDER[current + 1]


def most_sensitive_of(labels: list[SensitivityLabel]) -> SensitivityLabel:
    """Return the most sensitive label in ``labels``.

    Raises:
        ValueError: if ``labels`` is empty, since there is no defensible
            sensitivity to assume for an empty set. Callers decide what an
            absence of evidence means; this function does not guess.
    """
    if not labels:
        raise ValueError("most_sensitive_of() requires at least one label")
    return max(labels, key=rank)
