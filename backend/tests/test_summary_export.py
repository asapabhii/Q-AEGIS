"""Document summary export tests, ``PRD.md`` FR-16."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, UserRole
from app.db.models import AuditLog
from app.export.summary import SummaryBundle, render_csv, render_pdf


def test_render_csv_and_pdf_round_trip_bytes() -> None:
    bundle = SummaryBundle(
        document_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        filename="report.pdf",
        status="classified",
        sensitivity_label="CONFIDENTIAL",
        label_source="classification",
        risk_value="0.4500",
        trust_score="0.720",
        consensus_version="weighted-mean-0.1.0",
        policy_ai="force_pqc",
        policy_final="force_pqc",
        policy_overridden="no",
        profile_type="post_quantum",
        encrypted="yes",
        shredded="no",
        agent_rows=(("security", "0.700", "ok"),),
        generated_at="2026-09-14T00:00:00+00:00",
    )
    csv_bytes = render_csv(bundle)
    assert b"document_id" in csv_bytes
    assert b"security" in csv_bytes
    pdf_bytes = render_pdf(bundle)
    assert pdf_bytes.startswith(b"%PDF")
    assert b"Q-AEGIS" in pdf_bytes


def test_summary_endpoint_csv(
    client: TestClient, db_session: Session, registered_document
) -> None:
    response = client.get(
        f"/api/v1/documents/{registered_document.id}/summary?format=csv",
        headers={"X-Q-AEGIS-Actor-Role": UserRole.DATA_OWNER.value},
    )
    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["content-type"]
    assert registered_document.filename.encode() in response.content

    events = [
        e
        for e in db_session.query(AuditLog)
        .filter(AuditLog.document_id == registered_document.id)
        .all()
        if e.event_type == AuditEventType.DOCUMENT_SUMMARY_EXPORTED.value
    ]
    assert len(events) == 1
