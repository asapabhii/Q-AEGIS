"""Additive contextual risk scorer, ``SPEC.md`` 3.3, ``PRD.md`` FR-2.

THIS MODULE'S WEIGHTS ARE PLACEHOLDERS. They have no calibration against real
incident data. Changing ``BASE_RISK``, ``NEW_DEVICE_WEIGHT``, or
``AFTER_HOURS_WEIGHT`` requires bumping ``MODEL_VERSION`` so stored rows remain
attributable to the formula that produced them.

v1 is strictly additive: each firing signal adds its weight to the base, then
the sum is clamped to ``[0, 1]`` and rounded to four decimal places, matching
the classifier's convention (``app.classifier.stub_classifier``). There are no
interaction terms. The maximum v1 value is 0.8000; the headroom is intentional
so later signals can join the same scale without a rescale.

``after_hours`` and ``device_is_new`` are facts on the snapshot. This function
does not derive them.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID

#: Recorded on every ``risk_scores`` row and its audit payload.
MODEL_VERSION = "contextual-risk-additive-0.1.0"

BASE_RISK = Decimal("0.20")
NEW_DEVICE_WEIGHT = Decimal("0.35")
AFTER_HOURS_WEIGHT = Decimal("0.25")

#: Four decimal places, matching ``risk_scores.risk_value`` ``numeric(5,4)``
#: and the classifier's ``round(..., 4)``.
RISK_DECIMAL_PLACES = Decimal("0.0001")

_ZERO = Decimal("0")
_ONE = Decimal("1")


def clamp_unit_interval(value: Decimal) -> Decimal:
    """Bound ``value`` to ``[0, 1]``.

    v1 weights cannot exceed 0.80. The clamp is still part of the formula so a
    later signal on the same scale cannot produce a value outside the column's
    CHECK constraint.
    """
    if value < _ZERO:
        return _ZERO
    if value > _ONE:
        return _ONE
    return value


@dataclass(frozen=True)
class ContextSnapshot:
    """The closed v1 signal set. Every field is required; none is derived here."""

    actor_user_id: UUID
    device_id: str
    device_is_new: bool
    accessed_at: datetime
    after_hours: bool

    def as_json(self) -> dict[str, str | bool]:
        """JSON primitives for ``context_snapshot`` and the audit payload.

        UUIDs and timestamps become strings here so
        :func:`app.db.repositories.audit.normalize_payload` is not asked to
        coerce types.
        """
        accessed = self.accessed_at
        if accessed.tzinfo is None:
            raise ValueError("accessed_at must be timezone-aware")
        return {
            "actor_user_id": str(self.actor_user_id),
            "device_id": self.device_id,
            "device_is_new": self.device_is_new,
            "accessed_at": accessed.isoformat(),
            "after_hours": self.after_hours,
        }


@dataclass(frozen=True)
class RiskScoreResult:
    """Outcome of one contextual scoring. Frozen: the history table is append-only."""

    risk_value: Decimal
    model_version: str
    snapshot: ContextSnapshot


def score(snapshot: ContextSnapshot) -> RiskScoreResult:
    """Return the v1 additive risk for a complete snapshot.

    An incomplete snapshot must never reach this function. Rejection of missing
    fields is the API schema's job (422), not a default inside the formula.
    """
    value = BASE_RISK
    if snapshot.device_is_new:
        value += NEW_DEVICE_WEIGHT
    if snapshot.after_hours:
        value += AFTER_HOURS_WEIGHT
    rounded = clamp_unit_interval(value).quantize(
        RISK_DECIMAL_PLACES, rounding=ROUND_HALF_EVEN
    )
    return RiskScoreResult(
        risk_value=rounded,
        model_version=MODEL_VERSION,
        snapshot=snapshot,
    )
