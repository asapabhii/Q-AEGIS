"""Row builders for the database tests.

Plain functions rather than a factory library: the schema's foreign keys mean a
``crypto_profiles`` row needs a user, a document, a risk score, and a trust score
behind it, and spelling that chain out once here keeps each test focused on the
one behavior it is checking.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import (
    AgentType,
    CryptoProfileType,
    MigrationStatus,
    PolicyAction,
    SensitivityLabel,
    UserRole,
)
from app.db.models import (
    AgentOutput,
    ClassificationMetadata,
    CryptoProfile,
    Document,
    ManualOverride,
    MigrationSchedule,
    PolicyDecision,
    PolicyRule,
    RiskScore,
    TrustScore,
    User,
)


def make_user(session: Session, *, email: str, role: UserRole) -> User:
    """Create a user with an explicit email, for uniqueness tests."""
    user = User(name="Test User", email=email, role=role)
    session.add(user)
    session.flush()
    return user


def make_classification(
    session: Session,
    document: Document,
    *,
    label: SensitivityLabel = SensitivityLabel.CONFIDENTIAL,
    confidence: str = "0.7500",
    is_defaulted: bool = False,
    model_version: str = "test-model-0.1.0",
) -> ClassificationMetadata:
    """Create one ``classification_metadata`` row."""
    row = ClassificationMetadata(
        document_id=document.id,
        sensitivity_label=label,
        confidence_score=Decimal(confidence),
        model_version=model_version,
        is_defaulted=is_defaulted,
    )
    session.add(row)
    session.flush()
    return row


def make_override(
    session: Session,
    document: Document,
    user_id: UUID,
    *,
    justification: str = "Reviewed with the data owner and reclassified.",
    original: SensitivityLabel = SensitivityLabel.INTERNAL,
    new: SensitivityLabel = SensitivityLabel.RESTRICTED,
) -> ManualOverride:
    """Create one ``manual_overrides`` row."""
    row = ManualOverride(
        document_id=document.id,
        overridden_by=user_id,
        original_label=original,
        new_label=new,
        justification=justification,
    )
    session.add(row)
    session.flush()
    return row


def make_risk_score(
    session: Session, document: Document, *, risk_value: str = "0.400"
) -> RiskScore:
    """Create one ``risk_scores`` row."""
    row = RiskScore(
        document_id=document.id,
        risk_value=Decimal(risk_value),
        model_version="contextual-risk-additive-0.1.0",
        context_snapshot={
            "actor_user_id": str(document.uploaded_by),
            "device_id": "test-device",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00+00:00",
            "after_hours": False,
        },
    )
    session.add(row)
    session.flush()
    return row


def make_agent_output(
    session: Session,
    risk_score: RiskScore,
    *,
    agent_type: AgentType = AgentType.SECURITY,
    score: str = "0.700",
) -> AgentOutput:
    """Create one ``agent_outputs`` row."""
    row = AgentOutput(
        risk_score_id=risk_score.id,
        agent_type=agent_type,
        score=Decimal(score),
        rationale="Test rationale.",
    )
    session.add(row)
    session.flush()
    return row


def make_trust_score(
    session: Session,
    document: Document,
    risk_score: RiskScore,
    *,
    consensus_value: str = "0.650",
) -> TrustScore:
    """Create one ``trust_scores`` row."""
    row = TrustScore(
        document_id=document.id,
        risk_score_id=risk_score.id,
        consensus_value=Decimal(consensus_value),
        consensus_version="weighted-mean-0.1",
    )
    session.add(row)
    session.flush()
    return row


def make_crypto_profile(
    session: Session,
    document: Document,
    trust_score: TrustScore,
    *,
    profile_type: CryptoProfileType = CryptoProfileType.HYBRID,
) -> CryptoProfile:
    """Create one ``crypto_profiles`` row."""
    row = CryptoProfile(
        document_id=document.id,
        trust_score_id=trust_score.id,
        profile_type=profile_type,
    )
    session.add(row)
    session.flush()
    return row


def make_policy_rule(
    session: Session,
    user_id: UUID,
    *,
    rule_name: str = "Deny restricted below trust threshold",
    priority: int = 10,
    active: bool = True,
    action: PolicyAction = PolicyAction.DENY,
) -> PolicyRule:
    """Create one ``policy_rules`` row."""
    row = PolicyRule(
        rule_name=rule_name,
        condition_expr={"all": [{"field": "label", "op": "eq", "value": "RESTRICTED"}]},
        action=action,
        priority=priority,
        active=active,
        created_by=user_id,
    )
    session.add(row)
    session.flush()
    return row


def make_policy_decision(
    session: Session,
    document: Document,
    *,
    rule_id: UUID | None = None,
    ai_recommendation: PolicyAction = PolicyAction.ALLOW,
    final_decision: PolicyAction | None = None,
) -> PolicyDecision:
    """Create one ``policy_decisions`` row.

    ``overridden`` is derived rather than passed, because the table's CHECK
    constraint requires it to agree with the two decision columns. A test that
    needs them to disagree sets it explicitly instead of going through here.
    """
    decision = final_decision if final_decision is not None else ai_recommendation
    row = PolicyDecision(
        document_id=document.id,
        rule_id=rule_id,
        ai_recommendation=ai_recommendation,
        final_decision=decision,
        overridden=decision != ai_recommendation,
    )
    session.add(row)
    session.flush()
    return row


def make_migration_entry(
    session: Session,
    document: Document,
    *,
    priority_rank: int = 1,
    status: MigrationStatus = MigrationStatus.PENDING,
) -> MigrationSchedule:
    """Create one ``migration_schedule`` row."""
    row = MigrationSchedule(
        document_id=document.id,
        priority_rank=priority_rank,
        status=status,
        constraint_snapshot={"budget": 1000, "window_days": 30},
    )
    session.add(row)
    session.flush()
    return row
