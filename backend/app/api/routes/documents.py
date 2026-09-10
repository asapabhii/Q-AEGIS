"""Document registration, ``SPEC.md`` Section 5.

PARTIAL IMPLEMENTATION OF ``PRD.md`` FR-1's INPUT PATH, and labelled as such
because the gap matters to anyone building on it: this registers a document's
metadata, it does not accept a file. There is no object storage in this build, so
``storage_path`` stays null and ``current_status`` stays ``registered`` rather
than ``uploaded``.

It exists because ``classification_metadata.document_id`` is a foreign key to
``documents.id``, so a classification cannot be recorded for a document the
system has never heard of. The alternative was to leave ``/classify`` accepting
any invented UUID, which is what it did before the schema existed.

The file-upload half belongs to the classification request screen (``SPEC.md``
3.13, Input Screen 1) and its 50 MB / PDF-DOCX-XLSX-TXT validation rules. When it
lands, this endpoint gains a ``storage_path`` and this docstring loses its first
paragraph.

``GET /documents`` and ``GET /documents/{id}`` are the FR-14 read surface.
They do not write. Stage fields stay null until that step has run.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.deps import (
    DbSession,
    DocumentInventoryCaller,
    RegisterDocumentCaller,
    resolve_seeded_actor,
)
from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.enums import AuditEventType, CryptoProfileType, DocumentStatus, PolicyAction
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import inventory as inventory_repo
from app.db.repositories.inventory import DocumentSnapshot

router = APIRouter(tags=["documents"])

#: Upper bound on a filename, matching ``documents.filename``'s ``varchar(255)``.
MAX_FILENAME_CHARS = 255


class DocumentRegistrationRequest(BaseModel):
    """A request to register one document's metadata."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(
        min_length=1,
        max_length=MAX_FILENAME_CHARS,
        description="Original filename, not a storage key.",
    )

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str) -> str:
        """Reject a whitespace-only filename.

        ``min_length`` alone accepts a single space, which would store a document
        with no usable name and no error anywhere.
        """
        if not value.strip():
            raise ValueError(
                "filename must contain at least one non-whitespace character"
            )
        return value


class DocumentResponse(BaseModel):
    """A registered document."""

    id: UUID
    filename: str
    storage_path: str | None
    current_status: DocumentStatus
    uploaded_by: UUID
    uploaded_at: datetime


class DocumentSnapshotResponse(BaseModel):
    """One document's current risk and protection status. Not persisted."""

    id: UUID
    filename: str
    storage_path: str | None
    current_status: DocumentStatus
    uploaded_by: UUID
    uploaded_at: datetime
    sensitivity_label: SensitivityLabel | None
    label_source: SensitivitySource | None
    override_id: UUID | None
    classification_id: UUID | None
    risk_score_id: UUID | None
    risk_value: Decimal | None
    risk_computed_at: datetime | None
    trust_score_id: UUID | None
    trust_score: Decimal | None
    trust_computed_at: datetime | None
    policy_decision_id: UUID | None
    final_decision: PolicyAction | None
    decided_at: datetime | None
    crypto_profile_id: UUID | None
    profile_type: CryptoProfileType | None
    selected_at: datetime | None

    @classmethod
    def from_snapshot(cls, snapshot: DocumentSnapshot) -> "DocumentSnapshotResponse":
        """Project a repository snapshot onto the inventory contract."""
        document = snapshot.document
        classification = snapshot.classification
        override = snapshot.override
        risk = snapshot.risk
        trust = snapshot.trust
        decision = snapshot.decision
        profile = snapshot.profile
        return cls(
            id=document.id,
            filename=document.filename,
            storage_path=document.storage_path,
            current_status=document.current_status,
            uploaded_by=document.uploaded_by,
            uploaded_at=document.uploaded_at,
            sensitivity_label=snapshot.sensitivity_label,
            label_source=snapshot.label_source,
            override_id=(
                None
                if snapshot.label_source is not SensitivitySource.MANUAL_OVERRIDE
                else override.id
            ),
            classification_id=None if classification is None else classification.id,
            risk_score_id=None if risk is None else risk.id,
            risk_value=None if risk is None else risk.risk_value,
            risk_computed_at=None if risk is None else risk.computed_at,
            trust_score_id=None if trust is None else trust.id,
            trust_score=None if trust is None else trust.consensus_value,
            trust_computed_at=None if trust is None else trust.computed_at,
            policy_decision_id=None if decision is None else decision.id,
            final_decision=None if decision is None else decision.final_decision,
            decided_at=None if decision is None else decision.decided_at,
            crypto_profile_id=None if profile is None else profile.id,
            profile_type=None if profile is None else profile.profile_type,
            selected_at=None if profile is None else profile.selected_at,
        )


class DocumentInventoryResponse(BaseModel):
    """FR-14 inventory. Every monitored document, no silent truncation."""

    count: int
    documents: list[DocumentSnapshotResponse]


@router.get(
    "/documents",
    response_model=DocumentInventoryResponse,
    summary="List documents with current risk and protection status",
)
def list_document_inventory(
    session: DbSession,
    _caller: DocumentInventoryCaller,
) -> DocumentInventoryResponse:
    """Return every document's latest snapshot. Writes nothing.

    Stage fields are null until that step has run. The effective label is
    the latest override, else the latest classification — the same rule
    the policy gate uses. A later classification does not retract an
    override.
    """
    snapshots = inventory_repo.list_snapshots(session)
    return DocumentInventoryResponse(
        count=len(snapshots),
        documents=[DocumentSnapshotResponse.from_snapshot(item) for item in snapshots],
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentSnapshotResponse,
    summary="One document's current risk and protection status",
)
def get_document_inventory_item(
    document_id: UUID,
    session: DbSession,
    _caller: DocumentInventoryCaller,
) -> DocumentSnapshotResponse:
    """Return one snapshot, or 404 when the document does not exist.

    Writes nothing. Same field contract as one row of ``GET /documents``.
    """
    snapshot = inventory_repo.get_snapshot(session, document_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )
    return DocumentSnapshotResponse.from_snapshot(snapshot)


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a document's metadata (no file upload, see module docstring)",
)
def register_document(
    request: DocumentRegistrationRequest,
    session: DbSession,
    caller: RegisterDocumentCaller,
) -> DocumentResponse:
    """Register a document and record the registration in the audit log.

    Both writes share the request's transaction, so a document row cannot exist
    without the audit entry that accounts for it (``PRD.md`` Section 7: a decision
    with no corresponding audit entry is a defect).
    """
    actor = resolve_seeded_actor(session, caller)
    document = documents_repo.register_document(
        session, uploaded_by=actor.id, filename=request.filename
    )

    audit_repo.append_entry(
        session,
        event_type=AuditEventType.DOCUMENT_REGISTERED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload={
            "document_id": str(document.id),
            "filename": document.filename,
            "storage_path": document.storage_path,
            "current_status": document.current_status.value,
            "registered_by": str(actor.id),
            "registered_by_role": actor.role.value,
        },
    )

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        storage_path=document.storage_path,
        current_status=document.current_status,
        uploaded_by=document.uploaded_by,
        uploaded_at=document.uploaded_at,
    )
