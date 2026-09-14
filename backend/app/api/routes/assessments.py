"""Full P0 assessment API, risk → agents → trust → policy → crypto → encrypt."""

from decimal import Decimal
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, status
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, TrustScoreCaller, resolve_seeded_actor
from app.crypto.exceptions import CryptoConfigurationError, LiboqsUnavailableError
from app.db.enums import CryptoProfileType, PolicyAction
from app.policy.engine import PolicyEngineError
from app.risk_engine.pipeline import run_full_assessment
from app.risk_engine.schemas import MAX_DEVICE_ID_CHARS
from app.risk_engine.scorer import ContextSnapshot

router = APIRouter(tags=["assessments"])


class AssessmentRequest(BaseModel):
    """Run the full protection pipeline for one classified document."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    device_id: str = Field(min_length=1, max_length=MAX_DEVICE_ID_CHARS)
    device_is_new: bool
    accessed_at: AwareDatetime
    after_hours: bool
    content: str | None = Field(default=None, max_length=500_000)
    ai_recommendation: PolicyAction | None = None

    @field_validator("device_id")
    @classmethod
    def device_id_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "device_id must contain at least one non-whitespace character"
            )
        return value


class AssessmentResponse(BaseModel):
    """Outcome of one full assessment pass."""

    document_id: UUID
    risk_score_id: UUID
    trust_score_id: UUID
    consensus_value: Decimal
    ai_recommendation: PolicyAction
    policy_decision_id: UUID
    final_decision: PolicyAction
    overridden: bool
    crypto_profile_id: UUID
    profile_type: CryptoProfileType
    ciphertext_id: UUID | None
    encrypted: bool
    reselected: bool


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run risk, agents, trust, policy, and crypto for one document",
)
def create_assessment(
    request: AssessmentRequest,
    session: DbSession,
    caller: TrustScoreCaller,
) -> AssessmentResponse:
    """Orchestrate the P0 chain and optionally encrypt ``content``.

    Agent scores come from LangGraph (``SPEC.md`` 3.4), not the client.
    ``ai_recommendation`` may be omitted and is then derived from consensus.
    """
    actor = resolve_seeded_actor(session, caller)
    snapshot = ContextSnapshot(
        actor_user_id=actor.id,
        device_id=request.device_id,
        device_is_new=request.device_is_new,
        accessed_at=request.accessed_at,
        after_hours=request.after_hours,
    )
    plaintext = request.content.encode("utf-8") if request.content is not None else None
    try:
        result = run_full_assessment(
            session,
            document_id=request.document_id,
            actor=actor,
            snapshot=snapshot,
            plaintext=plaintext,
            ai_recommendation=request.ai_recommendation,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PolicyEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except CryptoConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LiboqsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        orig = exc.orig
        if isinstance(orig, psycopg.errors.UniqueViolation):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent outputs already exist for this risk score.",
            ) from exc
        raise

    return AssessmentResponse(
        document_id=result.document_id,
        risk_score_id=result.risk_score_id,
        trust_score_id=result.trust_score_id,
        consensus_value=result.consensus_value,
        ai_recommendation=result.ai_recommendation,
        policy_decision_id=result.policy_decision_id,
        final_decision=result.final_decision,
        overridden=result.overridden,
        crypto_profile_id=result.crypto_profile_id,
        profile_type=result.profile_type,
        ciphertext_id=result.ciphertext_id,
        encrypted=result.encrypted,
        reselected=result.reselected,
    )
