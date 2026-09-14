"""LangGraph parallel orchestration for five risk agents, ``SPEC.md`` 3.4."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import lru_cache
from typing import Callable
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.scoring import SCORERS, failure_score
from app.agents.state import (
    AgentFailureRecord,
    AssessmentInput,
    AssessmentState,
)
from app.db.enums import AgentType
from app.trust_engine.consensus import AgentScore

#: Per-agent wall-clock budget. Heuristics are synchronous; this guards injected
#: slow paths and future non-heuristic agents without letting one stall consensus.
AGENT_TIMEOUT_SECONDS = 5.0


def _assessment_input_from_state(state: AssessmentState) -> AssessmentInput:
    from app.risk_engine.scorer import ContextSnapshot

    snapshot_data = state["context_snapshot"]
    return AssessmentInput(
        sensitivity_label=state["sensitivity_label"],
        risk_value=state["risk_value"],
        filename=state["filename"],
        context_snapshot=ContextSnapshot(
            actor_user_id=snapshot_data["actor_user_id"],
            device_id=snapshot_data["device_id"],
            device_is_new=snapshot_data["device_is_new"],
            accessed_at=snapshot_data["accessed_at"],
            after_hours=snapshot_data["after_hours"],
        ),
    )


def _run_scorer_with_timeout(
    scorer: Callable[[AssessmentInput], AgentScore],
    assessment_input: AssessmentInput,
    agent_type: AgentType,
) -> tuple[AgentScore, AgentFailureRecord | None]:
    """Run one scorer, returning a failure score and record on timeout."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(scorer, assessment_input)
        try:
            return future.result(timeout=AGENT_TIMEOUT_SECONDS), None
        except FuturesTimeoutError:
            message = f"timed out after {AGENT_TIMEOUT_SECONDS:g}s"
            return failure_score(agent_type, message), AgentFailureRecord(
                agent_type=agent_type,
                message=message,
            )


def _make_agent_node(agent_type: AgentType) -> Callable[[AssessmentState], dict]:
    """Return a LangGraph node that scores one agent and captures failures."""

    def node(state: AssessmentState) -> dict:
        assessment_input = _assessment_input_from_state(state)
        scorer = SCORERS[agent_type]
        try:
            result, failure = _run_scorer_with_timeout(
                scorer,
                assessment_input,
                agent_type,
            )
        except Exception as exc:  # noqa: BLE001 - one agent must not abort the graph
            message = str(exc)
            result = failure_score(agent_type, message)
            failure = AgentFailureRecord(agent_type=agent_type, message=message)

        if failure is None:
            return {"outputs": [result]}
        return {"outputs": [result], "failures": [failure]}

    return node


def build_assessment_graph() -> StateGraph:
    """Construct the fan-out graph: START to five parallel agent nodes to END."""
    builder: StateGraph = StateGraph(AssessmentState)
    for agent_type in AgentType:
        builder.add_node(agent_type.value, _make_agent_node(agent_type))
        builder.add_edge(START, agent_type.value)
        builder.add_edge(agent_type.value, END)
    return builder


@lru_cache(maxsize=1)
def get_compiled_graph():
    """Return the compiled graph with in-memory checkpointing."""
    checkpointer = MemorySaver()
    return build_assessment_graph().compile(checkpointer=checkpointer)


def _initial_state(input: AssessmentInput) -> AssessmentState:
    snapshot = input.context_snapshot
    return {
        "sensitivity_label": input.sensitivity_label,
        "risk_value": input.risk_value,
        "filename": input.filename,
        "context_snapshot": {
            "actor_user_id": snapshot.actor_user_id,
            "device_id": snapshot.device_id,
            "device_is_new": snapshot.device_is_new,
            "accessed_at": snapshot.accessed_at,
            "after_hours": snapshot.after_hours,
        },
        "outputs": [],
        "failures": [],
    }


def _ordered_outputs(outputs: list[AgentScore]) -> list[AgentScore]:
    by_type = {item.agent_type: item for item in outputs}
    missing = [agent.value for agent in AgentType if agent not in by_type]
    if missing:
        raise RuntimeError(
            "Assessment finished without outputs for: " + ", ".join(missing)
        )
    return [by_type[agent] for agent in AgentType]


def run_assessment(input: AssessmentInput) -> list[AgentScore]:
    """Run the five agents in parallel and return one score per ``AgentType``.

    Each agent writes a trust score in ``[0, 1]`` and a human-readable
    rationale. A single failure or timeout is recorded in graph state and
    surfaced in that agent's rationale with a minimum-trust fail-safe score.
    """
    graph = get_compiled_graph()
    final_state = graph.invoke(
        _initial_state(input),
        config={"configurable": {"thread_id": str(uuid4())}},
    )
    return _ordered_outputs(final_state["outputs"])
