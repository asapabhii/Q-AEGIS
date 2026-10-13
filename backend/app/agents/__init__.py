"""Multi-agent risk assessment, ``SPEC.md`` 3.4, implements ``PRD.md`` FR-3.

Five deterministic agents (security, compliance, contextual, quantum-readiness,
sustainability) run as parallel LangGraph nodes. Each returns a trust score in
``[0, 1]`` and an audit-grade rationale. Every scorer reads a different subset of
the frozen per-access :class:`app.agents.features.AccessFeatures` bundle, so the
five are genuinely distinct lenses rather than restatements of the contextual
risk engine; the rules stay deterministic and reviewable (see
:mod:`app.agents.scoring`) and the orchestration layer is production-shaped.

A single agent failure or timeout is captured in graph checkpoint state and
reflected in that agent's output with a minimum-trust fail-safe score, so
consensus never sees a silent omission.

Owner: Abhinav (``WORK_DIVISION.md``).
"""

from app.agents.features import AccessFeatures
from app.agents.graph import run_assessment
from app.agents.scoring import FAILURE_TRUST_SCORE
from app.agents.state import AgentFailureRecord, AssessmentInput

__all__ = [
    "AccessFeatures",
    "AgentFailureRecord",
    "AssessmentInput",
    "FAILURE_TRUST_SCORE",
    "run_assessment",
]
