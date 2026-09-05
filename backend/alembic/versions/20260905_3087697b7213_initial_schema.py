"""initial schema: the twelve core tables and their append-only enforcement

Implements ``SPEC.md`` Section 5. Column-level reference:
``docs/data-dictionary.md``.

Two things in here are load-bearing and should not be "simplified" later.

**Enum types are created explicitly, before the tables.** ``sensitivity_label``
is used by three columns across two tables and ``policy_action`` by three columns
across two more. Left to inline ``sa.Enum(...)``, SQLAlchemy emits ``CREATE TYPE``
at each first use and the second table's creation fails outright. So the types are
created once here and every column references them with ``create_type=False``.

**Values are spelled out literally rather than imported from
``app.db.enums``.** A migration is a historical snapshot: it must keep producing
the schema it produced on the day it was written, even after the application's
enums have gained values. Importing them would make this file silently change
meaning as the code moves, which is how a migration chain stops being
reproducible.

Revision ID: 3087697b7213
Revises:
Create Date: 2026-09-05 04:39:36.851060+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3087697b7213"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- Enum types -------------------------------------------------------------

USER_ROLE = postgresql.ENUM(
    "data_owner",
    "security_analyst",
    "security_admin",
    "compliance_officer",
    "auditor",
    "ciso",
    "engineer",
    name="user_role",
    create_type=False,
)
DOCUMENT_STATUS = postgresql.ENUM(
    "registered",
    "uploaded",
    "classified",
    "protected",
    "archived",
    name="document_status",
    create_type=False,
)
SENSITIVITY_LABEL = postgresql.ENUM(
    "PUBLIC",
    "INTERNAL",
    "CONFIDENTIAL",
    "RESTRICTED",
    name="sensitivity_label",
    create_type=False,
)
AGENT_TYPE = postgresql.ENUM(
    "security",
    "compliance",
    "contextual",
    "quantum",
    "sustainability",
    name="agent_type",
    create_type=False,
)
POLICY_ACTION = postgresql.ENUM(
    "allow",
    "deny",
    "require_mfa",
    "force_pqc",
    name="policy_action",
    create_type=False,
)
CRYPTO_PROFILE_TYPE = postgresql.ENUM(
    "aes256",
    "hybrid",
    "post_quantum",
    name="crypto_profile_type",
    create_type=False,
)
MIGRATION_STATUS = postgresql.ENUM(
    "pending",
    "in_progress",
    "done",
    name="migration_status",
    create_type=False,
)

ENUM_TYPES = (
    USER_ROLE,
    DOCUMENT_STATUS,
    SENSITIVITY_LABEL,
    AGENT_TYPE,
    POLICY_ACTION,
    CRYPTO_PROFILE_TYPE,
    MIGRATION_STATUS,
)

# --- Append-only enforcement ------------------------------------------------

#: Tables where UPDATE is rejected outright, ``SPEC.md`` Section 5.
#:
#: A new decision is a new row. These four are history tables and the audit log
#: only means something if a past decision cannot be silently rewritten.
UPDATE_REJECTED_TABLES = (
    "classification_metadata",
    "risk_scores",
    "trust_scores",
    "crypto_profiles",
    "audit_log",
)

#: Tables where DELETE and TRUNCATE are also rejected.
#:
#: ``audit_log`` only. ``PRD.md`` FR-7 states its guarantee absolutely ("no code
#: path can update or delete an existing entry"), so it is enforced absolutely.
#: The four history tables above are not included on purpose: "never updated in
#: place" is what they require, and a prohibition with no requirement behind it
#: invites someone to disable the trigger later for an unrelated reason.
DELETE_REJECTED_TABLES = ("audit_log",)

REJECT_FUNCTION_NAME = "qaegis_reject_append_only_write"

# ERRCODE restrict_violation is SQLSTATE 23001, which psycopg surfaces as
# psycopg.errors.RestrictViolation. Raising a specific, documented code rather
# than the default P0001 means a caller can catch this exactly, and the test
# suite asserts on the exception type instead of matching message text.
CREATE_REJECT_FUNCTION = f"""
CREATE FUNCTION {REJECT_FUNCTION_NAME}() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'Table % is append-only: % is rejected. A new decision is a new row. '
        'See SPEC.md 3.8 and PRD.md FR-7.', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$;
