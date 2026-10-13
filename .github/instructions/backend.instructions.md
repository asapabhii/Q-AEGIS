---
applyTo: "backend/**/*.py"
---

Read `SPEC.md` Section 3 for the module you're editing before writing code, module boundaries are structural, not a suggestion.

- FastAPI for API routers under `backend/app/api/`. Pydantic models for every request/response body, no raw dicts crossing an API boundary.
- SQLAlchemy models mirror the data dictionary in the system design reference exactly, column names and types included. A renamed column requires updating that document in the same pull request.
- Alembic for every schema change, no hand-edited migrations, no direct ALTER TABLE outside a migration file.
- Format with `black`, lint with `flake8`, both run in CI.
- Append-only tables (`classification_metadata`, `risk_scores`, `trust_scores`, `crypto_profiles`, `audit_log`, `audit_signing_keys`, `audit_checkpoints`) get INSERT-only repository methods. If an `update_*` method seems needed for one of these, the logic belongs somewhere else, not in a workaround here.
- Every function in `backend/app/crypto/`, `backend/app/audit/`, and `backend/app/policy/` has a unit test in the same pull request that introduces it.
