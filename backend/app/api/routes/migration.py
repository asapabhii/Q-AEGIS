"""Migration ranking API, ``SPEC.md`` 3.10, ``PRD.md`` FR-9."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, MigrationCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.scheduler.rank import migration_audit_payload, rank_and_persist
from app.scheduler.schemas import (
    BaselineComparison,
    MigrationRankRequest,
    MigrationRankResponse,
    MigrationScheduleItem,
)

router = APIRouter(tags=["migration"])


@router.post(
    "/migration-schedule/rank",
    response_model=MigrationRankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rank documents for PQ migration (QAOA + baselines)",
)
def rank_migration(
    request: MigrationRankRequest,
    session: DbSession,
    caller: MigrationCaller,
) -> MigrationRankResponse:
    """Run QAOA and classical baselines on one constraint set; persist QAOA order.

    Does not claim QAOA is superior — baseline totals are returned so the
    comparison required by FR-9 / Risk R3 is visible in the same response.
    """
    try:
        outcome = rank_and_persist(
            session,
            budget=request.budget,
            window_days=request.window_days,
            seed=request.seed,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    actor = resolve_seeded_actor(session, caller)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.MIGRATION_SCHEDULED.value,
        document_id=None,
        actor_id=actor.id,
        payload=migration_audit_payload(
            outcome=outcome,
            schedule_ids=[row.id for row in outcome.rows],
        ),
    )

    def _cmp(result) -> BaselineComparison:
        return BaselineComparison(
            method=result.method,
            selected_ids=[UUID(item) for item in result.selected_ids],
            total_score=result.total_score,
            total_cost=result.total_cost,
        )

    return MigrationRankResponse(
        schedule=[
            MigrationScheduleItem(
                id=row.id,
                document_id=row.document_id,
                priority_rank=row.priority_rank,
                status=row.status.value,
                constraint_snapshot=row.constraint_snapshot,
            )
            for row in outcome.rows
        ],
        primary=_cmp(outcome.primary),
        baselines=[_cmp(item) for item in outcome.baselines],
        constraint_snapshot=outcome.constraint_snapshot,
        ranked_at=datetime.now(timezone.utc),
    )
