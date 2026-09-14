"""Pydantic models for migration ranking, ``SPEC.md`` 3.10 / FR-9."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MigrationRankRequest(BaseModel):
    """Budgeted ranking request. Extra keys forbidden."""

    model_config = ConfigDict(extra="forbid")

    budget: float = Field(gt=0, description="Max total upgrade cost units")
    window_days: int = Field(default=30, gt=0, le=3650)
    seed: int = Field(default=42)


class BaselineComparison(BaseModel):
    """One method's totals on the shared constraint set."""

    model_config = ConfigDict(extra="forbid")

    method: str
    selected_ids: list[UUID]
    total_score: float
    total_cost: float


class MigrationScheduleItem(BaseModel):
    """One persisted queue row."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    document_id: UUID
    priority_rank: int
    scheduled_upgrade_date: date | None
    status: str
    constraint_snapshot: dict[str, Any]


class MigrationRankResponse(BaseModel):
    """QAOA schedule plus baseline comparison (FR-9)."""

    model_config = ConfigDict(extra="forbid")

    schedule: list[MigrationScheduleItem]
    primary: BaselineComparison
    baselines: list[BaselineComparison]
    constraint_snapshot: dict[str, Any]
    ranked_at: datetime
