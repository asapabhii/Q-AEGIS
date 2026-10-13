"""The shared classification result type, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

Both classifier engines — the keyword engine in
:mod:`app.classifier.stub_classifier` and the trained model engine in
:mod:`app.classifier.model_classifier` — return this exact shape, so the API,
the persistence layer, and the policy gate never need to know which engine ran.
The ``model_version`` field is what records that distinction on every stored
classification (``PRD.md`` FR-1).
"""

from dataclasses import dataclass

from app.classifier.labels import SensitivityLabel


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
        confidence: Confidence in ``base_label``, in ``[0.0, 1.0]``. Note this
            is confidence in the *pre-escalation* judgement; it is not restated
            as high confidence just because escalation occurred.
        model_version: Identifier of the logic that produced this result. The
            keyword engine records a ``stub-`` version; the trained model
            records its own artifact version, so stored rows are attributable to
            the engine that produced them.
        is_defaulted: True when confidence fell below the threshold and the
            fail-safe fired. Escalation moves one step and saturates at the most
            sensitive label, so when ``base_label`` is already the most
            sensitive this is True while ``sensitivity_label`` equals
            ``base_label``. Read it as "this result was not trusted on its own
            evidence", not strictly as "the label changed".
        base_label: What the engine judged before escalation. Retained so an
            analyst reviewing a flagged classification can see what the model or
            heuristic actually thought.
        confidence_threshold: The threshold in force for this classification.
        matched_keywords: The keyword rules that fired, for explainability. On
            the model engine these are the rules that escalated the model's
            judgement toward more protection.
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
