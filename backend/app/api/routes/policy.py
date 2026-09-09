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
from app.db.repositories import documents as documents_repo
from app.db.repositories import policy as policy_repo
from app.policy.engine import PolicyEngineError, evaluate
from app.policy.schemas import (
    PolicyDecisionRequest,
    PolicyDecisionResponse,
    PolicyRuleCreateRequest,
    PolicyRuleResponse,
)

router = APIRouter(tags=["policy"])


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
    summary="Evaluate the policy gate for a registered document",
)
def evaluate_policy(
    request: PolicyDecisionRequest,
    session: DbSession,
    caller: PolicyDecisionCaller,
) -> PolicyDecisionResponse:
    """Evaluate active rules, persist the decision, and write the audit entry.

    ``final_decision`` is computed here. It is not accepted from the client.
    ``trust_score`` and ``ai_recommendation`` are still caller-supplied; this
    endpoint does not read ``trust_scores``.

    Raises:
        HTTPException: 404 if the document is not registered, 422 if a stored
            rule's tree is corrupt, 500 if the WASM evaluator fails.
    """
    document = documents_repo.get_document(session, request.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_document_detail(request.document_id),
        )

    actor = resolve_seeded_actor(session, caller)
    stored = policy_repo.list_active_rules(session)
    try:
        rules = [policy_repo.as_evaluable(row) for row in stored]
        result = evaluate(request.facts(), rules)
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

    row = policy_repo.append_decision(session, document_id=document.id, result=result)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.POLICY_DECISION_RECORDED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=policy_repo.decision_audit_payload(
            document_id=document.id,
            result=result,
            decision_id=row.id,
            facts=request.facts().as_json(),
        ),
    )
    return PolicyDecisionResponse.from_row(
        decision_id=row.id,
        document_id=document.id,
        result=result,
        decided_at=row.decided_at,
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


def _unknown_document_detail(document_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No document registered with id {document_id}. Register it first via "
        "POST /api/v1/documents."
    )
