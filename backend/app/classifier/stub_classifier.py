"""Rule/keyword-based sensitivity classifier STUB, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

THIS MODULE IS A STUB. It is a deterministic keyword heuristic, not a trained
model, and it is not the target implementation. ``SPEC.md`` 3.2 defines the build
order explicitly: this stub first, the real Scikit-learn model only once a
labelled dataset exists, which ``PRD.md`` Section 9 records as a dependency that
is not yet satisfied. ``PRD.md`` Section 8 excludes this stub from the
classification-accuracy success metric for that reason.

What is NOT a stub here is the fail-safe escalation. A confidence score below
the configured threshold escalates the result to the more sensitive label. That
behavior is load-bearing for the entire system's security posture, it survives
the replacement of this stub by the real model, and it has dedicated tests
asserting it (see ``PRD.md`` Risk R1, which describes exactly how this could be
silently removed in a future refactor).
"""

import re
from dataclasses import dataclass

from app.classifier.labels import (
    LEAST_SENSITIVE,
    SensitivityLabel,
    escalate,
    rank,
)
from app.classifier.rules import KEYWORD_RULES, KeywordRule
from app.config import get_settings

#: Version string recorded on every classification, per ``PRD.md`` FR-1 ("every
#: classification records which model version produced it"). The ``stub-``
#: prefix is deliberate: a stored classification must be identifiable as
#: stub-produced so it can be found and re-run once the real model lands.
MODEL_VERSION = "stub-keyword-rules-0.1.0"

#: Number of distinct keyword matches at which evidence volume is considered
#: saturated. Below this, confidence is damped, which is what causes a
#: thin-evidence document to escalate rather than be trusted.
EVIDENCE_SATURATION = 3

