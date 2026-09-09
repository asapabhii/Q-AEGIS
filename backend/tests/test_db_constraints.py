"""Schema constraints, ``SPEC.md`` Section 5, ``docs/data-dictionary.md``.

Each constraint here encodes a requirement that would otherwise depend on every
caller remembering it. A value the database refuses is a value no code path can
store, including a migration, a psql session, or a service written later in
another language.
"""

from decimal import Decimal

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import PolicyAction, SensitivityLabel, UserRole
from app.db.models import Document, PolicyDecision
from app.db.models.classification import MIN_JUSTIFICATION_CHARS
from tests import factories
from tests.test_db_append_only import statement_expected_to_fail


def assert_check_violation(exc_info: pytest.ExceptionInfo, constraint: str) -> None:
    """Assert a specific named CHECK constraint refused the write.

    Naming the constraint matters: without it a test passes when *any* error
    occurs, including a typo in the test itself.
    """
    assert isinstance(exc_info.value.orig, psycopg.errors.CheckViolation)
    assert constraint in str(exc_info.value.orig)


# --------------------------------------------------------------------------
# Score ranges
# --------------------------------------------------------------------------


@pytest.mark.parametrize("confidence", ["1.5000", "-0.0001"])
def test_confidence_score_must_be_a_probability(
    db_session: Session, registered_document: Document, confidence: str
) -> None:
    """A confidence outside 0 to 1 is not a confidence."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_classification(
                db_session, registered_document, confidence=confidence
            )

    assert_check_violation(exc_info, "confidence_score_range")


@pytest.mark.parametrize("boundary", ["0.0000", "1.0000"])
def test_confidence_score_accepts_both_boundaries(
    db_session: Session, registered_document: Document, boundary: str
) -> None:
    """The range is inclusive; zero confidence is a real, expected outcome.

    The classifier returns exactly 0.0 for content matching no rules, which is the
    case that triggers the fail-safe, so rejecting it would break the path that
    matters most.
    """
    row = factories.make_classification(
        db_session, registered_document, confidence=boundary
    )
    assert row.confidence_score == Decimal(boundary)


def test_risk_value_must_be_a_probability(
    db_session: Session, registered_document: Document
) -> None:
    """``risk_scores.risk_value`` is bounded the same way."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_risk_score(db_session, registered_document, risk_value="1.2")

    assert_check_violation(exc_info, "risk_value_range")


def test_agent_score_must_be_a_probability(
    db_session: Session, registered_document: Document
) -> None:
    """``agent_outputs.score`` is bounded the same way."""
    risk_score = factories.make_risk_score(db_session, registered_document)

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_agent_output(db_session, risk_score, score="1.001")

    assert_check_violation(exc_info, "score_range")


def test_consensus_value_must_be_a_probability(
    db_session: Session, registered_document: Document
) -> None:
    """``trust_scores.consensus_value`` is bounded the same way."""
    risk_score = factories.make_risk_score(db_session, registered_document)

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_trust_score(
                db_session, registered_document, risk_score, consensus_value="-0.1"
            )

    assert_check_violation(exc_info, "consensus_value_range")


# --------------------------------------------------------------------------
# Manual overrides, PRD.md FR-12
# --------------------------------------------------------------------------


