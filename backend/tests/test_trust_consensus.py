"""Consensus function tests, SPEC.md 3.5, PRD.md FR-4.

The function must refuse a partial set. A happy-path-only test would hide
the fail-closed rule.
"""

from decimal import Decimal

import pytest

from app.db.enums import AgentType
from app.trust_engine.consensus import (
    CONSENSUS_VERSION,
    WEIGHTS,
    AgentScore,
    IncompleteAgentSetError,
    combine,
)


def _five(
    scores: dict[AgentType, str] | None = None,
) -> list[AgentScore]:
    values = scores or {agent: "0.500" for agent in AgentType}
    return [
        AgentScore(
            agent_type=agent,
            score=Decimal(values[agent]),
            rationale=f"{agent.value} rationale",
        )
        for agent in AgentType
    ]


def test_weights_are_equal_fifths_and_sum_to_one() -> None:
    assert set(WEIGHTS) == set(AgentType)
    assert all(weight == Decimal("0.200") for weight in WEIGHTS.values())
    assert sum(WEIGHTS.values(), start=Decimal("0")) == Decimal("1.000")


def test_equal_scores_are_the_consensus() -> None:
    result = combine(_five())
    assert result.consensus_value == Decimal("0.500")
    assert result.consensus_version == CONSENSUS_VERSION
    assert [item.agent_type for item in result.outputs] == list(AgentType)


def test_weighted_mean_of_distinct_scores() -> None:
    result = combine(
        _five(
            {
                AgentType.SECURITY: "0.100",
                AgentType.COMPLIANCE: "0.200",
                AgentType.CONTEXTUAL: "0.300",
                AgentType.QUANTUM: "0.400",
                AgentType.SUSTAINABILITY: "0.500",
            }
        )
    )
    assert result.consensus_value == Decimal("0.300")


def test_scores_are_quantized_before_they_are_weighted() -> None:
    """0.1234 stored as 0.123; five of those mean 0.123, not 0.1234."""
    result = combine(_five({agent: "0.1234" for agent in AgentType}))
    assert result.outputs[0].score == Decimal("0.123")
    assert result.consensus_value == Decimal("0.123")


def test_extremes_stay_inside_the_unit_interval() -> None:
    assert combine(
        _five({agent: "0" for agent in AgentType})
    ).consensus_value == Decimal("0.000")
    assert combine(
        _five({agent: "1" for agent in AgentType})
    ).consensus_value == Decimal("1.000")


def test_a_non_finite_score_is_rejected_by_the_schema() -> None:
    from pydantic import ValidationError

    from app.trust_engine.schemas import AgentOutputBody

    with pytest.raises(ValidationError):
        AgentOutputBody(
            agent_type=AgentType.SECURITY,
            score=float("inf"),
            rationale="not a real number",
        )
    with pytest.raises(ValidationError):
        AgentOutputBody(
            agent_type=AgentType.SECURITY,
            score=Decimal("NaN"),
            rationale="not a real number",
        )
    with pytest.raises(ValidationError):
        AgentOutputBody(
            agent_type=AgentType.SECURITY,
            score=Decimal("Infinity"),
            rationale="not a real number",
        )
    with pytest.raises(ValidationError):
        AgentOutputBody(
            agent_type=AgentType.SECURITY,
            score="NaN",
            rationale="not a real number",
        )


def test_duplicate_agent_type_is_named_in_the_schema_error() -> None:
    from uuid import uuid4

    from pydantic import ValidationError

    from app.trust_engine.schemas import AgentOutputBody, TrustScoreRequest

    bodies = [
        AgentOutputBody(
            agent_type=agent,
            score=Decimal("0.5"),
            rationale=f"{agent.value} assessed this snapshot.",
        )
        for agent in AgentType
    ]
    bodies[-1] = AgentOutputBody(
        agent_type=AgentType.SECURITY,
        score=Decimal("0.5"),
        rationale="duplicate security",
    )
    with pytest.raises(ValidationError, match="Duplicate: security"):
        TrustScoreRequest(risk_score_id=uuid4(), outputs=bodies)


def test_four_agents_are_refused() -> None:
    with pytest.raises(IncompleteAgentSetError, match="Missing: sustainability"):
        combine(_five()[:-1])


def test_a_score_outside_the_unit_interval_is_refused() -> None:
    with pytest.raises(ValueError, match="must be in"):
        combine(_five({agent: "1.5" for agent in AgentType}))
    with pytest.raises(ValueError, match="must be in"):
        combine(_five({agent: "-0.1" for agent in AgentType}))


def test_quantize_clamps_before_rounding() -> None:
    from app.trust_engine.consensus import _quantize_unit

    assert _quantize_unit(Decimal("-1")) == Decimal("0.000")
    assert _quantize_unit(Decimal("2")) == Decimal("1.000")


def test_a_duplicate_type_is_refused() -> None:
    outputs = _five()
    outputs[4] = AgentScore(
        agent_type=AgentType.SECURITY,
        score=Decimal("0.100"),
        rationale="dup",
    )
    with pytest.raises(IncompleteAgentSetError, match="Duplicate"):
        combine(outputs)
