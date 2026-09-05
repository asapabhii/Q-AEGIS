"""Relational data model, ``SPEC.md`` Section 5.

The twelve core PostgreSQL tables, their SQLAlchemy models, the session factory,
and the repositories that write them. The authoritative column-level definition
is ``docs/data-dictionary.md``; a change here without a change there is a defect
per ``AGENTS.md``.

This package is not one of the numbered modules in ``SPEC.md`` Section 3. It is
the shared schema every one of those modules persists through, which is why it
lives on its own rather than inside any single feature subpackage. Nothing here
implements a module's behavior; behavior belongs to the owning subpackage.

Four tables are append-only history (``classification_metadata``,
``risk_scores``, ``trust_scores``, ``crypto_profiles``) and ``audit_log`` is
append-only against UPDATE, DELETE, and TRUNCATE. That is enforced by database
triggers installed in the initial migration, not by convention here. Do not add
an update path to any of them, and do not work around the triggers.
"""
