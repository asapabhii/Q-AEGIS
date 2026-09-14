"""Document summary export endpoint, ``PRD.md`` FR-16."""

from enum import Enum
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.api.deps import DbSession, SummaryCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.export.summary import (
    build_summary,
    render_csv,
    render_pdf,
    summary_audit_payload,
)

router = APIRouter(tags=["summary"])


class SummaryFormat(str, Enum):
    CSV = "csv"
    PDF = "pdf"


@router.get(
    "/documents/{document_id}/summary",
    summary="Export one document's classification/risk/protection summary",
    response_class=Response,
)
def export_document_summary(
    document_id: UUID,
    session: DbSession,
    caller: SummaryCaller,
    format: SummaryFormat = SummaryFormat.CSV,
) -> Response:
    """Return CSV or PDF for one document. Audits the export event."""
    bundle = build_summary(session, document_id)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document registered with id {document_id}.",
        )

    if format is SummaryFormat.PDF:
        body = render_pdf(bundle)
        media = "application/pdf"
        filename = f"qaegis-summary-{document_id}.pdf"
    else:
        body = render_csv(bundle)
        media = "text/csv; charset=utf-8"
        filename = f"qaegis-summary-{document_id}.csv"

    actor = resolve_seeded_actor(session, caller)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.DOCUMENT_SUMMARY_EXPORTED.value,
        document_id=document_id,
        actor_id=actor.id,
        payload=summary_audit_payload(
            document_id=document_id,
            format=format.value,
            byte_length=len(body),
        ),
    )

    return Response(
        content=body,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
