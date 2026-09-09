"""Trust score computation, ``SPEC.md`` 3.5, implements ``PRD.md`` FR-4.

v1 is an equal-weight arithmetic mean over exactly the five ``AgentType``
values, versioned as ``trust-weighted-mean-0.1.0``. The weights are placeholders;
see ``docs/decisions.md``. A partial set is refused.

The five scores are caller-asserted until 3.4 exists to produce them. This
package does not run agents and does not import LangGraph.

``trust_scores`` is append-only. Every row references the ``risk_score_id``
whose ``agent_outputs`` produced it.

Ambiguity resolves toward less trust, never more: a missing agent produces no
score, not a default of 1.0.

Owner: Abhinav (``WORK_DIVISION.md``).
"""
