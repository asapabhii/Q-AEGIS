"""Deterministic policy engine, ``SPEC.md`` 3.6, implements ``PRD.md`` FR-5.

NOT IMPLEMENTED. Scheduled for Phase 3 (``SPEC.md`` Section 7). This package
exists so the module boundary is fixed before code is written; it contains no
logic, stubbed or otherwise.

The highest-consequence module in the system (``PRD.md`` Risk R2): it sits
directly between an AI recommendation and a real security decision.

When built:
- Tool choice between Cedar and OPA is an open decision (``SPEC.md`` 2.2). It
  must be made against real constraints and logged to ``docs/decisions.md``, not
  defaulted to silently.
- ``policy_decisions.rule_id`` is nullable. "No rule fired, the AI
  recommendation stood" is the common case and is modeled as such, not worked
  around with a placeholder rule.
- Testing floor is one test per rule type and per condition operator, not a
  single happy-path test (``AGENTS.md``).

Owner: Udhav. Required reviewer on any change here, regardless of author.
"""
