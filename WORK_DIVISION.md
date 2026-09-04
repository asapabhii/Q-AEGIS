# Q-AEGIS SHIELD: WORK DIVISION

Ownership by module. Reference: `SPEC.md` for what each module does, `PRD.md` for the requirement each module satisfies.

---

## Abhinav

- Repository setup, CI/CD pipeline, branch protection.
- Trust Score computation, `SPEC.md` 3.5, PRD FR-4.
- Contextual risk engine, `SPEC.md` 3.3, PRD FR-2.
- Multi-agent orchestration (LangGraph), `SPEC.md` 3.4, PRD FR-3.
- Knowledge graph, `SPEC.md` 3.11, PRD FR-10.
- Agentic RAG, `SPEC.md` 3.12, PRD FR-11.
- Coordinates the three open tool decisions in `SPEC.md` Section 2 and ensures each is logged to `docs/decisions.md` once made.
- Final review and merge authority on all pull requests.

## Udhav

- Policy engine, `SPEC.md` 3.6, PRD FR-5, including the Cedar vs OPA decision at implementation time.
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
