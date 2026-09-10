"""Unit tests for FR-13 candidate replay, SPEC.md 3.6.

No database. Snapshots are the two fields ``_replay_one`` reads: ``payload``
and ``created_at``.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.classifier.labels import SensitivityLabel
from app.db.enums import PolicyAction
from app.policy.dry_run import _replay_one, replay_candidate
from app.policy.engine import EvaluableRule

DENY_RESTRICTED = {
    "field": "sensitivity_label",
    "op": "eq",
    "value": "RESTRICTED",
}

DECIDED_AT = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "policy_decision_id": str(uuid4()),
        "document_id": str(uuid4()),
        "sensitivity_label": "RESTRICTED",
        "risk_value": 0.2,
        "trust_score": 0.5,
        "ai_recommendation": "allow",
        "final_decision": "allow",
    }
    body.update(overrides)
    return body


def _snapshot(payload: dict[str, object]) -> SimpleNamespace:
    """Duck-typed audit row. ``replay_candidate`` only reads two attributes."""
    return SimpleNamespace(payload=payload, created_at=DECIDED_AT)


def _candidate() -> EvaluableRule:
    return EvaluableRule(
        id=uuid4(),
        rule_name="candidate",
        action=PolicyAction.DENY,
        condition=DENY_RESTRICTED,
    )


def test_empty_history_considers_nothing() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[],
    )
    assert result.considered == 0
    assert result.skipped == 0
    assert result.replays == []


def test_a_payload_missing_v1_keys_is_skipped() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[_snapshot({"final_decision": "allow"})],
    )
    assert result.considered == 1
    assert result.skipped == 1
    assert result.replays == []


def test_an_unrecognized_sensitivity_label_is_skipped() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[_snapshot(_payload(sensitivity_label="TOP_SECRET"))],
    )
    assert result.considered == 1
    assert result.skipped == 1
    assert result.replays == []


def test_an_unrecognized_recorded_decision_is_skipped() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[_snapshot(_payload(final_decision="quarantine"))],
    )
    assert result.considered == 1
    assert result.skipped == 1
    assert result.replays == []


def test_a_malformed_decision_id_is_skipped() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[_snapshot(_payload(policy_decision_id="not-a-uuid"))],
    )
    assert result.considered == 1
    assert result.skipped == 1
    assert result.replays == []


def test_replay_one_returns_none_for_a_malformed_payload() -> None:
    assert _replay_one(_candidate(), _snapshot({"sensitivity_label": "PUBLIC"})) is None


def test_a_match_reports_the_candidate_action_as_a_change() -> None:
    decision_id = uuid4()
    document_id = uuid4()
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[
            _snapshot(
                _payload(
                    policy_decision_id=str(decision_id),
                    document_id=str(document_id),
                )
            )
        ],
    )
    assert result.considered == 1
    assert result.skipped == 0
    replay = result.replays[0]
    assert replay.decision_id == decision_id
    assert replay.document_id == document_id
    assert replay.decided_at == DECIDED_AT
    assert replay.sensitivity_label is SensitivityLabel.RESTRICTED
    assert replay.would_match is True
    assert replay.hypothetical_final_decision is PolicyAction.DENY
    assert replay.recorded_final_decision is PolicyAction.ALLOW
    assert replay.would_change_outcome is True


def test_a_miss_keeps_the_ai_recommendation_and_does_not_claim_a_change() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[_snapshot(_payload(sensitivity_label="PUBLIC"))],
    )
    replay = result.replays[0]
    assert replay.would_match is False
    assert replay.hypothetical_final_decision is PolicyAction.ALLOW
    assert replay.would_change_outcome is False


def test_a_miss_flags_a_change_when_history_had_already_overridden() -> None:
    """Hypothetical is the AI rec, not the recorded final, when this rule misses."""
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[
            _snapshot(
                _payload(
                    sensitivity_label="PUBLIC",
                    ai_recommendation="allow",
                    final_decision="force_pqc",
                )
            )
        ],
    )
    replay = result.replays[0]
    assert replay.would_match is False
    assert replay.hypothetical_final_decision is PolicyAction.ALLOW
    assert replay.recorded_final_decision is PolicyAction.FORCE_PQC
    assert replay.would_change_outcome is True


def test_valid_and_malformed_snapshots_are_accounted_separately() -> None:
    result = replay_candidate(
        condition_expr=DENY_RESTRICTED,
        action=PolicyAction.DENY,
        snapshots=[_snapshot(_payload()), _snapshot({"nope": True})],
    )
    assert result.considered == 2
    assert result.skipped == 1
    assert len(result.replays) == 1
    assert isinstance(result.replays[0].decision_id, UUID)
