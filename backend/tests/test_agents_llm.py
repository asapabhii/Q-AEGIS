"""Claude-backed agent scoring: parsing, provenance, and fail-closed behavior.

The suite runs the deterministic backend (conftest). These tests inject the model
call so the parse/validate/provenance/fail-safe logic is covered without network.
The live Anthropic path is covered by ``test_real_anthropic_agent_scores``, which
is skipped unless ``RUN_REAL_LLM_TESTS=1`` and a key is configured.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents import llm
from app.agents.scoring import FAILURE_TRUST_SCORE
from app.agents.state import AssessmentInput
from app.classifier.labels import SensitivityLabel
from app.config import get_settings
from app.db.enums import AgentType
from app.risk_engine.scorer import ContextSnapshot


def _input(
    *,
    label: SensitivityLabel = SensitivityLabel.CONFIDENTIAL,
    risk: str = "0.400",
    device_is_new: bool = False,
    after_hours: bool = False,
) -> AssessmentInput:
    return AssessmentInput(
        sensitivity_label=label,
        risk_value=Decimal(risk),
        filename="report.pdf",
        context_snapshot=ContextSnapshot(
            actor_user_id=uuid4(),
            device_id="dev-1",
            device_is_new=device_is_new,
            accessed_at=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc),
            after_hours=after_hours,
        ),
    )


def test_parse_score_payload_valid() -> None:
    score, rationale = llm._parse_score_payload('{"score": 0.73, "rationale": "ok"}')
    assert score == 0.73
    assert rationale == "ok"


def test_parse_score_payload_extracts_json_from_noise() -> None:
    score, _ = llm._parse_score_payload(
        'Here you go: {"score": 0.4, "rationale": "x"} thanks'
    )
    assert score == 0.4


@pytest.mark.parametrize(
    "bad",
    [
        '{"rationale": "no score"}',
        '{"score": 1.5, "rationale": "too high"}',
        '{"score": "hi"}',
        '{"score": true}',
        "not json at all",
    ],
)
def test_parse_score_payload_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        llm._parse_score_payload(bad)


def test_score_agent_records_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm,
        "_call_model",
        lambda system, user: '{"score": 0.8, "rationale": "known device, hours ok"}',
    )
    result = llm.score_agent(AgentType.SECURITY, _input())
    assert result.agent_type is AgentType.SECURITY
    assert result.score == Decimal("0.800")
    assert "model=" in result.rationale
    assert "backend=anthropic" in result.rationale


def test_anthropic_backend_failure_is_failsafe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A raising model call under the anthropic backend must resolve to minimum
    # trust for all five agents (fail-closed), never a fabricated score.
    monkeypatch.setenv("AGENT_LLM_BACKEND", "anthropic")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key")
    get_settings.cache_clear()

    def boom(system: str, user: str) -> str:
        raise RuntimeError("api down")

    monkeypatch.setattr(llm, "_call_model", boom)

    from app.agents.graph import get_compiled_graph, run_assessment

    get_compiled_graph.cache_clear()
    outputs = run_assessment(_input())
    assert len(outputs) == 5
    assert all(o.score == FAILURE_TRUST_SCORE for o in outputs)


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_LLM_TESTS") != "1",
    reason="set RUN_REAL_LLM_TESTS=1 and AGENT_LLM_API_KEY to call the real model",
)
def test_real_anthropic_agent_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LLM_BACKEND", "anthropic")
    get_settings.cache_clear()
    if not get_settings().agent_llm_api_key:
        pytest.skip("AGENT_LLM_API_KEY not set")
    result = llm.score_agent(AgentType.SECURITY, _input(device_is_new=True))
    assert 0.0 <= float(result.score) <= 1.0
    assert "model=" in result.rationale
