"""Dry-run a candidate rule against historical gate snapshots, ``PRD.md`` FR-13.

The candidate is not persisted. Live ``policy_rules`` are not consulted. Each
snapshot is the audit payload from a prior ``policy_decision_recorded`` event,
so a later reclassify cannot rewrite what the test sees.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.classifier.labels import SensitivityLabel
from app.db.enums import PolicyAction
from app.db.models import AuditLog
from app.policy.engine import EvaluableRule, evaluate
from app.policy.schemas import facts_from_audit_payload


@dataclass(frozen=True)
class RuleReplay:
    """One historical decision replayed against the candidate rule."""

    decision_id: UUID
    document_id: UUID
    decided_at: datetime
    sensitivity_label: SensitivityLabel
    recorded_final_decision: PolicyAction
    would_match: bool
    hypothetical_final_decision: PolicyAction
    would_change_outcome: bool


@dataclass(frozen=True)
class DryRunResult:
    """Windowed replay. ``skipped`` could not be reconstructed from the payload."""

    considered: int
    skipped: int
    replays: list[RuleReplay]


def replay_candidate(
    *,
    condition_expr: dict[str, Any],
    action: PolicyAction,
    snapshots: list[AuditLog],
) -> DryRunResult:
    """Evaluate the candidate alone against each snapshot.

    A match means this rule's condition holds on that historical fact set.
    ``hypothetical_final_decision`` is the candidate action on a match, else
    the recorded AI recommendation — not a replay of the live first-match set.
    """
    candidate = EvaluableRule(
        id=uuid4(),
        rule_name="candidate",
        action=action,
        condition=condition_expr,
    )
    replays: list[RuleReplay] = []
    skipped = 0
    for entry in snapshots:
        replay = _replay_one(candidate, entry)
        if replay is None:
            skipped += 1
            continue
        replays.append(replay)
    return DryRunResult(considered=len(snapshots), skipped=skipped, replays=replays)


def _replay_one(candidate: EvaluableRule, entry: AuditLog) -> RuleReplay | None:
    """Return one replay, or ``None`` when the payload is not a v1 snapshot."""
    facts = facts_from_audit_payload(entry.payload)
    if facts is None:
        return None
    raw_decision_id = entry.payload.get("policy_decision_id")
    raw_document_id = entry.payload.get("document_id")
    raw_recorded = entry.payload.get("final_decision")
    try:
        decision_id = UUID(str(raw_decision_id))
        document_id = UUID(str(raw_document_id))
        recorded = PolicyAction(str(raw_recorded))
        label = SensitivityLabel(facts.sensitivity_label)
    except (TypeError, ValueError):
        return None
    result = evaluate(facts, [candidate])
    hypothetical = result.final_decision
    return RuleReplay(
        decision_id=decision_id,
        document_id=document_id,
        decided_at=entry.created_at,
        sensitivity_label=label,
        recorded_final_decision=recorded,
        would_match=result.rule_id is not None,
        hypothetical_final_decision=hypothetical,
        would_change_outcome=hypothetical != recorded,
    )
