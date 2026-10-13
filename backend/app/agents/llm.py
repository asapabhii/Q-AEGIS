"""Claude-backed scoring for the five agents, ``SPEC.md`` 3.4 / ``PRD.md`` FR-3.

Each agent is a real Claude call that reasons over the assessment context and
returns a trust score in ``[0, 1]`` (higher = more trust, so less protection
warranted) plus a short rationale. The model id and the rationale are recorded on
the ``AgentScore`` so the Merkle audit captures the provenance of every AI
decision. Bit-for-bit reproducibility is not claimed for an LLM; the recorded
model + prompt + response is what makes the decision auditable and reviewable.

Active only when ``AGENT_LLM_BACKEND=anthropic``. Any failure — missing client or
key, API error, timeout, or an unparseable / out-of-range response — is raised so
the orchestrator's fail-safe records minimum trust (:func:`app.agents.scoring.
failure_score`) rather than a fabricated number. Fail-closed, never fail-open.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.agents.scoring import _quantize_trust
from app.agents.state import AssessmentInput
from app.classifier.labels import rank
from app.config import get_settings
from app.db.enums import AgentType
from app.trust_engine.consensus import AgentScore

#: What each agent is asked to judge. Higher score = more trust in this access /
#: content, so a lighter protection posture; lower = more protection warranted.
_AGENT_BRIEFS: dict[AgentType, str] = {
    AgentType.SECURITY: (
        "the SECURITY agent. Judge how much to trust this document access from a "
        "threat and access-security standpoint (new/unknown device, after-hours "
        "access, and the contextual risk all lower trust)."
    ),
    AgentType.COMPLIANCE: (
        "the COMPLIANCE agent. Judge how well this access meets regulatory "
        "expectations for the document's sensitivity label (regulated labels "
        "accessed off a new device or after hours lower trust)."
    ),
    AgentType.CONTEXTUAL: (
        "the CONTEXTUAL agent. Judge trust from the behavioural/contextual "
        "signals of this access (device familiarity, timing, contextual risk)."
    ),
    AgentType.QUANTUM: (
        "the QUANTUM-READINESS agent. Judge trust in a lighter (classical) crypto "
        "posture given harvest-now-decrypt-later exposure: sensitive, long-lived "
        "content lowers trust because it must resist future quantum decryption."
    ),
    AgentType.SUSTAINABILITY: (
        "the SUSTAINABILITY agent. Judge trust in a lightweight protection path "
        "given that higher sensitivity and risk imply heavier crypto and storage "
        "cost; more warranted heavy protection lowers trust in the light path."
    ),
}

_SYSTEM_PROMPT = (
    "You are one of five parallel risk agents in an auditable document-security "
    "system. You are {brief}\n\n"
    "Return ONLY a compact JSON object, no prose, of the form:\n"
    '{{"score": <number 0.0-1.0>, "rationale": "<one or two sentences>"}}\n'
    "score is your trust in [0,1] (1.0 = fully trusted / lightest protection, "
    "0.0 = no trust / maximum protection). When evidence is ambiguous, resolve "
    "toward LESS trust (more protection), never more. The rationale must cite the "
    "specific signals you used."
)


@lru_cache(maxsize=2)
def _client(api_key: str, base_url: str | None, ca_bundle: str | None = None):
    """Cached Anthropic client. Imported lazily so the SDK is optional.

    When ``ca_bundle`` is set the endpoint is reached through a corporate
    TLS-inspection proxy that re-signs traffic with a private CA. We build an
    SSL context trusting the public roots (certifi) plus that CA, and pass it to
    the SDK's own HTTP client. We also clear ``VERIFY_X509_STRICT`` (on by default
    in Python 3.13): interception CAs such as Sophos commonly carry a non-critical
    ``basicConstraints`` extension that strict RFC 5280 checking rejects. Hostname
    verification and normal chain building stay enabled, and this is scoped to the
    LLM client alone — datastore TLS pins its own CA per connection and is
    untouched. With no ``ca_bundle`` the SDK's default (public roots, full strict)
    is used unchanged.
    """
    from anthropic import Anthropic

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    if ca_bundle:
        import ssl

        import certifi
        from anthropic import DefaultHttpxClient

        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cafile=ca_bundle)
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["http_client"] = DefaultHttpxClient(verify=ctx)
    return Anthropic(**kwargs)


def _context_lines(input: AssessmentInput) -> str:
    snap = input.context_snapshot
    return (
        f"- filename: {input.filename!r}\n"
        f"- sensitivity_label: {input.sensitivity_label.value} "
        f"(rank {rank(input.sensitivity_label)}, higher = more sensitive)\n"
        f"- contextual_risk_value: {input.risk_value} (0-1, higher = riskier)\n"
        f"- device_is_new: {snap.device_is_new}\n"
        f"- after_hours: {snap.after_hours}\n"
        f"- device_id: {snap.device_id!r}"
    )


def _parse_score_payload(text: str) -> tuple[float, str]:
    """Extract ``(score, rationale)`` from the model's JSON reply.

    Raises ``ValueError`` if no JSON object is present, the score is missing /
    non-numeric / outside ``[0, 1]``. Callers treat that as an agent failure.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("model reply contained no JSON object")
        data = json.loads(match.group(0))
    if not isinstance(data, dict) or "score" not in data:
        raise ValueError("model reply JSON missing 'score'")
    score = data["score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError(f"model 'score' is not a real number: {score!r}")
    if not (0.0 <= float(score) <= 1.0):
        raise ValueError(f"model 'score' out of [0,1]: {score!r}")
    rationale = str(data.get("rationale") or "").strip()
    return float(score), rationale


def _call_model(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.agent_llm_api_key:
        raise RuntimeError(
            "AGENT_LLM_API_KEY is not configured; cannot run the anthropic agent "
            "backend. Set it (and AGENT_LLM_BACKEND=anthropic) or use the "
            "deterministic backend."
        )
    client = _client(
        settings.agent_llm_api_key,
        settings.agent_llm_base_url,
        settings.agent_llm_ca_bundle,
    )
    # NOTE: the Messages API for the current Claude model line (anthropic SDK
    # >= 1.8) no longer accepts a ``temperature`` kwarg — passing it raises
    # TypeError and would fail every agent call (fail-closed to minimum trust).
    # Determinism of *behaviour* is carried by the system prompt (resolve toward
    # less trust when ambiguous); bit-for-bit reproducibility is not claimed for
    # an LLM (see module docstring), so we rely on the model default sampling.
    message = client.messages.create(
        model=settings.agent_llm_model,
        max_tokens=settings.agent_llm_max_tokens,
        timeout=settings.agent_llm_timeout_seconds,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    ]
    text = "".join(parts).strip()
    if not text:
        raise ValueError("model returned an empty response")
    return text


def score_agent(agent_type: AgentType, input: AssessmentInput) -> AgentScore:
    """Score one agent via Claude. Raises on any failure (fail-closed upstream)."""
    system = _SYSTEM_PROMPT.format(brief=_AGENT_BRIEFS[agent_type])
    user = (
        "Assess this document access and return your JSON verdict.\n\n"
        f"{_context_lines(input)}"
    )
    reply = _call_model(system, user)
    raw_score, rationale = _parse_score_payload(reply)
    score = _quantize_trust(_as_decimal(raw_score))
    model = get_settings().agent_llm_model
    detail = rationale or "no rationale returned"
    provenance = f"[agent={agent_type.value}; model={model}; backend=anthropic]"
    return AgentScore(
        agent_type=agent_type,
        score=score,
        rationale=f"{detail} {provenance}",
    )


def _as_decimal(value: float):
    from decimal import Decimal

    # Round-trip through str so 0.7 does not become 0.6999999999999.
    return Decimal(str(value))
