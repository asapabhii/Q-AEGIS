"""Pydantic request/response models for the classifier API, ``SPEC.md`` 3.2.

Per ``AGENTS.md``, no raw dicts cross an API boundary, and every input
validation rule is enforced server-side here rather than relying on the
frontend.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.classifier.labels import SensitivityLabel
from app.classifier.result import ClassificationResult

#: Upper bound on inline content accepted in one request. A cap is required so
#: an oversized body is rejected before it reaches the regex scan rather than
#: after.
MAX_CONTENT_CHARS = 1_000_000


class ClassificationRequest(BaseModel):
    """A request to classify one document.

    ``SPEC.md`` 3.2 specifies that ``POST /classify`` accepts a document
    reference. ``document_id`` is that reference.

    PHASE 1 LIMITATION: ``content`` is passed inline because no document store
    or event bus exists yet (``SPEC.md`` 3.1 is unbuilt). The real
    implementation resolves ``document_id`` to its ``storage_path`` and reads
    the content server-side, at which point ``content`` is dropped from this
    model. Do not build a client that depends on inline content permanently.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: UUID = Field(
        description="Reference to the document being classified.",
    )
    content: str = Field(
        min_length=1,
        max_length=MAX_CONTENT_CHARS,
        description="Document text. Phase 1 only, see the class docstring.",
    )

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        """Reject whitespace-only content.

        A blank body is a malformed request, not a document with no sensitive
        content, and conflating the two would record a classification for
        something that was never actually submitted.
        """
        if not value.strip():
            raise ValueError(
                "content must contain at least one non-whitespace character"
            )
        return value


class ClassificationResponse(BaseModel):
    """The result of one classification.

    The four fields required by ``SPEC.md`` 3.2's API contract are
    ``sensitivity_label``, ``confidence``, ``model_version``, and
    ``is_defaulted``. The remainder support the explainability that
    ``PRD.md`` FR-16's risk breakdown and FR-12's override screen need.
    """

    # ``protected_namespaces`` is cleared because ``SPEC.md`` 3.2 names the
    # field ``model_version``, and Pydantic v2 otherwise warns on any field
    # beginning with ``model_``. The spec's contract wins over the default.
    model_config = ConfigDict(protected_namespaces=())

    document_id: UUID
    sensitivity_label: SensitivityLabel
    confidence: float = Field(ge=0.0, le=1.0)
    model_version: str
    is_defaulted: bool
    base_label: SensitivityLabel
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str]
    rationale: str
    classified_at: datetime

    @classmethod
    def from_result(
        cls,
        *,
        document_id: UUID,
        result: ClassificationResult,
        classified_at: datetime,
    ) -> "ClassificationResponse":
        """Build a response from a domain result.

        Keeps the domain layer (:mod:`app.classifier.stub_classifier`) free of
        any framework dependency, so the classifier can be tested and reused
        without FastAPI or Pydantic in the way.
        """
        return cls(
            document_id=document_id,
            sensitivity_label=result.sensitivity_label,
            confidence=result.confidence,
            model_version=result.model_version,
            is_defaulted=result.is_defaulted,
            base_label=result.base_label,
            confidence_threshold=result.confidence_threshold,
            matched_keywords=list(result.matched_keywords),
            rationale=result.rationale,
            classified_at=classified_at,
        )
