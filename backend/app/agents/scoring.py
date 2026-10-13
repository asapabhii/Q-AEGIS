"""Deterministic scorers for the five agents, ``SPEC.md`` 3.4.

Each function is a pure, reviewable rule over the frozen
:class:`app.agents.state.AssessmentInput` — in particular its
:class:`app.agents.features.AccessFeatures` bundle, computed once on the request
thread before fan-out (scorers never touch the database or the network). Each
returns a trust score in ``[0, 1]`` where higher means more trust and lower
means more protection is warranted, plus an audit-grade rationale naming the
signals it used and stamping the scorer version. Failures/timeouts are handled
in :mod:`app.agents.graph`, not here.

The five lenses are deliberately distinct. Earlier revisions collapsed to a
function of ``{sensitivity_label, risk_value, device_is_new, after_hours}`` —
and ``risk_value`` is itself a function of the two booleans — so SECURITY and
CONTEXTUAL merely restated the contextual risk engine. Each scorer now reads a
different subset of the behavioural bundle:

* SECURITY       - device familiarity, device sharing, actor-relative timing.
* COMPLIANCE     - label regime, actor-role separation-of-duties, actor history.
* CONTEXTUAL     - zero-trust deviation from this actor/device baseline + trend.
* QUANTUM        - continuous risk term + harvest-now-decrypt-later longevity.
* SUSTAINABILITY - real protection cost: payload size band + content class.

Weights and the consensus function are unchanged, so ``CONSENSUS_VERSION`` stays
fixed; the per-scorer version below advances instead (mirrored into the
rationale, as the LLM path does in :mod:`app.agents.llm`).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Decimal

from app.agents.features import (
    DataLongevity,
    PayloadCost,
    data_longevity,
    payload_cost_class,
)
from app.agents.state import AssessmentInput
from app.classifier.labels import SensitivityLabel, rank
from app.db.enums import AgentType, UserRole
from app.trust_engine.consensus import AgentScore

_ZERO = Decimal("0")
_ONE = Decimal("1")
_THREE_DP = Decimal("0.001")

#: Per-scorer version, mirrored into each rationale for audit provenance. Bumped
#: to 2.0.0 for the AccessFeatures rewrite. The consensus weights and agent set
#: are unchanged, so ``trust_engine.consensus.CONSENSUS_VERSION`` stays fixed.
SCORER_VERSIONS: dict[AgentType, str] = {
    AgentType.SECURITY: "security-det-2.0.0",
    AgentType.COMPLIANCE: "compliance-det-2.0.0",
    AgentType.CONTEXTUAL: "contextual-det-2.0.0",
    AgentType.QUANTUM: "quantum-det-2.0.0",
    AgentType.SUSTAINABILITY: "sustainability-det-2.0.0",
}

#: Roles whose elevated data reach makes an unrecognised-device access a
#: separation-of-duties concern for the compliance lens.
_PRIVILEGED_ROLES = frozenset(
    {
        UserRole.SECURITY_ADMIN.value,
        UserRole.CISO.value,
        UserRole.ENGINEER.value,
    }
)

#: Prior after-hours share at or above which an actor is treated as having a
#: legitimate after-hours pattern rather than deviating from baseline.
_AFTER_HOURS_BASELINE = Decimal("0.25")

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


def _provenance(agent_type: AgentType) -> str:
    """Audit-provenance suffix naming the deterministic scorer version."""
    return f"[scorer={SCORER_VERSIONS[agent_type]}; backend=deterministic]"


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
    """Access-threat trust: device familiarity, sharing, actor-relative timing.

    Independent of the contextual risk engine — it reads device/actor history,
    not ``risk_value`` — so it is a genuinely separate lens, not a restatement
    of ``1 - risk_value``.
    """
    snapshot = input.context_snapshot
    features = input.features
    value = Decimal("0.85")
    if snapshot.device_is_new:
        value -= Decimal("0.12")
    if features.device_known_to_actor:
        value += Decimal("0.08")
    if features.device_is_shared:
        value -= Decimal("0.08")
    if features.actor_is_known:
        value += Decimal("0.05")
    unusual_hour = snapshot.after_hours and (
        features.actor_after_hours_ratio < _AFTER_HOURS_BASELINE
    )
    if unusual_hour:
        value -= Decimal("0.12")
    elif snapshot.after_hours:
        value -= Decimal("0.04")
    value -= _SENSITIVITY_TRUST_PENALTY[input.sensitivity_label]
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.SECURITY,
        score=score,
        rationale=(
            f"Security trust {score}: device_is_new={snapshot.device_is_new}, "
            f"known_to_actor={features.device_known_to_actor}, "
            f"device seen by {features.device_distinct_actor_count} actor(s), "
            f"actor prior accesses={features.actor_prior_access_count}, "
            f"after_hours={snapshot.after_hours} vs actor baseline "
            f"{features.actor_after_hours_ratio:.2f}, label "
            f"{input.sensitivity_label.value}. {_provenance(AgentType.SECURITY)}"
        ),
    )


def score_compliance(input: AssessmentInput) -> AgentScore:
    """Regulatory-fit trust: label regime, role SoD, and actor familiarity.

    Uses a label-specific base, penalises after-hours access on regulated
    labels, flags an unfamiliar actor on regulated content, and treats a
    privileged role operating from an unrecognised device as a
    separation-of-duties concern. It intentionally omits ``risk_value`` (a
    contextual, not regulatory, signal).
    """
    snapshot = input.context_snapshot
    features = input.features
    regulated = input.sensitivity_label in {
        SensitivityLabel.CONFIDENTIAL,
        SensitivityLabel.RESTRICTED,
    }
    value = _COMPLIANCE_BASE[input.sensitivity_label]
    if snapshot.after_hours and regulated:
        value -= Decimal("0.20")
    if features.device_known_to_actor:
        value += Decimal("0.10")
    if regulated and not features.actor_is_known:
        value -= Decimal("0.08")
    if snapshot.device_is_new and features.actor_role in _PRIVILEGED_ROLES:
        value -= Decimal("0.10")
    score = _quantize_trust(value)
    role_label = features.actor_role or "unknown"
    return AgentScore(
        agent_type=AgentType.COMPLIANCE,
        score=score,
        rationale=(
            f"Compliance trust {score} for {input.sensitivity_label.value} "
            f"on {input.filename!r}: after_hours={snapshot.after_hours}, "
            f"known_device={features.device_known_to_actor}, "
            f"actor_role={role_label}, "
            f"actor_prior_accesses={features.actor_prior_access_count}. "
            f"{_provenance(AgentType.COMPLIANCE)}"
        ),
    )


def score_contextual(input: AssessmentInput) -> AgentScore:
    """Zero-trust deviation from this actor/device baseline, plus risk trend.

    Reads behavioural history and the *direction* of ``risk_value`` relative to
    the document's prior assessment, not the raw risk score, so it duplicates
    neither the contextual risk engine nor the security lens.
    """
    snapshot = input.context_snapshot
    features = input.features
    value = Decimal("0.80")
    if features.device_known_to_actor:
        value += Decimal("0.10")
    else:
        value -= Decimal("0.15")
    if features.actor_is_known:
        value += Decimal("0.05")
    if snapshot.after_hours and (
        features.actor_after_hours_ratio < _AFTER_HOURS_BASELINE
    ):
        value -= Decimal("0.15")
    prior = features.document_prior_risk_value
    rising = prior is not None and input.risk_value > prior
    if rising:
        value -= Decimal("0.08")
    score = _quantize_trust(value)
    trend = f"rising from {prior}" if rising else "no adverse trend"
    return AgentScore(
        agent_type=AgentType.CONTEXTUAL,
        score=score,
        rationale=(
            f"Contextual trust {score}: known_to_actor="
            f"{features.device_known_to_actor}, actor_known="
            f"{features.actor_is_known}, after_hours={snapshot.after_hours} vs "
            f"baseline {features.actor_after_hours_ratio:.2f}, risk "
            f"{input.risk_value} ({trend}). {_provenance(AgentType.CONTEXTUAL)}"
        ),
    )


def score_quantum(input: AssessmentInput) -> AgentScore:
    """Quantum-readiness trust: continuous risk term + data longevity (HNDL).

    Replaces the old 0.50 risk cliff with a continuous risk term, and adds a
    harvest-now-decrypt-later longevity signal derived only from the file-name
    suffix (a closed extension map, never classifier or keyword data).
    """
    value = _QUANTUM_READINESS[input.sensitivity_label]
    value -= input.risk_value * Decimal("0.15")
    longevity = data_longevity(input.filename)
    if longevity is DataLongevity.LONG:
        value -= Decimal("0.10")
    elif longevity is DataLongevity.SHORT:
        value += Decimal("0.05")
    score = _quantize_trust(value)
    return AgentScore(
        agent_type=AgentType.QUANTUM,
        score=score,
        rationale=(
            f"Quantum-readiness trust {score} for "
            f"{input.sensitivity_label.value} content: contextual risk "
            f"{input.risk_value}, data longevity {longevity.value}. "
            f"{_provenance(AgentType.QUANTUM)}"
        ),
    )


def score_sustainability(input: AssessmentInput) -> AgentScore:
    """Sustainability trust: real protection cost, not a risk proxy.

    Trust that a lightweight protection path suffices, reduced by the actual
    cost drivers — payload size band and content-type class (closed suffix
    map) — plus the sensitivity label. Larger, heavier, more-sensitive payloads
    pull toward stronger, costlier protection.
    """
    features = input.features
    label_rank = Decimal(str(rank(input.sensitivity_label)))
    value = Decimal("0.90")
    value -= label_rank * Decimal("0.10")
    size = features.payload_byte_size
    if size is None:
        value -= Decimal("0.05")
        size_band = "unknown"
    elif size >= 5_000_000:
        value -= Decimal("0.20")
        size_band = "large"
    elif size >= 512_000:
        value -= Decimal("0.10")
        size_band = "medium"
    else:
        value -= Decimal("0.03")
        size_band = "small"
    cost_class = payload_cost_class(input.filename)
    if cost_class is PayloadCost.HEAVY:
        value -= Decimal("0.05")
    elif cost_class is PayloadCost.LIGHT:
        value += Decimal("0.03")
    score = _quantize_trust(value)
    size_text = "n/a" if size is None else str(size)
    return AgentScore(
        agent_type=AgentType.SUSTAINABILITY,
        score=score,
        rationale=(
            f"Sustainability trust {score}: label rank {int(label_rank)} "
            f"({input.sensitivity_label.value}), payload {size_band} "
            f"({size_text} bytes), content class {cost_class.value}. "
            f"{_provenance(AgentType.SUSTAINABILITY)}"
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
