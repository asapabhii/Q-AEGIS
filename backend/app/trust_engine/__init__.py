"""Trust score computation, ``SPEC.md`` 3.5, implements ``PRD.md`` FR-4.

v1 is a weighted arithmetic mean over exactly the five ``AgentType`` values,
versioned as ``trust-weighted-mean-1.0.0``. The weights are principled NIST/ISO
policy weights (security + compliance co-lead), not an incident-derived
calibration; see ``docs/decisions.md``. A partial set is refused.

The LangGraph assessment pipeline (``SPEC.md`` 3.4,
:func:`app.agents.run_assessment`) now produces the five scores: ``POST
/assessments`` runs the agents and feeds their real outputs to this consensus.
``POST /trust-scores`` still accepts caller-asserted scores for direct tests.
This package itself does not run agents or import LangGraph; it is the pure
consensus math the assessment path calls.

``trust_scores`` is append-only. Every row references the ``risk_score_id``
whose ``agent_outputs`` produced it.

Ambiguity resolves toward less trust, never more: a missing agent produces no
score, not a default of 1.0.

Owner: Abhinav (``WORK_DIVISION.md``).
"""
