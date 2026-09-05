"""Enumerated domain values, mirroring the native Postgres enum types.

Each class here corresponds to one Postgres enum type named in
``docs/data-dictionary.md``. Adding a value requires a migration, which is the
point: an unconstrained ``varchar`` lets a typo become a silently distinct
category, and these columns feed security decisions.

``SensitivityLabel`` is deliberately not redefined here. It already exists in
:mod:`app.classifier.labels`, where its ordering defines what "more sensitive"
means for the classifier's fail-safe. Two copies of that enum would be two
places to get the ordering wrong.
"""

from enum import Enum

from app.classifier.labels import SensitivityLabel

__all__ = [
    "AgentType",
    "AuditEventType",
    "CryptoProfileType",
    "DocumentStatus",
    "MigrationStatus",
    "PolicyAction",
    "SensitivityLabel",
    "UserRole",
    "enum_values",
]


def enum_values(enum_class: type[Enum]) -> list[str]:
    """Return an enum's values for SQLAlchemy's ``values_callable``.

    Without this, SQLAlchemy persists enum *names* rather than *values*, so
    ``UserRole.DATA_OWNER`` would be stored as ``DATA_OWNER`` while the API and
    the data dictionary both say ``data_owner``. Passing this to every
    ``Enum(...)`` column keeps the stored value identical to the documented one.
    """
    return [member.value for member in enum_class]


class UserRole(str, Enum):
    """A user's role, ``users.role``.

    The authorization guard in :mod:`app.api.deps` checks against this enum, so
    a role that can be stored is a role that can be reasoned about, and there is
    no second list to keep in step.

    ``CISO`` and ``ENGINEER`` exist here because the data dictionary defines
    them. ``PRD.md`` Section 5 lists six personas and folds the CISO into the
    Security Admin row, so the two documents disagree; the schema keeps the
    wider set, since a role that exists in the data but not in the enum is the
    worse failure.
    """

    DATA_OWNER = "data_owner"
    SECURITY_ANALYST = "security_analyst"
    SECURITY_ADMIN = "security_admin"
    COMPLIANCE_OFFICER = "compliance_officer"
    AUDITOR = "auditor"
    CISO = "ciso"
    ENGINEER = "engineer"


class DocumentStatus(str, Enum):
    """Lifecycle stage of a document, ``documents.current_status``.

    ``REGISTERED`` means the document's metadata row exists but no file has been
    stored yet. It is separate from ``UPLOADED`` because calling a document
    uploaded when nothing was uploaded puts a false statement in the lifecycle
    field, and this build has no object storage (``PRD.md`` FR-1's upload screen
    is unbuilt).
    """

    REGISTERED = "registered"
    UPLOADED = "uploaded"
    CLASSIFIED = "classified"
    PROTECTED = "protected"
    ARCHIVED = "archived"


class AgentType(str, Enum):
    """Which of the five risk agents produced an output, ``agent_outputs.agent_type``.

    Five agents per assessment, per ``SPEC.md`` 3.4 and ``PRD.md`` FR-3.
    """

    SECURITY = "security"
    COMPLIANCE = "compliance"
    CONTEXTUAL = "contextual"
    QUANTUM = "quantum"
    SUSTAINABILITY = "sustainability"


class PolicyAction(str, Enum):
    """An action a policy rule can take, and the domain of a policy decision.

    Used by ``policy_rules.action``, ``policy_decisions.ai_recommendation``, and
    ``policy_decisions.final_decision``. All three share one domain because a
    matching rule's action *becomes* the final decision (``SPEC.md`` 3.6), so a
    recommendation and a decision have to be comparable.
    """

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_MFA = "require_mfa"
    FORCE_PQC = "force_pqc"


class CryptoProfileType(str, Enum):
    """Protection profile selected for a document, ``crypto_profiles.profile_type``.

    Parameter sets are in ``SPEC.md`` Section 6 and are not restated here.
    ``HYBRID`` is ``X25519MLKEM768``; ``POST_QUANTUM`` is ML-KEM-1024 with
    ML-DSA-87.
    """

    AES256 = "aes256"
    HYBRID = "hybrid"
    POST_QUANTUM = "post_quantum"


class MigrationStatus(str, Enum):
    """Progress of a scheduled post-quantum upgrade, ``migration_schedule.status``."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class AuditEventType(str, Enum):
    """Known ``audit_log.event_type`` values.

    Unlike every other enum here this is NOT a Postgres enum type. The column is
    ``varchar(60)`` on purpose: every module in ``SPEC.md`` Section 3 will add
    event types as it lands, and gating each one behind a migration would make
    the audit log the thing that slows down writing to the audit log.

    This class is the write-side vocabulary, so callers within this codebase
    share one spelling instead of scattering string literals. A value absent
    here is still storable, by design.
    """

    DOCUMENT_REGISTERED = "document_registered"
    CLASSIFICATION_COMPLETED = "classification_completed"
    MANUAL_OVERRIDE = "manual_override"
    RISK_SCORE_COMPUTED = "risk_score_computed"
    TRUST_SCORE_UPDATED = "trust_score_updated"
    POLICY_DECISION_RECORDED = "policy_decision_recorded"
    CRYPTO_PROFILE_SELECTED = "crypto_profile_selected"
