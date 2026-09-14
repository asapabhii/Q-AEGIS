"""Multi-agent risk assessment, ``SPEC.md`` 3.4, implements ``PRD.md`` FR-3.

Five deterministic heuristic agents (security, compliance, contextual,
quantum-readiness, sustainability) run as parallel LangGraph nodes. Each
returns a trust score in ``[0, 1]`` and a human-readable rationale. Scoring
rules are provisional heuristics documented in :mod:`app.agents.scoring`; the
orchestration layer is production-shaped, not a stub.

A single agent failure or timeout is captured in graph checkpoint state and
reflected in that agent's output with a minimum-trust fail-safe score, so
consensus never sees a silent omission.

Owner: Abhinav (``WORK_DIVISION.md``).
"""

from app.agents.graph import run_assessment
from app.agents.state import AssessmentInput, AgentFailureRecord
from app.agents.scoring import FAILURE_TRUST_SCORE

__all__ = [
    "AgentFailureRecord",
    "AssessmentInput",
    "FAILURE_TRUST_SCORE",
    "run_assessment",
]
