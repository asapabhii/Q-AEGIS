"""Document summary export (CSV / PDF), ``SPEC.md`` 3.13 / ``PRD.md`` FR-16."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AgentOutput
from app.db.repositories import ciphertexts as ciphertext_repo
from app.db.repositories import inventory as inventory_repo
from sqlalchemy import select


@dataclass(frozen=True)
class SummaryBundle:
    """Flat fields for CSV and PDF renderers."""

    document_id: str
    filename: str
    status: str
    sensitivity_label: str
    label_source: str
    risk_value: str
    trust_score: str
    consensus_version: str
    policy_ai: str
    policy_final: str
    policy_overridden: str
    profile_type: str
    encrypted: str
    shredded: str
    agent_rows: tuple[tuple[str, str, str], ...]
    generated_at: str


def build_summary(session: Session, document_id: UUID) -> SummaryBundle | None:
    """Assemble one document's exportable summary, or ``None`` if unknown."""
    snap = inventory_repo.get_snapshot(session, document_id)
    if snap is None:
        return None

    agent_rows: list[tuple[str, str, str]] = []
    if snap.trust is not None:
        outputs = session.scalars(
            select(AgentOutput)
            .where(AgentOutput.risk_score_id == snap.trust.risk_score_id)
            .order_by(AgentOutput.agent_type.asc())
        ).all()
        for row in outputs:
            agent_rows.append((row.agent_type.value, str(row.score), row.rationale))

    latest_ct = ciphertext_repo.latest_for_document(session, document_id)
    shredded = "no"
    encrypted = "no"
    if latest_ct is not None:
        encrypted = "yes"
        from app.crypto.shred import is_shredded

        shredded = "yes" if is_shredded(latest_ct.wrapped_dek) else "no"

    return SummaryBundle(
        document_id=str(snap.document.id),
        filename=snap.document.filename,
        status=snap.document.current_status.value,
        sensitivity_label=(
            snap.sensitivity_label.value if snap.sensitivity_label else ""
        ),
        label_source=snap.label_source.value if snap.label_source else "",
        risk_value=str(snap.risk.risk_value) if snap.risk else "",
        trust_score=str(snap.trust.consensus_value) if snap.trust else "",
        consensus_version=snap.trust.consensus_version if snap.trust else "",
        policy_ai=(snap.decision.ai_recommendation.value if snap.decision else ""),
        policy_final=(snap.decision.final_decision.value if snap.decision else ""),
        policy_overridden=(
            "yes" if snap.decision and snap.decision.overridden else "no"
        ),
        profile_type=(snap.profile.profile_type.value if snap.profile else ""),
        encrypted=encrypted,
        shredded=shredded,
        agent_rows=tuple(agent_rows),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def render_csv(bundle: SummaryBundle) -> bytes:
    """UTF-8 CSV bytes for one summary."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["field", "value"])
    for field, value in [
        ("document_id", bundle.document_id),
        ("filename", bundle.filename),
        ("status", bundle.status),
        ("sensitivity_label", bundle.sensitivity_label),
        ("label_source", bundle.label_source),
        ("risk_value", bundle.risk_value),
        ("trust_score", bundle.trust_score),
        ("consensus_version", bundle.consensus_version),
        ("policy_ai_recommendation", bundle.policy_ai),
        ("policy_final_decision", bundle.policy_final),
        ("policy_overridden", bundle.policy_overridden),
        ("crypto_profile", bundle.profile_type),
        ("encrypted", bundle.encrypted),
        ("shredded", bundle.shredded),
        ("generated_at", bundle.generated_at),
    ]:
        writer.writerow([field, value])
    writer.writerow([])
    writer.writerow(["agent_type", "score", "rationale"])
    for agent_type, score, rationale in bundle.agent_rows:
        writer.writerow([agent_type, score, rationale])
    return buffer.getvalue().encode("utf-8")


def render_pdf(bundle: SummaryBundle) -> bytes:
    """Minimal single-page PDF without third-party deps."""
    lines = [
        "Q-AEGIS Shield — Document Summary",
        f"Generated: {bundle.generated_at}",
        "",
        f"Document: {bundle.filename}",
        f"ID: {bundle.document_id}",
        f"Status: {bundle.status}",
        f"Sensitivity: {bundle.sensitivity_label} ({bundle.label_source})",
        f"Risk: {bundle.risk_value}",
        f"Trust: {bundle.trust_score} ({bundle.consensus_version})",
        f"Policy: {bundle.policy_ai} -> {bundle.policy_final} "
        f"(overridden={bundle.policy_overridden})",
        f"Crypto profile: {bundle.profile_type}",
        f"Encrypted: {bundle.encrypted}  Shredded: {bundle.shredded}",
        "",
        "Agents:",
    ]
    for agent_type, score, rationale in bundle.agent_rows:
        clipped = rationale.replace("\n", " ")[:90]
        lines.append(f"- {agent_type}: {score} — {clipped}")
    return _simple_pdf(lines)


def _simple_pdf(lines: list[str]) -> bytes:
    """Write a one-page PDF with Helvetica text (no external library)."""

    # PDF string escaping
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = ["BT", "/F1 11 Tf", "50 780 Td", "14 TL"]
    first = True
    for line in lines:
        safe = esc(line[:110])
        if first:
            content_lines.append(f"({safe}) Tj")
            first = False
        else:
            content_lines.append(f"T* ({safe}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def summary_audit_payload(
    *, document_id: UUID, format: str, byte_length: int
) -> dict[str, object]:
    """Audit payload for one export."""
    return {
        "document_id": str(document_id),
        "format": format,
        "byte_length": byte_length,
    }
