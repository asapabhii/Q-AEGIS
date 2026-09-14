"""Deterministic heuristic scorers for the five agents, ``SPEC.md`` 3.4.

THESE HEURISTICS ARE PROVISIONAL. They encode reviewable rules, not calibrated
incident models. Each function returns a trust score in ``[0, 1]`` where higher
means more trust and lower means more protection is warranted. Failures are
handled in :mod:`app.agents.graph`, not here.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Decimal

from app.agents.state import AssessmentInput
from app.classifier.labels import SensitivityLabel, rank
from app.db.enums import AgentType
from app.trust_engine.consensus import AgentScore

_ZERO = Decimal("0")
_ONE = Decimal("1")
_THREE_DP = Decimal("0.001")

#: Minimum trust on agent failure (fail-safe: less trust, more protection).
FAILURE_TRUST_SCORE = Decimal("0.000")

_SENSITIVITY_TRUST_PENALTY: dict[SensitivityLabel, Decimal] = {
    SensitivityLabel.PUBLIC: Decimal("0.00"),
    SensitivityLabel.INTERNAL: Decimal("0.05"),
    SensitivityLabel.CONFIDENTIAL: Decimal("0.10"),
    SensitivityLabel.RESTRICTED: Decimal("0.15"),
}

_COMPLIANCE_BASE: dict[SensitivityLabel, Decimal] = {
    SensitivityLabel.PUBLIC: Decimal("0.85"),
    SensitivityLabel.INTERNAL: Decimal("0.75"),
    SensitivityLabel.CONFIDENTIAL: Decimal("0.60"),
    SensitivityLabel.RESTRICTED: Decimal("0.45"),
}

_QUANTUM_READINESS: dict[SensitivityLabel, Decimal] = {
    SensitivityLabel.PUBLIC: Decimal("0.80"),
    SensitivityLabel.INTERNAL: Decimal("0.65"),
    SensitivityLabel.CONFIDENTIAL: Decimal("0.45"),
    SensitivityLabel.RESTRICTED: Decimal("0.25"),
}


def failure_score(agent_type: AgentType, reason: str) -> AgentScore:
    """Return a fail-safe output with minimum trust and a visible rationale."""
    return AgentScore(
        agent_type=agent_type,
        score=FAILURE_TRUST_SCORE,
        rationale=(
            f"{agent_type.value} agent failed: {reason}. "
            "Defaulting to minimum trust per fail-safe policy."
        ),
    )


def score_security(input: AssessmentInput) -> AgentScore:
    """Trust from contextual risk and access-threat signals.

    Starts at ``1 - risk_value``, then subtracts fixed penalties for a new
    device, after-hours access, and higher sensitivity labels.
    """
    snapshot = input.context_snapshot
    value = _ONE - input.risk_value
    if snapshot.device_is_new:
        value -= Decimal("0.15")
    if snapshot.after_hours:
        value -= Decimal("0.10")
    value -= _SENSITIVITY_TRUST_PENALTY[input.sensitivity_label]
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.SECURITY,
        score=score,
        rationale=(
            f"Security trust {score}: inverse contextual risk "
            f"{input.risk_value}, label {input.sensitivity_label.value}, "
            f"device_is_new={snapshot.device_is_new}, "
            f"after_hours={snapshot.after_hours}."
        ),
    )


def score_compliance(input: AssessmentInput) -> AgentScore:
    """Trust that access context meets regulatory expectations for the label.

    Uses a label-specific base, penalises after-hours access on regulated
    labels, and rewards a known device.
    """
    snapshot = input.context_snapshot
    value = _COMPLIANCE_BASE[input.sensitivity_label]
    if snapshot.after_hours and input.sensitivity_label in {
        SensitivityLabel.CONFIDENTIAL,
        SensitivityLabel.RESTRICTED,
    }:
        value -= Decimal("0.20")
    if not snapshot.device_is_new:
        value += Decimal("0.10")
    value -= input.risk_value * Decimal("0.15")
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.COMPLIANCE,
        score=score,
        rationale=(
            f"Compliance trust {score} for {input.sensitivity_label.value} "
            f"on file {input.filename!r}; after_hours={snapshot.after_hours}, "
            f"known_device={not snapshot.device_is_new}."
        ),
    )


def score_contextual(input: AssessmentInput) -> AgentScore:
    """Trust from the v1 contextual snapshot signals (``SPEC.md`` 3.3 inputs).

    Begins at 0.80, subtracts the same new-device and after-hours weights used
    by the contextual risk engine, then blends toward ``1 - risk_value``.
    """
    snapshot = input.context_snapshot
    value = Decimal("0.80")
    if snapshot.device_is_new:
        value -= Decimal("0.25")
    if snapshot.after_hours:
        value -= Decimal("0.15")
    inverse_risk = _ONE - input.risk_value
    value = (value + inverse_risk) / Decimal("2")
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.CONTEXTUAL,
        score=score,
        rationale=(
            f"Contextual trust {score}: device {snapshot.device_id!r} "
            f"(new={snapshot.device_is_new}), after_hours={snapshot.after_hours}, "
            f"contextual risk {input.risk_value}."
        ),
    )


def score_quantum(input: AssessmentInput) -> AgentScore:
    """Quantum-readiness trust from label and contextual risk.

    Sensitive labels assume harvest-now-decrypt-later exposure; higher
    ``risk_value`` further reduces readiness trust.
    """
    value = _QUANTUM_READINESS[input.sensitivity_label]
    if input.risk_value > Decimal("0.50"):
        value -= Decimal("0.10")
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.QUANTUM,
        score=score,
        rationale=(
            f"Quantum-readiness trust {score} for {input.sensitivity_label.value} "
            f"content; contextual risk {input.risk_value}."
        ),
    )


def score_sustainability(input: AssessmentInput) -> AgentScore:
    """Sustainability trust from protection intensity implied by label and risk.

    Higher sensitivity and risk imply heavier crypto and storage cost, so trust
    in a lightweight path is reduced.
    """
    label_rank = Decimal(str(rank(input.sensitivity_label)))
    value = Decimal("0.90")
    value -= label_rank * Decimal("0.12")
    value -= input.risk_value * Decimal("0.20")
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.SUSTAINABILITY,
        score=score,
        rationale=(
            f"Sustainability trust {score}: label rank {int(label_rank)} for "
            f"{input.sensitivity_label.value}, contextual risk {input.risk_value}."
        ),
    )


SCORERS: dict[AgentType, Callable[[AssessmentInput], AgentScore]] = {
    AgentType.SECURITY: score_security,
    AgentType.COMPLIANCE: score_compliance,
    AgentType.CONTEXTUAL: score_contextual,
    AgentType.QUANTUM: score_quantum,
    AgentType.SUSTAINABILITY: score_sustainability,
}


def _quantize_trust(value: Decimal) -> Decimal:
    """Clamp to ``[0, 1]`` and round to three decimal places."""
    if value < _ZERO:
        value = _ZERO
    elif value > _ONE:
        value = _ONE
    return value.quantize(_THREE_DP, rounding=ROUND_HALF_EVEN)
