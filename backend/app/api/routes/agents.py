"""Agent output deep-dive reads for dashboard / CISO views."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import DbSession, DocumentInventoryCaller
from app.db.enums import AgentType
from app.db.models import AgentOutput, RiskScore
from app.db.repositories import documents as documents_repo

router = APIRouter(tags=["agents"])


class AgentOutputItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    agent_type: AgentType
    score: Decimal
    rationale: str


class AgentDeepDiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    risk_score_id: UUID | None = None
    assessed_at: datetime | None = None
    agents: list[AgentOutputItem] = Field(default_factory=list)
    missing_agents: list[AgentType] = Field(default_factory=list)
    note: str | None = None


@router.get(
    "/documents/{document_id}/agents",
    response_model=AgentDeepDiveResponse,
    summary="Latest agent scores and rationales for one document",
)
def get_document_agents(
    document_id: UUID,
    session: DbSession,
    _caller: DocumentInventoryCaller,
) -> AgentDeepDiveResponse:
    """Return the newest assessment's five agent outputs, noting gaps."""
    document = documents_repo.get_document(session, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )

    risk = session.scalars(
        select(RiskScore)
        .where(RiskScore.document_id == document_id)
        .order_by(RiskScore.computed_at.desc(), RiskScore.id.desc())
        .limit(1)
    ).one_or_none()
    if risk is None:
        return AgentDeepDiveResponse(
            document_id=document_id,
            note="No risk assessment has been recorded for this document yet.",
            missing_agents=list(AgentType),
        )

    rows = list(
        session.scalars(
            select(AgentOutput)
            .where(AgentOutput.risk_score_id == risk.id)
            .order_by(AgentOutput.agent_type.asc())
        ).all()
    )
    present = {row.agent_type for row in rows}
    missing = [agent for agent in AgentType if agent not in present]
    return AgentDeepDiveResponse(
        document_id=document_id,
        risk_score_id=risk.id,
        assessed_at=risk.computed_at,
        agents=[
            AgentOutputItem(
                id=row.id,
                agent_type=row.agent_type,
                score=row.score,
                rationale=row.rationale,
            )
            for row in rows
        ],
        missing_agents=missing,
        note=(
            "One or more agents did not produce an output for this assessment."
            if missing
            else None
        ),
    )
