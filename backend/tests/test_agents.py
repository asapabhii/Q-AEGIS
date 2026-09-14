"""Multi-agent orchestration tests, SPEC.md 3.4, PRD.md FR-3."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents import AssessmentInput, FAILURE_TRUST_SCORE, run_assessment
from app.agents.scoring import SCORERS, score_security
from app.classifier.labels import SensitivityLabel
from app.db.enums import AgentType
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
) -> AssessmentInput:
    return AssessmentInput(
        sensitivity_label=label,
        risk_value=Decimal(risk_value),
        filename=filename,
        context_snapshot=_snapshot(
            device_is_new=device_is_new,
            after_hours=after_hours,
        ),
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
