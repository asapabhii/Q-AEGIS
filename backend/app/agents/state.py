"""Assessment input and LangGraph state types, ``SPEC.md`` 3.4."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, TypedDict

from app.classifier.labels import SensitivityLabel
from app.db.enums import AgentType
from app.risk_engine.scorer import ContextSnapshot
from app.trust_engine.consensus import AgentScore


@dataclass(frozen=True)
class AssessmentInput:
    """Caller-supplied facts for one five-agent assessment pass."""

    sensitivity_label: SensitivityLabel
    risk_value: Decimal
    filename: str
    context_snapshot: ContextSnapshot


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
    outputs: Annotated[list[AgentScore], operator.add]
    failures: Annotated[list[AgentFailureRecord], operator.add]