#: Keyword rules precompiled to word-boundary patterns, so that "ssn" matches
#: the token "SSN" but not the substring inside "lesson".
_COMPILED_RULES: tuple[tuple[KeywordRule, re.Pattern[str]], ...] = tuple(
    (rule, re.compile(rf"\b{re.escape(rule.keyword)}\b", re.IGNORECASE))
    for rule in KEYWORD_RULES
)


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of one classification.

    Frozen because a classification is a historical fact.
    ``classification_metadata`` is an append-only history table
    (``SPEC.md`` Section 5), so a result is superseded by a new record, never
    mutated in place.

    Attributes:
        sensitivity_label: The label the system will act on, after fail-safe
            escalation has been applied.
        confidence: Heuristic confidence in ``base_label``, in ``[0.0, 1.0]``.
            Note this is confidence in the *pre-escalation* judgement; it is not
            restated as high confidence just because escalation occurred.
        model_version: Identifier of the logic that produced this result.
        is_defaulted: True when confidence fell below the threshold and the
            fail-safe fired. Escalation moves one step and saturates at the most
            sensitive label, so when ``base_label`` is already the most
            sensitive this is True while ``sensitivity_label`` equals
            ``base_label``. Read it as "this result was not trusted on its own
            evidence", not strictly as "the label changed".
        base_label: What the rules alone suggested, before escalation. Retained
            so an analyst reviewing a flagged classification can see what the
            heuristic actually thought.
        confidence_threshold: The threshold in force for this classification.
        matched_keywords: The keywords that fired, for explainability.
        rationale: Human-readable explanation of the decision.
    """

    sensitivity_label: SensitivityLabel
    confidence: float
    model_version: str
    is_defaulted: bool
    base_label: SensitivityLabel
    confidence_threshold: float
    matched_keywords: tuple[str, ...]
    rationale: str


def _score(content: str) -> tuple[dict[SensitivityLabel, float], tuple[str, ...]]:
    """Accumulate per-label evidence weight and the keywords that fired.

    Returns:
        A ``(scores, matched_keywords)`` pair. ``scores`` contains only labels
        with at least one match, so an empty dict means no evidence at all.
    """
    scores: dict[SensitivityLabel, float] = {}
    matched: list[str] = []
    for rule, pattern in _COMPILED_RULES:
        if pattern.search(content):
            scores[rule.label] = scores.get(rule.label, 0.0) + rule.weight
            matched.append(rule.keyword)
    return scores, tuple(matched)


def _select_base_label(scores: dict[SensitivityLabel, float]) -> SensitivityLabel:
    """Pick the best-supported label, breaking ties toward more sensitive.

    The tie-break direction is a fail-safe in its own right: when two labels are
    supported by exactly equal evidence, the system has no basis to prefer the
    lower one, so it does not.
    """
    return max(scores.items(), key=lambda item: (item[1], rank(item[0])))[0]


def _confidence(scores: dict[SensitivityLabel, float], match_count: int) -> float:
    """Compute heuristic confidence in the selected label.

    Two independent factors, multiplied:

    - **Dominance**: the winning label's share of total evidence weight. A
      document matching only confidential terms scores 1.0 here; one split
      evenly between two labels scores near 0.5.
    - **Volume**: how much evidence exists at all, saturating at
      ``EVIDENCE_SATURATION`` matches. This is what stops a single incidental
      keyword from producing a confident answer.

    Multiplying rather than averaging means either factor being weak is enough
    to hold confidence down, which is the conservative direction.
    """
    total = sum(scores.values())
    if total <= 0.0 or match_count <= 0:
        return 0.0
    dominance = max(scores.values()) / total
    volume = min(1.0, match_count / EVIDENCE_SATURATION)
    return round(dominance * volume, 4)


def classify(content: str, *, threshold: float | None = None) -> ClassificationResult:
    """Classify ``content`` and apply the fail-safe escalation.

    Args:
        content: Raw document text. Empty or whitespace-only content is valid
            input and yields zero evidence, which escalates rather than being
            reported as confidently public.
        threshold: Confidence threshold override. Defaults to
            ``Settings.classifier_confidence_threshold``. Injectable so tests
            can pin it rather than depending on ambient configuration.

    Returns:
        A :class:`ClassificationResult`. When ``confidence`` is strictly below
        the threshold, ``sensitivity_label`` is one step more sensitive than
        ``base_label`` and ``is_defaulted`` is True.

    Raises:
        RuntimeError: if the computed label would be less sensitive than the
            rules alone supported. This is an internal invariant check, not
            input validation. It exists because that specific regression is
            silent by nature (``PRD.md`` Risk R1): it produces no error, only a
            quieter failure mode, so it is checked explicitly at runtime rather
            than trusted to review.
    """
    effective_threshold = (
        get_settings().classifier_confidence_threshold
        if threshold is None
        else threshold
    )

    scores, matched_keywords = _score(content)

    if not scores:
        # No evidence at all. This is NOT treated as "confidently public": an
        # unreadable, empty, or simply unrecognized document is an unknown, and
        # an unknown resolves toward more protection, never less.
        base_label = LEAST_SENSITIVE
        confidence = 0.0
    else:
        base_label = _select_base_label(scores)
        confidence = _confidence(scores, len(matched_keywords))

    is_defaulted = confidence < effective_threshold
    final_label = escalate(base_label) if is_defaulted else base_label

    if rank(final_label) < rank(base_label):
        raise RuntimeError(
            "Classifier fail-safe invariant violated: final label "
            f"{final_label.value} is less sensitive than base label "
            f"{base_label.value}. Escalation must never downgrade."
        )

    return ClassificationResult(
        sensitivity_label=final_label,
        confidence=confidence,
        model_version=MODEL_VERSION,
        is_defaulted=is_defaulted,
        base_label=base_label,
        confidence_threshold=effective_threshold,
        matched_keywords=matched_keywords,
        rationale=_rationale(
            base_label=base_label,
            final_label=final_label,
            confidence=confidence,
            threshold=effective_threshold,
            matched_keywords=matched_keywords,
            is_defaulted=is_defaulted,
        ),
    )


def _rationale(
    *,
    base_label: SensitivityLabel,
    final_label: SensitivityLabel,
    confidence: float,
    threshold: float,
    matched_keywords: tuple[str, ...],
    is_defaulted: bool,
) -> str:
    """Build the human-readable explanation attached to a result."""
    if matched_keywords:
        evidence = (
            f"matched {len(matched_keywords)} keyword rule(s): "
            f"{', '.join(matched_keywords)}"
        )
    else:
        evidence = "matched no keyword rules, treated as zero evidence"

    if is_defaulted:
        return (
            f"Keyword rules suggested {base_label.value} ({evidence}), with "
            f"confidence {confidence:.4f} below the threshold {threshold:.2f}. "
            f"Escalated to {final_label.value} because low-confidence "
            f"classifications resolve toward more protection."
        )
    return (
        f"Classified {final_label.value} ({evidence}), with confidence "
        f"{confidence:.4f} at or above the threshold {threshold:.2f}. "
        f"No escalation applied."
    )
