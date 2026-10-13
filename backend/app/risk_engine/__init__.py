"""Contextual risk engine, ``SPEC.md`` 3.3, implements ``PRD.md`` FR-2.

Computes ``risk_scores.risk_value`` from a closed v1 context snapshot. That
number is this engine's own score, not the five-agent aggregate; that aggregate
is ``trust_scores.consensus_value`` (``SPEC.md`` 3.5).

The v1 weights (``BASE_RISK``, ``NEW_DEVICE_WEIGHT``, ``AFTER_HOURS_WEIGHT``)
are provisional *policy* weights, not incident-calibrated coefficients: they
encode a defensible ordering, to be re-fit against real access-incident data as
it accrues (``docs/decisions.md``). Changing any of them requires bumping
``MODEL_VERSION``. There are no interaction terms in v1; combining signals
non-additively is a future change that needs data to justify it, not an
encoding convenience.

``after_hours`` is server-authoritative: ``schemas.py`` derives it from
``accessed_at`` and the org ``org_timezone`` (weekday 09:00-18:00 local is
business hours; everything outside that window is after-hours) via
``derive_after_hours``. The API never accepts ``after_hours`` from the client,
so a caller cannot understate its own risk, and scheduled recomputes re-derive
it against the stored timezone and the fresh wall-clock (``recompute.py``).
``device_is_new`` remains a caller-asserted fact in v0.2.0; making it
server-authoritative needs a device-enrollment registry with a trust lifecycle,
tracked separately.

Recomputes run both on a periodic schedule and off the Redis Streams bus
(``recompute.py``, ``scheduler.py``): a ``schedule.tick`` re-scores every
document from its latest snapshot with a fresh wall-clock, and a ``risk.trigger``
re-scores one document immediately.

Owner: Abhinav (``WORK_DIVISION.md``).
"""
