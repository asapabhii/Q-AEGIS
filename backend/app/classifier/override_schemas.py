"""Pydantic models for manual classification overrides, ``PRD.md`` FR-12.

No raw dicts cross this API boundary. ``original_label`` is read from the
current effective sensitivity; the client cannot supply it. Extra keys are
forbidden, including a confirmation boolean: FR-12's checkbox is a UI gate,
not evidence the server can trust.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.classifier.labels import SensitivityLabel
from app.db.models.classification import MIN_JUSTIFICATION_CHARS


class ManualOverrideRequest(BaseModel):
    """Relabel one document. ``original_label`` is computed server-side."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    new_label: SensitivityLabel
    justification: str = Field(min_length=MIN_JUSTIFICATION_CHARS)

    @field_validator("justification")
    @classmethod
    def justification_must_meet_the_floor_after_strip(cls, value: str) -> str:
        """Leading or trailing whitespace does not count toward FR-12's floor."""
        stripped = value.strip()
        if len(stripped) < MIN_JUSTIFICATION_CHARS:
            raise ValueError(
                "justification must contain at least "
                f"{MIN_JUSTIFICATION_CHARS} non-padding characters"
            )
        return stripped


class ManualOverrideResponse(BaseModel):
    """One persisted human relabel."""

    id: UUID
    document_id: UUID
    overridden_by: UUID
    original_label: SensitivityLabel
    new_label: SensitivityLabel
    justification: str
    overridden_at: datetime
