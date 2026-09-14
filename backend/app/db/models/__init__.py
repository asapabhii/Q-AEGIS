"""SQLAlchemy models for the twelve tables in ``SPEC.md`` Section 5.

Grouped by pipeline stage rather than one file per table, so a reader following a
document's lifecycle reads them in order: identity, the document itself,
classification, risk and trust, policy, protection, and the audit log that every
stage writes to.

Column-level authority is ``docs/data-dictionary.md``.

ORM ``relationship()`` attributes are deliberately absent. Every query in this
package is an explicit ``select()`` in a repository, which keeps the loading
strategy visible at the call site instead of buried in a lazy-load default. Add
one where it genuinely earns its place, not by reflex.
"""

from app.db.models.audit import AuditLog
from app.db.models.classification import ClassificationMetadata, ManualOverride
from app.db.models.crypto import CryptoProfile, DocumentCiphertext, MigrationSchedule
from app.db.models.documents import Document
from app.db.models.identity import User
from app.db.models.policy import PolicyDecision, PolicyRule
from app.db.models.risk import AgentOutput, RiskScore, TrustScore

#: Every table that is append-only against UPDATE at the database level.
#: The migration installs the triggers; this tuple exists so the test suite
#: asserts against one list rather than a hand-maintained copy of it.
UPDATE_REJECTED_TABLES: tuple[str, ...] = (
    ClassificationMetadata.__tablename__,
    RiskScore.__tablename__,
    TrustScore.__tablename__,
    CryptoProfile.__tablename__,
    AuditLog.__tablename__,
)

#: Tables that additionally reject DELETE and TRUNCATE. ``PRD.md`` FR-7 states
#: the audit log's guarantee absolutely, so it is enforced absolutely.
DELETE_REJECTED_TABLES: tuple[str, ...] = (AuditLog.__tablename__,)

__all__ = [
    "AgentOutput",
    "AuditLog",
    "ClassificationMetadata",
    "CryptoProfile",
    "DELETE_REJECTED_TABLES",
    "Document",
    "DocumentCiphertext",
    "ManualOverride",
    "MigrationSchedule",
    "PolicyDecision",
    "PolicyRule",
    "RiskScore",
    "TrustScore",
    "UPDATE_REJECTED_TABLES",
    "User",
]
