# Q-AEGIS SHIELD: WORK DIVISION

Ownership by module. Reference: `SPEC.md` for what each module does, `PRD.md` for the requirement each module satisfies.

This is the current, authoritative allocation of work across the three inventors — Abhinav, Udhav, and Sukhmani — not a historical record. The split is intended to be equitable: each owner carries a comparable share of the system's substance — Abhinav the shared foundation and the scoring spine (data model, contextual risk, five-agent orchestration, trust consensus, knowledge graph, agentic RAG), Udhav the entire enforcement-and-cryptography half (policy engine, crypto-agile engine, tamper-evident audit, crypto-shredding, migration scheduler), and Sukhmani the classification model, the full operator frontend, documentation, and cross-module test authorship. All three are named inventors on the patent filing and authors on the project; keep `PRD.md`, `Q-AEGIS-PATENT-SPECIFICATION.md`, and `Q-AEGIS-PROJECT-REPORT.md` consistent with this file.

---

## Abhinav

- Repository setup, CI/CD pipeline, branch protection.
- **Data model and persistence layer, `SPEC.md` Section 5.** The twelve core PostgreSQL tables as SQLAlchemy models plus Alembic migrations, including the database-level append-only enforcement on `audit_log` that `AGENTS.md` requires. Nobody owned this before; it sat between three module owners and got skipped. It is on the critical path: `classification_metadata`, `risk_scores`, `trust_scores`, and `crypto_profiles` are append-only history tables, and Phase 3 cannot write a risk score, a trust score, or a policy decision anywhere until they exist, which blocks Udhav as much as it blocks the integration work.
  - Known open defect this closes, tracked here so it is not mistaken for finished work: `POST /api/v1/classify` computes a classification and persists nothing, no `classification_metadata` row and no `audit_log` entry. `PRD.md` Section 7 states that a decision without a corresponding audit entry is a defect, so Phase 1 is functionally complete but has this gap open against it.
  - Read before starting: `SPEC.md` Section 5 declines to define the schema and points at a "system design reference document" for the column-level data dictionary and ER diagram. That document is not in this repository and `docs/` has no `er-diagram.svg`. Either bring it in under `docs/` first or define the schema in-repo and make that the cited source of truth, but do not invent columns against a reference nobody can open.
- ~~Drives the Cedar vs OPA decision to a logged conclusion, `SPEC.md` 2.2~~ Done, 2026-09-05: OPA with Rego, logged in `docs/decisions.md`, with the implementation constraints written into `SPEC.md` 3.6. `SPEC.md` 3.6 is no longer blocked.
- Trust Score computation, `SPEC.md` 3.5, PRD FR-4.
- Contextual risk engine, `SPEC.md` 3.3, PRD FR-2.
- Multi-agent orchestration (LangGraph), `SPEC.md` 3.4, PRD FR-3.
- Knowledge graph, `SPEC.md` 3.11, PRD FR-10.
- Agentic RAG, `SPEC.md` 3.12, PRD FR-11.
- Coordinates the two remaining open tool decisions in `SPEC.md` Section 2, the event bus (2.3) and the vector store (2.4), and ensures each is logged to `docs/decisions.md` once made. The policy engine decision (2.2) is closed.
- Final review and merge authority on all pull requests.

## Udhav

- Policy engine, `SPEC.md` 3.6, PRD FR-5. Unblocked: the engine is OPA with Rego, decided 2026-09-05 and logged in `docs/decisions.md`. `SPEC.md` 3.6 lists the four constraints that decision commits the module to, read those and the decision entry first. If you think the call is wrong, say so before writing code rather than after.
- Crypto-Agile Protection Engine, `SPEC.md` 3.7, PRD FR-6.
- Tamper-evident audit log, `SPEC.md` 3.8, PRD FR-7.
- Crypto-shredding, `SPEC.md` 3.9, PRD FR-8.
- Migration scheduler, `SPEC.md` 3.10, PRD FR-9.
- Required reviewer on any pull request touching `backend/app/crypto/`, `backend/app/policy/`, or `backend/app/audit/`, regardless of author.

## Sukhmani

- Sensitivity classifier, `SPEC.md` 3.2, PRD FR-1.
- Frontend build, `SPEC.md` 3.13, PRD FR-12 through FR-16, all six screens.
- Documentation: keeps `README.md`, `PRD.md`, `SPEC.md`, and API docs synchronized with what the code actually does. A gap between documented and actual behavior is treated as a defect she owns closing, regardless of which module it's in.
- Test authorship across all modules, including tests for code written by Abhinav or Udhav. A pull request lacking a corresponding test update is flagged in review before merge.
- Backlog maintenance: keeps the persona-based backlog current as modules or screens change.

---

## How pull requests move

A change to `backend/app/crypto/`, `backend/app/policy/`, or `backend/app/audit/` requires Udhav's review before merge, given the consequence of an error in those three modules. Every change requires a test update in the same pull request, not a follow-up one, per Sukhmani's ownership above. Abhinav holds final merge authority on `main` across all modules.

If actual workload stops matching this division, for example one person underwater while another has slack, resolve it directly between the three of you and update this file to reflect the new reality. This document describes a working allocation, not a fixed contract.
