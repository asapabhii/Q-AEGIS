"""Contextual risk engine, ``SPEC.md`` 3.3, implements ``PRD.md`` FR-2.

Computes ``risk_scores.risk_value`` from a closed v1 context snapshot. That
number is this engine's own score, not the five-agent aggregate; that aggregate
is ``trust_scores.consensus_value`` (``SPEC.md`` 3.5).

THIS MODULE'S WEIGHTS ARE PLACEHOLDERS. ``BASE_RISK``, ``NEW_DEVICE_WEIGHT``,
and ``AFTER_HOURS_WEIGHT`` have no calibration against real incident data.
Changing any of them requires bumping ``MODEL_VERSION``. There are no
interaction terms in v1; combining signals non-additively is a future change
that needs data to justify it, not an encoding convenience.

``after_hours`` is caller-asserted. This engine does not derive business hours
from a timezone or calendar; that is deferred until an org working-hours policy
exists (see ``docs/decisions.md``).

v1 does not schedule recomputes and does not consume an event bus. Redis
Streams vs Kafka is still open (``SPEC.md`` 2.3) and is not decided here.

Owner: Abhinav (``WORK_DIVISION.md``).
"""
