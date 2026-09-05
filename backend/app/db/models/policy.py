"""``policy_rules`` and ``policy_decisions``, ``SPEC.md`` 3.6."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, jsonb_column, uuid_primary_key
from app.db.enums import PolicyAction
from app.db.types import POLICY_ACTION


class PolicyRule(Base):
    """A deterministic rule that can override an AI recommendation, ``PRD.md`` FR-5."""

    __tablename__ = "policy_rules"
    __table_args__ = (
        CheckConstraint("priority > 0", name="priority_positive"),
        # Two ACTIVE rules cannot share a priority. Without this, evaluation
        # order between equal-priority rules is undefined, which for the module
        # that gates security decisions means the outcome depends on the query
        # plan. The team's own Sprint 3 defect log recorded exactly this as an
        # open defect (DEF-10) to be fixed in the rule builder UI; enforcing it
        # here instead means no UI can bypass it.
        #
        # Partial, on active rules only, so a superseded rule can be
        # deactivated and keep its historical priority rather than having to be
        # renumbered or deleted.
        Index(
            "uq_policy_rules_active_priority",
            "priority",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    rule_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    condition_expr: Mapped[dict[str, Any]] = jsonb_column()
    action: Mapped[PolicyAction] = mapped_column(POLICY_ACTION, nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = created_timestamp()


class PolicyDecision(Base):
    """The outcome of one pass through the policy gate, ``PRD.md`` FR-5."""

    __tablename__ = "policy_decisions"
    __table_args__ = (
        # Keeps the summary flag from drifting away from the two columns it
        # summarises. IS DISTINCT FROM rather than <> so the comparison is
        # well-defined even if a null ever reaches it.
        CheckConstraint(
            "overridden = (final_decision IS DISTINCT FROM ai_recommendation)",
            name="overridden_matches_decision",
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("policy_rules.id", ondelete="RESTRICT"),
        # NULLABLE, and this is the common case, not an edge case: "no rule
        # fired, the AI recommendation stood" (SPEC.md 3.6, PRD.md FR-5). Do not
        # invent a placeholder no-op rule row to satisfy a NOT NULL here.
        nullable=True,
        index=True,
    )
    ai_recommendation: Mapped[PolicyAction] = mapped_column(
        POLICY_ACTION, nullable=False
    )
    final_decision: Mapped[PolicyAction] = mapped_column(POLICY_ACTION, nullable=False)
    overridden: Mapped[bool] = mapped_column(nullable=False)
    decided_at: Mapped[datetime] = created_timestamp(index=True)
