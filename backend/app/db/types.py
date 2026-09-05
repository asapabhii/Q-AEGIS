"""Reusable SQLAlchemy type objects for the native Postgres enum types.

One object per Postgres type, shared by every column that uses it. This matters:
``sensitivity_label`` appears on three columns across two tables, and building a
separate ``Enum(...)`` for each would have SQLAlchemy emit ``CREATE TYPE`` three
times for one type. Sharing the instance means the type is defined once and every
column that references it stays in step by construction.

The Python enums themselves live in :mod:`app.db.enums`, which stays free of any
SQLAlchemy import so the domain values can be used without pulling in the ORM.
"""

from sqlalchemy import Enum as SAEnum

from app.db.enums import (
    AgentType,
    CryptoProfileType,
    DocumentStatus,
    MigrationStatus,
    PolicyAction,
    SensitivityLabel,
    UserRole,
    enum_values,
)

USER_ROLE = SAEnum(UserRole, name="user_role", values_callable=enum_values)

DOCUMENT_STATUS = SAEnum(
    DocumentStatus, name="document_status", values_callable=enum_values
)

SENSITIVITY_LABEL = SAEnum(
    SensitivityLabel, name="sensitivity_label", values_callable=enum_values
)

AGENT_TYPE = SAEnum(AgentType, name="agent_type", values_callable=enum_values)

POLICY_ACTION = SAEnum(PolicyAction, name="policy_action", values_callable=enum_values)

CRYPTO_PROFILE_TYPE = SAEnum(
    CryptoProfileType, name="crypto_profile_type", values_callable=enum_values
)

MIGRATION_STATUS = SAEnum(
    MigrationStatus, name="migration_status", values_callable=enum_values
)

#: Every enum type the initial migration creates, in creation order.
#: The migration iterates this rather than repeating the list, so adding a type
#: here cannot leave the migration behind.
ALL_ENUM_TYPES = (
    USER_ROLE,
    DOCUMENT_STATUS,
    SENSITIVITY_LABEL,
    AGENT_TYPE,
    POLICY_ACTION,
    CRYPTO_PROFILE_TYPE,
    MIGRATION_STATUS,
)
