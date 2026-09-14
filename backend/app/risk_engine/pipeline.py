"""End-to-end P0 assessment: risk → agents → trust → policy → crypto → encrypt.

Orchestrates existing module boundaries rather than merging them. Each stage
still writes its own history row and audit entry. ``SPEC.md`` 3.4 supplies
agent scores; the gate may derive ``ai_recommendation`` from consensus.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents import AssessmentInput, run_assessment
from app.crypto.engine import encrypt_document_bytes
from app.crypto.selector import select_crypto_profile
from app.db.enums import AuditEventType, CryptoProfileType, PolicyAction
from app.db.models import User
from app.db.repositories import audit as audit_repo
from app.db.repositories import ciphertexts as ciphertext_repo
from app.db.repositories import crypto as crypto_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import overrides as override_repo
from app.db.repositories import policy as policy_repo
from app.db.repositories import risk as risk_repo
from app.db.repositories import trust as trust_repo
from app.event_bus import EventType, publish_event
from app.policy.engine import evaluate
from app.policy.schemas import facts_from_persisted
from app.risk_engine.scorer import ContextSnapshot, score
from app.trust_engine.consensus import IncompleteAgentSetError, combine
from app.trust_engine.recommendation import (
    RECOMMENDATION_VERSION,
    recommend_from_consensus,
)


@dataclass(frozen=True)
class AssessmentResult:
    """Ids and outcomes from one full pipeline pass."""

    document_id: UUID
    risk_score_id: UUID
    trust_score_id: UUID
    consensus_value: Decimal
    ai_recommendation: PolicyAction
    policy_decision_id: UUID
    final_decision: PolicyAction
    overridden: bool
    crypto_profile_id: UUID
    profile_type: CryptoProfileType
    ciphertext_id: UUID | None
    encrypted: bool
    reselected: bool


def run_full_assessment(
    session: Session,
    *,
    document_id: UUID,
    actor: User,
    snapshot: ContextSnapshot,
    plaintext: bytes | None = None,
    ai_recommendation: PolicyAction | None = None,
) -> AssessmentResult:
    """Run risk → agents → trust → policy → crypto, optionally encrypting bytes.

    Raises:
        LookupError: document missing.
        ValueError: classification missing or incomplete agents.
        IncompleteAgentSetError: agent set not exactly five types.
        PolicyEngineError / ValidationError: from the gate (caller maps to HTTP).
        CryptoConfigurationError / LiboqsUnavailableError: encrypt path.
        IntegrityError: duplicate agent outputs for the same risk row.
    """
    document = documents_repo.get_document(session, document_id)
    if document is None:
        raise LookupError(f"No document registered with id {document_id}.")

    effective = override_repo.effective_for_document(session, document_id)
    if effective is None:
        raise ValueError(
            "No classification recorded for this document. Classify it first."
        )

    prior_profile = crypto_repo.latest_for_document(session, document_id)

    risk_result = score(snapshot)
    risk_row = risk_repo.append_risk_score(
        session, document_id=document.id, result=risk_result
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.RISK_SCORE_COMPUTED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=risk_repo.risk_score_audit_payload(
            document_id=document.id,
            result=risk_result,
            risk_score_id=risk_row.id,
        ),
    )

    agent_outputs = run_assessment(
        AssessmentInput(
            sensitivity_label=effective.label,
            risk_value=risk_result.risk_value,
            filename=document.filename,
            context_snapshot=snapshot,
        )
    )
    try:
        trust_result = combine(list(agent_outputs))
    except IncompleteAgentSetError as exc:
        raise ValueError(str(exc)) from exc

    output_rows = trust_repo.append_agent_outputs(
        session, risk_score_id=risk_row.id, outputs=trust_result.outputs
    )
    trust_row = trust_repo.append_trust_score(
        session,
        document_id=document.id,
        risk_score_id=risk_row.id,
        result=trust_result,
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.TRUST_SCORE_UPDATED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=trust_repo.trust_score_audit_payload(
            document_id=document.id,
            risk_score_id=risk_row.id,
            result=trust_result,
            trust_score_id=trust_row.id,
            output_ids=[item.id for item in output_rows],
        ),
    )
    publish_event(
        EventType.TRUST_UPDATED,
        {
            "document_id": str(document.id),
            "trust_score_id": str(trust_row.id),
            "consensus_value": str(trust_result.consensus_value),
        },
    )

    recommendation = ai_recommendation or recommend_from_consensus(
        trust_result.consensus_value
    )
    facts = facts_from_persisted(
        sensitivity_label=effective.label,
        risk=risk_row,
        trust=trust_row,
        ai_recommendation=recommendation,
    )
    stored_rules = policy_repo.list_active_rules(session)
    rules = [policy_repo.as_evaluable(row) for row in stored_rules]
    policy_result = evaluate(facts, rules)
    decision_row = policy_repo.append_decision(
        session, document_id=document.id, result=policy_result
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.POLICY_DECISION_RECORDED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload={
            **policy_repo.decision_audit_payload(
                document_id=document.id,
                result=policy_result,
                decision_id=decision_row.id,
                facts=facts.as_json(),
                trust_score_id=trust_row.id,
                risk_score_id=risk_row.id,
                classification_id=effective.classification.id,
                override_id=effective.override_id,
                label_source=effective.source,
            ),
            "recommendation_version": RECOMMENDATION_VERSION,
        },
    )

    profile_type = select_crypto_profile(float(trust_result.consensus_value))
    reselected = (
        prior_profile is not None and prior_profile.profile_type != profile_type
    )
    profile_row = crypto_repo.append_profile(
        session,
        document_id=document.id,
        trust_score_id=trust_row.id,
        profile_type=profile_type,
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.CRYPTO_PROFILE_SELECTED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=crypto_repo.profile_selected_audit_payload(
            document_id=document.id,
            trust_score_id=trust_row.id,
            crypto_profile_id=profile_row.id,
            profile_type=profile_type,
            consensus_value=trust_result.consensus_value,
            consensus_version=trust_result.consensus_version,
        ),
    )

    ciphertext_id: UUID | None = None
    encrypted = False
    if plaintext is not None:
        encrypt_result = encrypt_document_bytes(plaintext, profile_type)
        cipher_row = ciphertext_repo.append_ciphertext(
            session,
            document_id=document.id,
            crypto_profile_id=profile_row.id,
            result=encrypt_result,
        )
        documents_repo.mark_protected(session, document)
        ciphertext_id = cipher_row.id
        encrypted = True

    return AssessmentResult(
        document_id=document.id,
        risk_score_id=risk_row.id,
        trust_score_id=trust_row.id,
        consensus_value=trust_result.consensus_value,
        ai_recommendation=recommendation,
        policy_decision_id=decision_row.id,
        final_decision=policy_result.final_decision,
        overridden=policy_result.overridden,
        crypto_profile_id=profile_row.id,
        profile_type=profile_type,
        ciphertext_id=ciphertext_id,
        encrypted=encrypted,
        reselected=reselected,
    )
