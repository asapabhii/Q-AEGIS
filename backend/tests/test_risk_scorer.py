"""Pure scoring tests for SPEC.md Section 3.3.

No database. Every combination of the two boolean signals, plus the
validation gates that keep an incomplete snapshot out of ``score``.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.risk_engine.schemas import RiskScoreRequest, RiskScoreResponse
from app.risk_engine.schemas import derive_after_hours
from app.risk_engine.scorer import (
    AFTER_HOURS_WEIGHT,
    BASE_RISK,
    MODEL_VERSION,
    NEW_DEVICE_WEIGHT,
    ContextSnapshot,
    clamp_unit_interval,
    score,
)


def _snapshot(
    *,
    device_is_new: bool = False,
    after_hours: bool = False,
    device_id: str = "laptop-12",
    accessed_at: datetime | None = None,
) -> ContextSnapshot:
    return ContextSnapshot(
        actor_user_id=uuid4(),
        device_id=device_id,
        device_is_new=device_is_new,
        accessed_at=accessed_at or datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
        after_hours=after_hours,
    )


def _request_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "document_id": uuid4(),
        "actor_user_id": uuid4(),
        "device_id": "laptop-12",
        "device_is_new": False,
        "accessed_at": "2026-09-09T12:00:00+00:00",
    }
    body.update(overrides)
    return body


def test_base_risk_when_neither_signal_is_set() -> None:
    result = score(_snapshot())
    assert result.risk_value == Decimal("0.2000")
    assert result.model_version == MODEL_VERSION


def test_new_device_adds_its_weight() -> None:
    result = score(_snapshot(device_is_new=True))
    assert result.risk_value == Decimal("0.5500")
    assert result.risk_value == BASE_RISK + NEW_DEVICE_WEIGHT


def test_after_hours_adds_its_weight() -> None:
    result = score(_snapshot(after_hours=True))
    assert result.risk_value == Decimal("0.4500")
    assert result.risk_value == BASE_RISK + AFTER_HOURS_WEIGHT


def test_both_signals_sum_without_an_interaction_term() -> None:
    result = score(_snapshot(device_is_new=True, after_hours=True))
    assert result.risk_value == Decimal("0.8000")
    assert result.risk_value == BASE_RISK + NEW_DEVICE_WEIGHT + AFTER_HOURS_WEIGHT


def test_v1_ceiling_leaves_headroom_on_the_unit_interval() -> None:
    """0.80 is the v1 max. Future signals add on the same scale."""
    result = score(_snapshot(device_is_new=True, after_hours=True))
    assert result.risk_value < Decimal("1")


def test_clamp_holds_the_unit_interval() -> None:
    assert clamp_unit_interval(Decimal("-0.1000")) == Decimal("0")
    assert clamp_unit_interval(Decimal("1.1000")) == Decimal("1")
    assert clamp_unit_interval(Decimal("0.5500")) == Decimal("0.5500")


def test_after_hours_is_derived_not_supplied() -> None:
    """``after_hours`` is never a request field; the server derives it.

    Noon UTC is 17:30 in Asia/Kolkata — inside business hours — so the derived
    value is False.
    """
    request = RiskScoreRequest.model_validate(_request_body())
    assert request.snapshot().after_hours is False


def test_extra_snapshot_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        RiskScoreRequest.model_validate(_request_body(geo_country="IN"))


def test_client_supplied_risk_value_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        RiskScoreRequest.model_validate(_request_body(risk_value="0.99"))


def test_blank_device_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RiskScoreRequest.model_validate(_request_body(device_id="   "))


def test_naive_accessed_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RiskScoreRequest.model_validate(
            _request_body(accessed_at="2026-09-09T12:00:00")
        )


def test_as_json_emits_json_primitives() -> None:
    snapshot = _snapshot(device_is_new=True, after_hours=True)
    payload = snapshot.as_json()
    assert payload["actor_user_id"] == str(snapshot.actor_user_id)
    assert payload["device_id"] == "laptop-12"
    assert payload["device_is_new"] is True
    assert payload["after_hours"] is True
    assert payload["accessed_at"] == snapshot.accessed_at.isoformat()


def test_as_json_refuses_a_naive_timestamp() -> None:
    snapshot = _snapshot(accessed_at=datetime(2026, 9, 9, 12, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        snapshot.as_json()


def test_request_snapshot_carries_the_closed_fields() -> None:
    request = RiskScoreRequest.model_validate(_request_body())
    snap = request.snapshot()
    assert snap.actor_user_id == request.actor_user_id
    assert snap.device_id == request.device_id
    assert snap.device_is_new is False
    assert snap.after_hours is False
    assert snap.org_timezone == request.org_timezone


def test_after_hours_derives_weeknight_in_org_timezone() -> None:
    request = RiskScoreRequest.model_validate(
        _request_body(
            accessed_at="2026-09-09T16:00:00+00:00",
            org_timezone="Asia/Kolkata",
        )
    )
    assert request.snapshot().after_hours is True


def test_after_hours_derives_weekend_in_org_timezone() -> None:
    request = RiskScoreRequest.model_validate(
        _request_body(
            accessed_at="2026-09-12T06:00:00+00:00",
            org_timezone="Asia/Kolkata",
        )
    )
    assert request.snapshot().after_hours is True


def test_caller_asserted_after_hours_is_rejected() -> None:
    """The client cannot smuggle ``after_hours`` in to understate its risk."""
    with pytest.raises(ValidationError):
        RiskScoreRequest.model_validate(
            _request_body(
                accessed_at="2026-09-09T16:00:00+00:00",
                after_hours=False,
                org_timezone="Asia/Kolkata",
            )
        )


def test_invalid_org_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError, match="valid IANA timezone"):
        RiskScoreRequest.model_validate(_request_body(org_timezone="Mars/Olympus"))


def test_derive_after_hours_refuses_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        derive_after_hours(datetime(2026, 9, 9, 12, 0), "Asia/Kolkata")


def test_response_from_row_carries_the_computed_score() -> None:
    result = score(_snapshot())
    computed_at = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    document_id = uuid4()
    row_id = uuid4()
    response = RiskScoreResponse.from_row(
        risk_score_id=row_id,
        document_id=document_id,
        result=result,
        computed_at=computed_at,
    )
    assert response.id == row_id
    assert response.document_id == document_id
    assert response.risk_value == Decimal("0.2000")
    assert response.model_version == MODEL_VERSION
    assert response.computed_at == computed_at
