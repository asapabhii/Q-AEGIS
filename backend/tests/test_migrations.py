"""Migration round-trip, ``SPEC.md`` Section 5.

``alembic upgrade head`` has to build the schema from empty, and ``downgrade base``
has to leave nothing behind, or the next ``upgrade`` fails. A migration that only
works forwards on a database that already happens to be in the right state is not
a migration.

These tests run against a scratch database created and dropped per test, not
against the shared development one. Applying ``downgrade base`` to the database
every other test uses would drop the schema out from under them.
"""

from alembic import command
from sqlalchemy import Engine, text

from tests.conftest import alembic_config

#: Tables the initial migration creates, excluding Alembic's own bookkeeping.
EXPECTED_TABLES = frozenset(
    {
        "users",
        "documents",
        "classification_metadata",
        "manual_overrides",
        "risk_scores",
        "agent_outputs",
        "trust_scores",
        "policy_rules",
        "policy_decisions",
        "crypto_profiles",
        "migration_schedule",
        "audit_log",
    }
)

#: Postgres enum types the migration creates.
EXPECTED_ENUM_TYPES = frozenset(
    {
        "user_role",
        "document_status",
        "sensitivity_label",
        "agent_type",
        "policy_action",
        "crypto_profile_type",
        "migration_status",
    }
)

#: Every trigger the migration installs, as (table, trigger) pairs.
EXPECTED_TRIGGERS = frozenset(
    {
        ("audit_log", "trg_audit_log_no_update"),
        ("audit_log", "trg_audit_log_no_delete"),
        ("audit_log", "trg_audit_log_no_truncate"),
        ("classification_metadata", "trg_classification_metadata_no_update"),
        ("risk_scores", "trg_risk_scores_no_update"),
        ("trust_scores", "trg_trust_scores_no_update"),
        ("crypto_profiles", "trg_crypto_profiles_no_update"),
    }
)


def table_names(engine: Engine) -> frozenset[str]:
    """Return the public tables present in ``engine``'s database."""
    with engine.connect() as connection:
        return frozenset(
            connection.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).all()
        )


def enum_type_names(engine: Engine) -> frozenset[str]:
    """Return the enum types present in ``engine``'s database."""
    with engine.connect() as connection:
        return frozenset(
            connection.scalars(
                text(
                    "SELECT t.typname FROM pg_type t "
                    "JOIN pg_namespace n ON n.oid = t.typnamespace "
                    "WHERE t.typtype = 'e' AND n.nspname = 'public'"
                )
            ).all()
        )


def trigger_pairs(engine: Engine) -> frozenset[tuple[str, str]]:
    """Return (table, trigger) pairs for every non-internal trigger."""
    with engine.connect() as connection:
        return frozenset(
            connection.execute(
                text(
                    "SELECT c.relname, t.tgname FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "WHERE NOT t.tgisinternal"
                )
            ).all()
        )


def test_upgrade_builds_the_schema_from_empty(scratch_engine: Engine) -> None:
    """``upgrade head`` against a database with nothing in it."""
    assert table_names(scratch_engine) == frozenset()

    command.upgrade(alembic_config(str(scratch_engine.url)), "head")

    assert EXPECTED_TABLES <= table_names(scratch_engine)
    assert enum_type_names(scratch_engine) == EXPECTED_ENUM_TYPES


def test_upgrade_installs_every_append_only_trigger(scratch_engine: Engine) -> None:
    """The append-only guarantee ships with the schema, not as a manual step.

    ``SPEC.md`` 3.8 requires database-level enforcement, so a developer who runs
    only ``alembic upgrade head`` must end up with it. If these were applied by
    hand, a fresh database would silently accept an UPDATE on the audit log.
    """
    command.upgrade(alembic_config(str(scratch_engine.url)), "head")
    assert EXPECTED_TRIGGERS <= trigger_pairs(scratch_engine)


def test_downgrade_leaves_nothing_behind(scratch_engine: Engine) -> None:
    """Including the enum types, which outlive the tables that used them.

    A leftover type is the failure mode this catches: the tables drop cleanly, the
    downgrade reports success, and the next upgrade dies on ``CREATE TYPE``.
    """
    config = alembic_config(str(scratch_engine.url))
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    remaining = table_names(scratch_engine)
    assert remaining <= {"alembic_version"}
    assert enum_type_names(scratch_engine) == frozenset()
    assert trigger_pairs(scratch_engine) == frozenset()


def test_the_full_round_trip_is_clean(scratch_engine: Engine) -> None:
    """upgrade head, downgrade base, upgrade head, with no manual repair."""
    config = alembic_config(str(scratch_engine.url))

    command.upgrade(config, "head")
    first_pass = table_names(scratch_engine)

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    assert table_names(scratch_engine) == first_pass
    assert enum_type_names(scratch_engine) == EXPECTED_ENUM_TYPES
    assert EXPECTED_TRIGGERS <= trigger_pairs(scratch_engine)


def test_the_schema_matches_the_models_with_no_drift(scratch_engine: Engine) -> None:
    """``alembic check`` finds nothing to generate after ``upgrade head``.

    Catches the specific mistake of editing a model and forgetting the migration.
    ``docs/data-dictionary.md`` is the written source of truth; this is the
    mechanical half of keeping the three in step.
    """
    config = alembic_config(str(scratch_engine.url))
    command.upgrade(config, "head")

    # Raises AutogenerateDiffsDetected when the models and the database disagree.
    command.check(config)