"""


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ENUM_TYPES:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "documents",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("current_status", DOCUMENT_STATUS, nullable=False),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_documents_uploaded_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(
        op.f("ix_documents_uploaded_by"), "documents", ["uploaded_by"], unique=False
    )
    op.create_table(
        "policy_rules",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("rule_name", sa.String(length=150), nullable=False),
        sa.Column(
            "condition_expr", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("action", POLICY_ACTION, nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority > 0", name=op.f("ck_policy_rules_priority_positive")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_policy_rules_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_rules")),
        sa.UniqueConstraint("rule_name", name=op.f("uq_policy_rules_rule_name")),
    )
    op.create_index(
        op.f("ix_policy_rules_created_by"), "policy_rules", ["created_by"], unique=False
    )
    # Partial, on active rules only, so a superseded rule can be deactivated and
    # keep its historical priority instead of being renumbered or deleted.
    op.create_index(
        "uq_policy_rules_active_priority",
        "policy_rules",
        ["priority"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "audit_log",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("prev_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("merkle_root_at_time", sa.CHAR(length=64), nullable=False),
        sa.Column("frontier", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_audit_log_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
        # A fork is two entries claiming the same predecessor. NULLS NOT
        # DISTINCT extends that to the genesis entry, which would otherwise be
        # duplicable because Postgres treats each null as unique by default.
        sa.UniqueConstraint(
            "document_id",
            "prev_hash",
            name="no_forked_chain",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_document_id"), "audit_log", ["document_id"], unique=False
    )
    op.create_table(
        "classification_metadata",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("sensitivity_label", SENSITIVITY_LABEL, nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("model_version", sa.String(length=30), nullable=False),
        sa.Column("is_defaulted", sa.Boolean(), nullable=False),
        sa.Column(
            "classified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name=op.f("ck_classification_metadata_confidence_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_classification_metadata_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classification_metadata")),
    )
    op.create_index(
        op.f("ix_classification_metadata_classified_at"),
        "classification_metadata",
        ["classified_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classification_metadata_document_id"),
        "classification_metadata",
        ["document_id"],
        unique=False,
    )
    op.create_table(
        "manual_overrides",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("overridden_by", sa.Uuid(), nullable=False),
        sa.Column("original_label", SENSITIVITY_LABEL, nullable=False),
        sa.Column("new_label", SENSITIVITY_LABEL, nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column(
            "overridden_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # PRD.md FR-12's 20-character minimum, enforced in the database as well
        # as in the API. It is an acceptance criterion, so no path should be able
        # to store a row that violates it.
        sa.CheckConstraint(
            "char_length(justification) >= 20",
            name=op.f("ck_manual_overrides_justification_min_length"),
        ),
        sa.CheckConstraint(
            "new_label <> original_label",
            name=op.f("ck_manual_overrides_label_actually_changed"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_manual_overrides_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["overridden_by"],
            ["users.id"],
            name=op.f("fk_manual_overrides_overridden_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_manual_overrides")),
    )
    op.create_index(
        op.f("ix_manual_overrides_document_id"),
        "manual_overrides",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manual_overrides_overridden_by"),
        "manual_overrides",
        ["overridden_by"],
        unique=False,
    )
    op.create_table(
        "migration_schedule",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("scheduled_upgrade_date", sa.Date(), nullable=True),
        sa.Column("status", MIGRATION_STATUS, nullable=False),
        sa.Column(
            "constraint_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority_rank > 0",
            name=op.f("ck_migration_schedule_priority_rank_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_migration_schedule_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_migration_schedule")),
    )
    op.create_index(
        op.f("ix_migration_schedule_document_id"),
        "migration_schedule",
        ["document_id"],
        unique=False,
    )
    op.create_table(
        "policy_decisions",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        # Nullable, and this is the common case: no rule fired and the AI
        # recommendation stood (SPEC.md 3.6). Not a placeholder no-op rule.
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("ai_recommendation", POLICY_ACTION, nullable=False),
        sa.Column("final_decision", POLICY_ACTION, nullable=False),
        sa.Column("overridden", sa.Boolean(), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "overridden = (final_decision IS DISTINCT FROM ai_recommendation)",
            name=op.f("ck_policy_decisions_overridden_matches_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_policy_decisions_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["policy_rules.id"],
            name=op.f("fk_policy_decisions_rule_id_policy_rules"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_decisions")),
    )
    op.create_index(
        op.f("ix_policy_decisions_decided_at"),
        "policy_decisions",
        ["decided_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_decisions_document_id"),
        "policy_decisions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_decisions_rule_id"),
        "policy_decisions",
        ["rule_id"],
        unique=False,
    )
    op.create_table(
        "risk_scores",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("risk_value", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column(
            "context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_value >= 0 AND risk_value <= 1",
            name=op.f("ck_risk_scores_risk_value_range"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_risk_scores_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_scores")),
    )
    op.create_index(
        op.f("ix_risk_scores_computed_at"), "risk_scores", ["computed_at"], unique=False
    )
    op.create_index(
        op.f("ix_risk_scores_document_id"), "risk_scores", ["document_id"], unique=False
    )
    op.create_table(
        "agent_outputs",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("risk_score_id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", AGENT_TYPE, nullable=False),
        sa.Column("score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "score >= 0 AND score <= 1", name=op.f("ck_agent_outputs_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["risk_score_id"],
            ["risk_scores.id"],
            name=op.f("fk_agent_outputs_risk_score_id_risk_scores"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_outputs")),
        # One output per agent per assessment; a duplicate means an agent ran
        # twice and the consensus function would double-count it.
        sa.UniqueConstraint("risk_score_id", "agent_type", name="one_output_per_agent"),
    )
    op.create_index(
        op.f("ix_agent_outputs_risk_score_id"),
        "agent_outputs",
        ["risk_score_id"],
        unique=False,
    )
    op.create_table(
        "trust_scores",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("risk_score_id", sa.Uuid(), nullable=False),
        sa.Column("consensus_value", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("consensus_version", sa.String(length=30), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "consensus_value >= 0 AND consensus_value <= 1",
            name=op.f("ck_trust_scores_consensus_value_range"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_trust_scores_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["risk_score_id"],
            ["risk_scores.id"],
            name=op.f("fk_trust_scores_risk_score_id_risk_scores"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trust_scores")),
    )
    op.create_index(
        op.f("ix_trust_scores_computed_at"),
        "trust_scores",
        ["computed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trust_scores_document_id"),
        "trust_scores",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trust_scores_risk_score_id"),
        "trust_scores",
        ["risk_score_id"],
        unique=False,
    )
    op.create_table(
        "crypto_profiles",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("trust_score_id", sa.Uuid(), nullable=False),
        sa.Column("profile_type", CRYPTO_PROFILE_TYPE, nullable=False),
        sa.Column(
            "selected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_crypto_profiles_document_id_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trust_score_id"],
            ["trust_scores.id"],
            name=op.f("fk_crypto_profiles_trust_score_id_trust_scores"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crypto_profiles")),
    )
    op.create_index(
        op.f("ix_crypto_profiles_document_id"),
        "crypto_profiles",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crypto_profiles_selected_at"),
        "crypto_profiles",
        ["selected_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crypto_profiles_trust_score_id"),
        "crypto_profiles",
        ["trust_score_id"],
        unique=False,
    )

    _install_append_only_triggers()


def downgrade() -> None:
    _drop_append_only_triggers()

    op.drop_index(
        op.f("ix_crypto_profiles_trust_score_id"), table_name="crypto_profiles"
    )
    op.drop_index(op.f("ix_crypto_profiles_selected_at"), table_name="crypto_profiles")
    op.drop_index(op.f("ix_crypto_profiles_document_id"), table_name="crypto_profiles")
    op.drop_table("crypto_profiles")
    op.drop_index(op.f("ix_trust_scores_risk_score_id"), table_name="trust_scores")
    op.drop_index(op.f("ix_trust_scores_document_id"), table_name="trust_scores")
    op.drop_index(op.f("ix_trust_scores_computed_at"), table_name="trust_scores")
    op.drop_table("trust_scores")
    op.drop_index(op.f("ix_agent_outputs_risk_score_id"), table_name="agent_outputs")
    op.drop_table("agent_outputs")
    op.drop_index(op.f("ix_risk_scores_document_id"), table_name="risk_scores")
    op.drop_index(op.f("ix_risk_scores_computed_at"), table_name="risk_scores")
    op.drop_table("risk_scores")
    op.drop_index(op.f("ix_policy_decisions_rule_id"), table_name="policy_decisions")
    op.drop_index(
        op.f("ix_policy_decisions_document_id"), table_name="policy_decisions"
    )
    op.drop_index(op.f("ix_policy_decisions_decided_at"), table_name="policy_decisions")
    op.drop_table("policy_decisions")
    op.drop_index(
        op.f("ix_migration_schedule_document_id"), table_name="migration_schedule"
    )
    op.drop_table("migration_schedule")
    op.drop_index(
        op.f("ix_manual_overrides_overridden_by"), table_name="manual_overrides"
    )
    op.drop_index(
        op.f("ix_manual_overrides_document_id"), table_name="manual_overrides"
    )
    op.drop_table("manual_overrides")
    op.drop_index(
        op.f("ix_classification_metadata_document_id"),
        table_name="classification_metadata",
    )
    op.drop_index(
        op.f("ix_classification_metadata_classified_at"),
        table_name="classification_metadata",
    )
    op.drop_table("classification_metadata")
    op.drop_index(op.f("ix_audit_log_document_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(
        "uq_policy_rules_active_priority",
        table_name="policy_rules",
        postgresql_where=sa.text("active"),
    )
    op.drop_index(op.f("ix_policy_rules_created_by"), table_name="policy_rules")
    op.drop_table("policy_rules")
    op.drop_index(op.f("ix_documents_uploaded_by"), table_name="documents")
    op.drop_table("documents")
    op.drop_table("users")

    # Enum types outlive their tables, so dropping the tables is not enough. A
    # leftover type makes a re-upgrade fail on CREATE TYPE, which is exactly what
    # the migration round-trip test in the suite catches.
    bind = op.get_bind()
    for enum_type in reversed(ENUM_TYPES):
        enum_type.drop(bind, checkfirst=True)


def _trigger_name(table: str, operation: str) -> str:
    """Return the trigger name for one table and operation."""
    return f"trg_{table}_no_{operation}"


def _install_append_only_triggers() -> None:
    """Install the database-level append-only guards.

    ``SPEC.md`` 3.8 requires this at the database level rather than trusting
    application discipline, and ``AGENTS.md`` forbids working around it.
    """
    op.execute(CREATE_REJECT_FUNCTION)

    for table in UPDATE_REJECTED_TABLES:
        op.execute(
            f"CREATE TRIGGER {_trigger_name(table, 'update')} "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {REJECT_FUNCTION_NAME}();"
        )

    for table in DELETE_REJECTED_TABLES:
        op.execute(
            f"CREATE TRIGGER {_trigger_name(table, 'delete')} "
            f"BEFORE DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {REJECT_FUNCTION_NAME}();"
        )
        # Separate, and not redundant: TRUNCATE does not fire row-level
        # triggers, so without a statement-level guard the whole table stays
        # erasable in one statement despite the DELETE trigger above.
        op.execute(
            f"CREATE TRIGGER {_trigger_name(table, 'truncate')} "
            f"BEFORE TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {REJECT_FUNCTION_NAME}();"
        )


def _drop_append_only_triggers() -> None:
    """Remove the guards, so the tables can be dropped on downgrade."""
    for table in DELETE_REJECTED_TABLES:
        for operation in ("truncate", "delete"):
            op.execute(
                f"DROP TRIGGER IF EXISTS {_trigger_name(table, operation)} ON {table};"
            )
    for table in UPDATE_REJECTED_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS {_trigger_name(table, 'update')} ON {table};"
        )
    op.execute(f"DROP FUNCTION IF EXISTS {REJECT_FUNCTION_NAME}();")
