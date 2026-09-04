"""Contextual risk engine, ``SPEC.md`` 3.3, implements ``PRD.md`` FR-2.

NOT IMPLEMENTED. Scheduled for Phase 3 (``SPEC.md`` Section 7). This package
exists so the module boundary is fixed before code is written; it contains no
logic, stubbed or otherwise.

When built: recomputes on a schedule and on trigger events (new device login,
after-hours access), not once at upload. Writes to ``risk_scores`` with a
``context_snapshot`` jsonb column. Append-only, a new computation never
overwrites a prior one.

Owner: Abhinav (``WORK_DIVISION.md``).
"""
