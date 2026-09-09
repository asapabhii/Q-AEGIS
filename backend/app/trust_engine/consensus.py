"""Explicit weighted-mean consensus, ``SPEC.md`` 3.5, ``PRD.md`` FR-4.

THIS MODULE'S WEIGHTS ARE PLACEHOLDERS. They have no calibration against real
incident data. Equal fifths exist so the function is deterministic and
reviewable, not because 0.200 is an empirically justified share. Changing any
weight requires bumping ``CONSENSUS_VERSION`` so stored rows remain attributable
to the formula that produced them.

v1 is a weighted arithmetic mean over exactly the five ``AgentType`` values.
A partial set is refused, not filled in. Inventing a missing agent's score
would be fail-open toward a number we cannot defend. Ambiguity therefore
produces no trust score, never a quietly higher one.

LangGraph orchestration (``SPEC.md`` 3.4) is Phase 5. Until it exists the five
scores are caller-asserted, the same treatment as 3.3's ``after_hours``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from app.db.enums import AgentType
from app.db.models.risk import EXPECTED_AGENT_COUNT

#: Recorded on every ``trust_scores`` row and its audit payload.
CONSENSUS_VERSION = "trust-weighted-mean-0.1.0"

#: Equal fifths. Sum is exactly ``1.000``. See the module docstring.
WEIGHTS: dict[AgentType, Decimal] = {
    AgentType.SECURITY: Decimal("0.200"),
    AgentType.COMPLIANCE: Decimal("0.200"),
    AgentType.CONTEXTUAL: Decimal("0.200"),
    AgentType.QUANTUM: Decimal("0.200"),
    AgentType.SUSTAINABILITY: Decimal("0.200"),
}

#: Three decimal places, matching ``trust_scores.consensus_value`` ``numeric(4,3)``
#: and ``agent_outputs.score``.
SCORE_DECIMAL_PLACES = Decimal("0.001")

_ZERO = Decimal("0")
_ONE = Decimal("1")


class IncompleteAgentSetError(ValueError):
    """Fewer or more than the five required agent types, or a duplicate type."""


@dataclass(frozen=True)
class AgentScore:
    """One agent's numeric score and rationale. The rationale is not scored."""

    agent_type: AgentType
    score: Decimal
    rationale: str

    def quantized(self) -> "AgentScore":
        """The score as it will be stored, three decimal places, half-even."""
        return AgentScore(
            agent_type=self.agent_type,
            score=_quantize_unit(self.score),
            rationale=self.rationale,
        )


@dataclass(frozen=True)
class TrustScoreResult:
    """Outcome of one consensus pass. Frozen: the history table is append-only."""

    consensus_value: Decimal
    consensus_version: str
    outputs: tuple[AgentScore, ...]


def combine(outputs: list[AgentScore]) -> TrustScoreResult:
    """Return the weighted mean, or raise if the set is not exactly the five types.

    Scores are quantized to three decimal places before they are weighted, so
    the stored ``agent_outputs.score`` values re-derive the consensus. The
    mean is then quantized the same way.

    Raises:
        IncompleteAgentSetError: on a missing type, a duplicate type, or a
            count other than :data:`EXPECTED_AGENT_COUNT`.
        ValueError: if a score is outside ``[0, 1]``.
    """
    by_type: dict[AgentType, AgentScore] = {}
    for raw in outputs:
        if raw.score < _ZERO or raw.score > _ONE:
            raise ValueError(
                f"{raw.agent_type.value} score must be in [0, 1], got {raw.score}."
            )
        item = raw.quantized()
        if item.agent_type in by_type:
            raise IncompleteAgentSetError(
                f"Duplicate output for agent type {item.agent_type.value}."
            )
        by_type[item.agent_type] = item

    missing = [agent.value for agent in AgentType if agent not in by_type]
    if missing or len(by_type) != EXPECTED_AGENT_COUNT:
        raise IncompleteAgentSetError(
            "Consensus requires exactly one output for each agent type "
            f"({', '.join(agent.value for agent in AgentType)}). "
            f"Missing: {', '.join(missing) if missing else 'none'}."
        )

    total = sum(
        (by_type[agent].score * WEIGHTS[agent] for agent in AgentType),
        start=_ZERO,
    )
    ordered = tuple(by_type[agent] for agent in AgentType)
    return TrustScoreResult(
        consensus_value=_quantize_unit(total),
        consensus_version=CONSENSUS_VERSION,
        outputs=ordered,
    )


def _quantize_unit(value: Decimal) -> Decimal:
    """Clamp to ``[0, 1]`` and round half-even to three decimal places."""
    if value < _ZERO:
        value = _ZERO
    elif value > _ONE:
        value = _ONE
    return value.quantize(SCORE_DECIMAL_PLACES, rounding=ROUND_HALF_EVEN)
