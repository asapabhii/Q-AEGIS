"""Assessment input and LangGraph state types, ``SPEC.md`` 3.4."""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated, Any, TypedDict

from app.agents.features import AccessFeatures
from app.classifier.labels import SensitivityLabel
from app.db.enums import AgentType
from app.risk_engine.scorer import ContextSnapshot
from app.trust_engine.consensus import AgentScore


@dataclass(frozen=True)
class AssessmentInput:
    """Caller-supplied facts for one five-agent assessment pass.

    ``features`` is the frozen per-access behavioural bundle
    (:class:`app.agents.features.AccessFeatures`). It defaults to a neutral
    first-contact bundle so callers and tests without access history still
    construct a valid input; the pipeline computes the real bundle on the
    request thread before fan-out.
    """

    sensitivity_label: SensitivityLabel
    risk_value: Decimal
    filename: str
    context_snapshot: ContextSnapshot
    features: AccessFeatures = field(default_factory=AccessFeatures)


@dataclass(frozen=True)
class AgentFailureRecord:
    """One agent that failed or timed out during orchestration."""

    agent_type: AgentType
    message: str


class AssessmentState(TypedDict):
    """LangGraph state for parallel agent execution."""

    sensitivity_label: SensitivityLabel
    risk_value: Decimal
    filename: str
    context_snapshot: dict[str, Any]
    features: dict[str, Any]
    outputs: Annotated[list[AgentScore], operator.add]
    failures: Annotated[list[AgentFailureRecord], operator.add]
