"""Policy rule authoring and evaluation, ``SPEC.md`` 3.6, ``PRD.md`` FR-5."""

from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    DbSession,
    PolicyDecisionCaller,
    PolicyRuleCaller,
    resolve_seeded_actor,
)
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import overrides as override_repo
from app.db.repositories import policy as policy_repo
from app.db.repositories import risk as risk_repo
from app.db.repositories import trust as trust_repo
from app.policy.dry_run import replay_candidate
from app.policy.engine import PolicyEngineError, evaluate
from app.policy.schemas import (
    PolicyDecisionRequest,
    PolicyDecisionResponse,
    PolicyRuleCreateRequest,
    PolicyRuleResponse,
    PolicyRuleTestReplay,
    PolicyRuleTestResponse,
    facts_from_persisted,
)
from app.trust_engine.recommendation import recommend_from_consensus

router = APIRouter(tags=["policy"])


@router.post(
    "/policy-rules/test",
    response_model=PolicyRuleTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Dry-run a candidate rule against recent decisions",
)
def test_policy_rule(
    request: PolicyRuleCreateRequest,
    session: DbSession,
    caller: PolicyRuleCaller,
) -> PolicyRuleTestResponse:
    """Evaluate the candidate against the last ``TEST_RULE_WINDOW`` decisions.

    The rule is not stored. No ``policy_decisions`` row is written. No audit
    entry is written. Live rules are not consulted. Facts come from each
    decision's audit payload, not from current classification or trust.

    Raises:
        HTTPException: 500 if the WASM evaluator fails on the candidate itself.
    """
    resolve_seeded_actor(session, caller)
    snapshots = policy_repo.list_recent_decision_audits(
        session, limit=policy_repo.TEST_RULE_WINDOW
    )
    try:
        result = replay_candidate(
            condition_expr=request.condition_expr,
            action=request.action,
            snapshots=snapshots,
        )
    except PolicyEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return PolicyRuleTestResponse(
        rule_name=request.rule_name,
        action=request.action,
        priority=request.priority,
        condition_expr=request.condition_expr,
        window=policy_repo.TEST_RULE_WINDOW,
        considered=result.considered,
        skipped=result.skipped,
        replays=[
            PolicyRuleTestReplay(
                decision_id=item.decision_id,
                document_id=item.document_id,
                decided_at=item.decided_at,
                sensitivity_label=item.sensitivity_label,
                recorded_final_decision=item.recorded_final_decision,
                would_match=item.would_match,
                hypothetical_final_decision=item.hypothetical_final_decision,
                would_change_outcome=item.would_change_outcome,
            )
            for item in result.replays
        ],
    )


@router.post(
    "/policy-rules",
    response_model=PolicyRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Author a policy override rule",
)
def create_policy_rule(
    request: PolicyRuleCreateRequest,
    session: DbSession,
    caller: PolicyRuleCaller,
) -> PolicyRuleResponse:
    """Persist one active rule. The tree was already validated on the request.

    Raises:
        HTTPException: 409 if the name or active priority is already taken.
    """
    actor = resolve_seeded_actor(session, caller)
    try:
        row = policy_repo.insert_rule(
            session,
            rule_name=request.rule_name,
            condition_expr=request.condition_expr,
            action=request.action,
            priority=request.priority,
            created_by=actor.id,
        )
    except IntegrityError as exc:
        _raise_rule_conflict(exc)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.POLICY_RULE_CREATED.value,
        document_id=None,
        actor_id=actor.id,
        payload=policy_repo.rule_created_audit_payload(rule=row),
    )
    return PolicyRuleResponse(
        id=row.id,
        rule_name=row.rule_name,
        condition_expr=row.condition_expr,
        action=row.action,
        priority=row.priority,
        active=row.active,
        created_at=row.created_at,
    )


@router.post(
    "/policy-decisions",
    response_model=PolicyDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate the policy gate from a persisted trust score",
)
def evaluate_policy(
    request: PolicyDecisionRequest,
    session: DbSession,
    caller: PolicyDecisionCaller,
) -> PolicyDecisionResponse:
    """Evaluate active rules, persist the decision, and write the audit entry.

    ``final_decision`` is computed here. It is not accepted from the client.
    ``sensitivity_label`` is the effective label (latest override, else latest
    classification). ``risk_value`` and ``trust_score`` come from the risk row
    behind this trust score and the trust row itself. ``ai_recommendation`` may
    be supplied by the client or derived from the consensus when omitted.

    Raises:
        HTTPException: 404 if the trust score is unknown, 422 if classification
            or the linked risk score is missing or a stored rule's tree is
            corrupt, 500 if the WASM evaluator fails.
    """
    trust_row = trust_repo.get_trust_score(session, request.trust_score_id)
    if trust_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_trust_score_detail(request.trust_score_id),
        )

    risk_row = risk_repo.get_risk_score(session, trust_row.risk_score_id)
    if risk_row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "No risk score is linked to this trust score. Compute one first "
                "via POST /api/v1/risk-scores."
            ),
        )
    if risk_row.document_id != trust_row.document_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "This trust score's risk row belongs to a different document. "
                "Score a new contextual risk row and recompute consensus."
            ),
        )

    effective = override_repo.effective_for_document(session, trust_row.document_id)
    if effective is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "No classification recorded for this document. Classify it "
                "first via POST /api/v1/classify."
            ),
        )

    ai_recommendation = request.ai_recommendation
    if ai_recommendation is None:
        ai_recommendation = recommend_from_consensus(trust_row.consensus_value)

    facts = facts_from_persisted(
        sensitivity_label=effective.label,
        risk=risk_row,
        trust=trust_row,
        ai_recommendation=ai_recommendation,
    )

    actor = resolve_seeded_actor(session, caller)
    stored = policy_repo.list_active_rules(session)
    try:
        rules = [policy_repo.as_evaluable(row) for row in stored]
        result = evaluate(facts, rules)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "An active policy rule has a condition_expr this version cannot "
                f"interpret: {exc}"
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PolicyEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    row = policy_repo.append_decision(
        session, document_id=trust_row.document_id, result=result
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.POLICY_DECISION_RECORDED.value,
        document_id=trust_row.document_id,
        actor_id=actor.id,
        payload=policy_repo.decision_audit_payload(
            document_id=trust_row.document_id,
            result=result,
            decision_id=row.id,
            facts=facts.as_json(),
            trust_score_id=trust_row.id,
            risk_score_id=risk_row.id,
            classification_id=effective.classification.id,
            override_id=effective.override_id,
            label_source=effective.source,
        ),
    )
    return PolicyDecisionResponse.from_row(
        decision_id=row.id,
        document_id=trust_row.document_id,
        trust_score_id=trust_row.id,
        risk_score_id=risk_row.id,
        classification_id=effective.classification.id,
        override_id=effective.override_id,
        label_source=effective.source,
        facts=facts,
        result=result,
        decided_at=row.decided_at,
        risk_value=risk_row.risk_value,
        trust_score=trust_row.consensus_value,
    )


def _raise_rule_conflict(exc: IntegrityError) -> None:
    """Map unique-constraint failures onto 409, not 500."""
    orig = exc.orig
    if isinstance(orig, psycopg.errors.UniqueViolation):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A rule with this name already exists, or another active rule "
                "already has this priority."
            ),
        ) from exc
    raise exc


def _unknown_trust_score_detail(trust_score_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No trust score with id {trust_score_id}. Compute one first via "
        "POST /api/v1/trust-scores."
    )
