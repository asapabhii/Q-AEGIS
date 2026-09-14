"""Migration candidates and ranking helpers, ``SPEC.md`` 3.10 / ``PRD.md`` FR-9."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import CryptoProfileType, MigrationStatus
from app.db.models import MigrationSchedule
from app.db.repositories import inventory as inventory_repo
from app.classifier.labels import SensitivityLabel

#: Version string stored in every constraint snapshot for this ranker.
RANKER_VERSION = "migration-ranker-0.1.0"

_LABEL_WEIGHT = {
    SensitivityLabel.PUBLIC: Decimal("0.10"),
    SensitivityLabel.INTERNAL: Decimal("0.35"),
    SensitivityLabel.CONFIDENTIAL: Decimal("0.70"),
    SensitivityLabel.RESTRICTED: Decimal("1.00"),
}


@dataclass(frozen=True)
class MigrationCandidate:
    """One document considered for post-quantum upgrade."""

    document_id: UUID
    filename: str
    score: float
    cost: float
    profile_type: CryptoProfileType | None
    sensitivity_label: str | None
    trust_score: str | None
    risk_value: str | None


def _candidate_score(snapshot: inventory_repo.DocumentSnapshot) -> float:
    label = snapshot.sensitivity_label
    label_w = float(_LABEL_WEIGHT.get(label, Decimal("0.50"))) if label else 0.50
    trust = float(snapshot.trust.consensus_value) if snapshot.trust else 0.50
    # Lower trust and higher sensitivity → upgrade sooner.
    risk = float(snapshot.risk.risk_value) if snapshot.risk else 0.20
    return round((1.0 - trust) * 0.5 + label_w * 0.3 + risk * 0.2, 6)


def _candidate_cost(snapshot: inventory_repo.DocumentSnapshot) -> float:
    """Unit cost placeholder: restricted / hybrid / PQ already cost more effort."""
    base = 1.0
    if snapshot.profile is None:
        return base
    if snapshot.profile.profile_type is CryptoProfileType.POST_QUANTUM:
        return 0.0  # already at full PQ
    if snapshot.profile.profile_type is CryptoProfileType.HYBRID:
        return 0.5
    return base


def collect_candidates(session: Session) -> list[MigrationCandidate]:
    """Build the closed candidate set from current document snapshots."""
    candidates: list[MigrationCandidate] = []
    for snap in inventory_repo.list_snapshots(session):
        cost = _candidate_cost(snap)
        if cost <= 0:
            continue
        if snap.profile is None:
            continue
        candidates.append(
            MigrationCandidate(
                document_id=snap.document.id,
                filename=snap.document.filename,
                score=_candidate_score(snap),
                cost=cost,
                profile_type=snap.profile.profile_type,
                sensitivity_label=(
                    snap.sensitivity_label.value if snap.sensitivity_label else None
                ),
                trust_score=(
                    str(snap.trust.consensus_value) if snap.trust is not None else None
                ),
                risk_value=(
                    str(snap.risk.risk_value) if snap.risk is not None else None
                ),
            )
        )
    return candidates


def replace_schedule(
    session: Session,
    *,
    ordered: list[MigrationCandidate],
    constraint_snapshot: dict[str, Any],
    window_days: int = 30,
) -> list[MigrationSchedule]:
    """Replace pending schedule rows with a new ranking.

    Prior ``pending`` rows for ranked documents are marked ``done`` so history
    is retained without UPDATEing priority on an old row. New ranks are inserts.

    ``window_days`` spreads ``scheduled_upgrade_date`` from today across the
    window: rank 1 is soonest, last rank lands at ``today + (window_days - 1)``.
    """
    from datetime import date, timedelta

    from sqlalchemy import select

    from app.db.models import MigrationSchedule as MS

    if window_days <= 0:
        raise ValueError("window_days must be positive")

    pending = list(
        session.scalars(select(MS).where(MS.status == MigrationStatus.PENDING)).all()
    )
    for row in pending:
        row.status = MigrationStatus.DONE
    session.flush()

    today = date.today()
    span = max(window_days - 1, 0)
    last_index = max(len(ordered) - 1, 1)

    created: list[MigrationSchedule] = []
    for rank, item in enumerate(ordered, start=1):
        if len(ordered) == 1:
            day_offset = 0
        else:
            day_offset = int(round((rank - 1) * span / last_index))
        row = MigrationSchedule(
            document_id=item.document_id,
            priority_rank=rank,
            scheduled_upgrade_date=today + timedelta(days=day_offset),
            status=MigrationStatus.PENDING,
            constraint_snapshot=constraint_snapshot,
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created
