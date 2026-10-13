"""Multi-agent orchestration tests, SPEC.md 3.4, PRD.md FR-3."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents import (
    AccessFeatures,
    AssessmentInput,
    FAILURE_TRUST_SCORE,
    run_assessment,
)
from app.agents.scoring import (
    SCORER_VERSIONS,
    SCORERS,
    score_compliance,
    score_contextual,
    score_quantum,
    score_security,
    score_sustainability,
)
from app.classifier.labels import SensitivityLabel
from app.db.enums import AgentType, UserRole
from app.risk_engine.scorer import ContextSnapshot
from app.trust_engine.consensus import combine


def _snapshot(
    *,
    device_is_new: bool = False,
    after_hours: bool = False,
) -> ContextSnapshot:
    return ContextSnapshot(
        actor_user_id=uuid4(),
        device_id="laptop-01",
        device_is_new=device_is_new,
        accessed_at=datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc),
        after_hours=after_hours,
    )


def _input(
    *,
    label: SensitivityLabel = SensitivityLabel.INTERNAL,
    risk_value: str = "0.2000",
    filename: str = "quarterly-report.pdf",
    device_is_new: bool = False,
    after_hours: bool = False,
    features: AccessFeatures | None = None,
) -> AssessmentInput:
    return AssessmentInput(
        sensitivity_label=label,
        risk_value=Decimal(risk_value),
        filename=filename,
        context_snapshot=_snapshot(
            device_is_new=device_is_new,
            after_hours=after_hours,
        ),
        features=features if features is not None else AccessFeatures(),
    )


def test_parallel_execution_returns_all_five_agent_types() -> None:
    outputs = run_assessment(_input())
    assert [item.agent_type for item in outputs] == list(AgentType)


def test_scores_are_within_unit_interval() -> None:
    outputs = run_assessment(
        _input(
            label=SensitivityLabel.RESTRICTED,
            risk_value="0.8000",
            device_is_new=True,
            after_hours=True,
        )
    )
    for item in outputs:
        assert Decimal("0") <= item.score <= Decimal("1")
        assert item.rationale.strip()


def test_each_output_has_a_human_readable_rationale() -> None:
    outputs = run_assessment(_input())
    for item in outputs:
        assert len(item.rationale) >= 20
        assert item.agent_type.value in item.rationale or "trust" in item.rationale


def test_outputs_feed_trust_consensus() -> None:
    result = combine(run_assessment(_input()))
    assert Decimal("0") <= result.consensus_value <= Decimal("1")
    assert len(result.outputs) == 5


def test_one_agent_failure_still_returns_five_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(input: AssessmentInput):
        raise RuntimeError("security scorer unavailable")

    monkeypatch.setitem(SCORERS, AgentType.SECURITY, boom)
    outputs = run_assessment(_input())
    assert len(outputs) == 5
    security = next(item for item in outputs if item.agent_type == AgentType.SECURITY)
    assert security.score == FAILURE_TRUST_SCORE
    assert "failed" in security.rationale.lower()
    assert "security scorer unavailable" in security.rationale


def test_non_failed_agents_still_score_normally_on_peer_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = run_assessment(_input())
    baseline_compliance = next(
        item for item in baseline if item.agent_type == AgentType.COMPLIANCE
    )

    def boom(input: AssessmentInput):
        raise RuntimeError("security scorer unavailable")

    monkeypatch.setitem(SCORERS, AgentType.SECURITY, boom)
    outputs = run_assessment(_input())
    compliance = next(
        item for item in outputs if item.agent_type == AgentType.COMPLIANCE
    )
    assert compliance.score == baseline_compliance.score
    assert "failed" not in compliance.rationale.lower()


def test_security_scorer_matches_orchestrated_output() -> None:
    assessment_input = _input(device_is_new=True, after_hours=True)
    expected = score_security(assessment_input)
    actual = next(
        item
        for item in run_assessment(assessment_input)
        if item.agent_type == AgentType.SECURITY
    )
    assert actual.score == expected.score
    assert actual.rationale == expected.rationale


def test_every_scorer_stamps_its_version_in_the_rationale() -> None:
    outputs = run_assessment(_input())
    for item in outputs:
        assert SCORER_VERSIONS[item.agent_type] in item.rationale
        assert "backend=deterministic" in item.rationale


def test_access_features_json_round_trips() -> None:
    features = AccessFeatures(
        actor_prior_access_count=9,
        actor_device_prior_count=4,
        actor_after_hours_count=3,
        device_distinct_actor_count=2,
        document_prior_access_count=5,
        document_prior_risk_value=Decimal("0.4500"),
        actor_role=UserRole.DATA_OWNER.value,
        payload_byte_size=2048,
    )
    assert AccessFeatures.from_json(features.as_json()) == features


def test_rich_features_round_trip_through_the_graph() -> None:
    # A feature bundle must survive serialisation into LangGraph state and be
    # rebuilt identically, so the orchestrated output equals the direct call.
    features = AccessFeatures(
        actor_prior_access_count=12,
        actor_device_prior_count=7,
        actor_after_hours_count=1,
        device_distinct_actor_count=3,
        document_prior_access_count=4,
        document_prior_risk_value=Decimal("0.3000"),
        actor_role=UserRole.SECURITY_ADMIN.value,
        payload_byte_size=4096,
    )
    assessment_input = _input(
        label=SensitivityLabel.CONFIDENTIAL,
        device_is_new=True,
        after_hours=True,
        features=features,
    )
    expected = score_security(assessment_input)
    actual = next(
        item
        for item in run_assessment(assessment_input)
        if item.agent_type == AgentType.SECURITY
    )
    assert actual.score == expected.score
    assert actual.rationale == expected.rationale


def test_security_penalises_a_shared_device() -> None:
    known = AccessFeatures(actor_prior_access_count=5, actor_device_prior_count=5)
    shared = AccessFeatures(
        actor_prior_access_count=5,
        actor_device_prior_count=5,
        device_distinct_actor_count=4,
    )
    private_score = score_security(_input(features=known)).score
    shared_score = score_security(_input(features=shared)).score
    assert shared_score < private_score


def test_contextual_rewards_a_device_known_to_the_actor() -> None:
    first_contact = score_contextual(_input(features=AccessFeatures())).score
    familiar = score_contextual(
        _input(
            features=AccessFeatures(
                actor_prior_access_count=8, actor_device_prior_count=8
            )
        )
    ).score
    assert familiar > first_contact


def test_compliance_flags_privileged_role_on_a_new_device() -> None:
    ordinary = AccessFeatures(actor_role=UserRole.DATA_OWNER.value)
    privileged = AccessFeatures(actor_role=UserRole.SECURITY_ADMIN.value)
    ordinary_score = score_compliance(
        _input(label=SensitivityLabel.RESTRICTED, device_is_new=True, features=ordinary)
    ).score
    privileged_score = score_compliance(
        _input(
            label=SensitivityLabel.RESTRICTED, device_is_new=True, features=privileged
        )
    ).score
    assert privileged_score < ordinary_score


def test_quantum_uses_longevity_and_has_no_risk_cliff() -> None:
    long_lived = score_quantum(
        _input(label=SensitivityLabel.CONFIDENTIAL, filename="archive.zip")
    ).score
    short_lived = score_quantum(
        _input(label=SensitivityLabel.CONFIDENTIAL, filename="scratch.tmp")
    ).score
    assert short_lived > long_lived
    # Continuous risk term: a hair over the old 0.50 boundary must not jump.
    below = score_quantum(_input(risk_value="0.5000")).score
    above = score_quantum(_input(risk_value="0.5100")).score
    assert abs(below - above) < Decimal("0.01")


def test_sustainability_reflects_payload_size() -> None:
    small = score_sustainability(
        _input(features=AccessFeatures(payload_byte_size=1024))
    ).score
    large = score_sustainability(
        _input(features=AccessFeatures(payload_byte_size=10_000_000))
    ).score
    assert large < small