def test_override_justification_has_a_minimum_length(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """FR-12's 20-character minimum is an acceptance criterion, not a UI hint."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_override(
                db_session,
                registered_document,
                seeded_users[UserRole.SECURITY_ANALYST].id,
                justification="too short",
            )

    assert_check_violation(exc_info, "justification_min_length")


def test_override_justification_accepts_exactly_the_minimum(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """The boundary is inclusive, matching FR-12's "at least 20 characters"."""
    row = factories.make_override(
        db_session,
        registered_document,
        seeded_users[UserRole.SECURITY_ANALYST].id,
        justification="x" * MIN_JUSTIFICATION_CHARS,
    )
    assert len(row.justification) == MIN_JUSTIFICATION_CHARS


def test_an_override_must_actually_change_the_label(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """FR-12 requires the new label to differ from the current one.

    An override to the same label is a no-op that would still be permanently
    logged as a human decision, which misrepresents what happened.
    """
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_override(
                db_session,
                registered_document,
                seeded_users[UserRole.SECURITY_ANALYST].id,
                original=SensitivityLabel.CONFIDENTIAL,
                new=SensitivityLabel.CONFIDENTIAL,
            )

    assert_check_violation(exc_info, "label_actually_changed")


# --------------------------------------------------------------------------
# Policy rules and decisions
# --------------------------------------------------------------------------


def test_rule_priority_must_be_positive(
    db_session: Session, seeded_users: dict
) -> None:
    """Lower means evaluated first, so zero and negatives have no defined place."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_policy_rule(
                db_session, seeded_users[UserRole.COMPLIANCE_OFFICER].id, priority=0
            )

    assert_check_violation(exc_info, "priority_positive")


def test_two_active_rules_cannot_share_a_priority(
    db_session: Session, seeded_users: dict
) -> None:
    """Closes DEF-10 from the team's Sprint 3 defect log at the schema level.

    Equal priorities left evaluation order undefined, which for the module that
    gates security decisions means the outcome depends on the query plan.
    """
    author = seeded_users[UserRole.COMPLIANCE_OFFICER].id
    factories.make_policy_rule(db_session, author, rule_name="first", priority=5)

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_policy_rule(
                db_session, author, rule_name="second", priority=5
            )

    assert isinstance(exc_info.value.orig, psycopg.errors.UniqueViolation)


def test_an_inactive_rule_may_reuse_an_active_priority(
    db_session: Session, seeded_users: dict
) -> None:
    """The index is partial on purpose.

    A superseded rule keeps its historical priority instead of being renumbered or
    deleted, which would lose the record of what it was.
    """
    author = seeded_users[UserRole.COMPLIANCE_OFFICER].id
    factories.make_policy_rule(db_session, author, rule_name="active", priority=5)
    retired = factories.make_policy_rule(
        db_session, author, rule_name="retired", priority=5, active=False
    )
    assert retired.priority == 5


def test_rule_names_are_unique(db_session: Session, seeded_users: dict) -> None:
    """``PRD.md`` FR-13 requires a unique rule name before a rule can be saved."""
    author = seeded_users[UserRole.COMPLIANCE_OFFICER].id
    factories.make_policy_rule(db_session, author, rule_name="Same name", priority=1)

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError):
            factories.make_policy_rule(
                db_session, author, rule_name="Same name", priority=2
            )


def test_a_decision_with_no_rule_is_valid(
    db_session: Session, registered_document: Document
) -> None:
    """ "No rule fired, the AI recommendation stood" is the common outcome.

    ``PRD.md`` FR-5 is explicit that this is a normal, correctly modelled result
    rather than a workaround, which is why ``rule_id`` is nullable.
    """
    decision = factories.make_policy_decision(db_session, registered_document)
    assert decision.rule_id is None
    assert decision.overridden is False


def test_the_overridden_flag_must_agree_with_the_decision(
    db_session: Session, registered_document: Document
) -> None:
    """Stops the summary flag from drifting away from what it summarises."""
    row = PolicyDecision(
        document_id=registered_document.id,
        rule_id=None,
        ai_recommendation=PolicyAction.ALLOW,
        final_decision=PolicyAction.DENY,
        # Wrong: the decision plainly differs from the recommendation.
        overridden=False,
    )

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.add(row)
            db_session.flush()

    assert_check_violation(exc_info, "overridden_matches_decision")


# --------------------------------------------------------------------------
# Uniqueness and referential integrity
# --------------------------------------------------------------------------


def test_one_output_per_agent_per_assessment(
    db_session: Session, registered_document: Document
) -> None:
    """A duplicate means an agent ran twice and consensus would double-count it."""
    risk_score = factories.make_risk_score(db_session, registered_document)
    factories.make_agent_output(db_session, risk_score)

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_agent_output(db_session, risk_score)

    assert isinstance(exc_info.value.orig, psycopg.errors.UniqueViolation)


def test_all_five_agents_can_score_one_assessment(
    db_session: Session, registered_document: Document
) -> None:
    """The uniqueness rule must not block the five-per-assessment normal case."""
    from app.db.enums import AgentType

    risk_score = factories.make_risk_score(db_session, registered_document)
    for agent_type in AgentType:
        factories.make_agent_output(db_session, risk_score, agent_type=agent_type)

    assert (
        db_session.execute(
            text("SELECT count(*) FROM agent_outputs WHERE risk_score_id = :id"),
            {"id": risk_score.id},
        ).scalar_one()
        == 5
    )


def test_user_emails_are_unique(db_session: Session) -> None:
    """``email`` is the login identity, so two users cannot share one."""
    factories.make_user(db_session, email="dup@example.test", role=UserRole.AUDITOR)

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError):
            factories.make_user(
                db_session, email="dup@example.test", role=UserRole.ENGINEER
            )


def test_a_user_with_documents_cannot_be_deleted(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """RESTRICT, not CASCADE.

    Cascading would take a user's documents and, through them, a chain of
    decisions and audit entries. A deletion that would orphan a document should
    fail and be dealt with deliberately.
    """
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": seeded_users[UserRole.DATA_OWNER].id},
            )

    assert isinstance(exc_info.value.orig, psycopg.errors.ForeignKeyViolation)


def test_a_classification_needs_a_real_document(db_session: Session) -> None:
    """The foreign key is what closed the "classify any invented UUID" gap."""
    from uuid import uuid4

    from app.db.models import ClassificationMetadata

    row = ClassificationMetadata(
        document_id=uuid4(),
        sensitivity_label=SensitivityLabel.PUBLIC,
        confidence_score=Decimal("0.9000"),
        model_version="test-0.1.0",
        is_defaulted=False,
    )

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.add(row)
            db_session.flush()

    assert isinstance(exc_info.value.orig, psycopg.errors.ForeignKeyViolation)


def test_migration_priority_rank_must_be_positive(
    db_session: Session, registered_document: Document
) -> None:
    """A rank of zero has no meaning in an ordering that starts at one."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            factories.make_migration_entry(
                db_session, registered_document, priority_rank=0
            )

    assert_check_violation(exc_info, "priority_rank_positive")


# --------------------------------------------------------------------------
# Defaults and server-side generation
# --------------------------------------------------------------------------


def test_ids_are_generated_by_the_database(
    db_session: Session, registered_document: Document
) -> None:
    """A client cannot choose a primary key, and neither can a raw SQL insert."""
    generated = db_session.execute(
        text(
            "INSERT INTO risk_scores "
            "(document_id, risk_value, model_version, context_snapshot) "
            "VALUES (:doc, 0.5, 'contextual-risk-additive-0.1.0', "
            "CAST('{}' AS jsonb)) RETURNING id"
        ),
        {"doc": registered_document.id},
    ).scalar_one()
    assert generated is not None


def test_risk_score_requires_model_version(
    db_session: Session, registered_document: Document
) -> None:
    """A stored score without a formula version cannot be attributed later."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError):
            db_session.execute(
                text(
                    "INSERT INTO risk_scores "
                    "(document_id, risk_value, context_snapshot) "
                    "VALUES (:doc, 0.5, CAST('{}' AS jsonb))"
                ),
                {"doc": registered_document.id},
            )
            db_session.flush()


def test_a_new_document_starts_as_registered(registered_document: Document) -> None:
    """No file has been stored, so the lifecycle field must not say "uploaded"."""
    assert registered_document.current_status.value == "registered"
    assert registered_document.storage_path is None


def test_timestamps_are_timezone_aware(registered_document: Document) -> None:
    """``timestamptz`` throughout; a naive timestamp is ambiguous in an audit."""
    assert registered_document.uploaded_at.tzinfo is not None
