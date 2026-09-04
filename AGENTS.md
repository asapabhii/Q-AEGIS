# AGENTS.md

This file is read automatically by every agent working in this repository (Antigravity, OpenCode, GitHub Copilot coding agent, and Cursor all support this format natively). It is the standing instruction set. Read it before starting any task. For anything beyond what's here, the canonical deep-reference document is `SPEC.md`, read the specific numbered section relevant to your task before writing code, don't guess at module boundaries or algorithm choices.

## Project

Q-AEGIS Shield: a platform that classifies data sensitivity, continuously scores risk from five independent AI agents, combines them into one continuous Trust Score, gates that score through a deterministic policy layer capable of overriding the AI outright, then selects AES-256, hybrid (X25519MLKEM768), or full post-quantum encryption accordingly. Every decision anywhere in that chain writes to a tamper-evident, append-only audit log.

## Repository layout

```
backend/app/{classifier,risk_engine,agents,trust_engine,policy,crypto,audit,scheduler,graph,rag,api}
backend/tests/
frontend/src/
infra/           # docker-compose, deployment config
docs/            # architecture-diagram.svg, er-diagram.svg, decisions.md
```

Each `backend/app/` subpackage corresponds to exactly one numbered module in `SPEC.md` Section 5. Do not merge modules together for convenience, the separation is structural, not cosmetic.

## Build, test, and run

```bash
# backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload          # run
pytest --cov=app --cov-fail-under=70   # test, coverage gate is enforced, not advisory
black --check . && flake8 .            # lint, must pass before any PR

# frontend
cd frontend && npm run dev
npm run lint

# full stack, local
cd infra && docker-compose up
```

## Ownership by module

Read this before starting work on any module. If you are an agent acting on behalf of one of these three people, only touch the modules they own unless explicitly told otherwise for that session.

| Module (SPEC.md section) | Owner |
|---|---|
| Repo/CI/CD, integration, Trust Engine (5.5), multi-agent orchestration (5.4) | Abhinav |
| Policy engine (5.6), crypto engine (5.7), audit log (5.8), crypto-shredding (5.9), migration scheduler (5.10) | Udhav |
| Classifier (5.2), frontend (5.13), documentation, test authorship across all modules | Sukhmani |

Full detail: `WORK_DIVISION.md`.

## Code style

Backend: Python, `black` formatting, `flake8` linting, type hints on every function signature. Pydantic models for every API request/response, no raw dicts crossing an API boundary. SQLAlchemy models mirror the data dictionary in the system design document exactly, do not rename a column without updating that document in the same PR.

Frontend: TypeScript only, no plain `.js` files. Tailwind for styling. Centralize API calls in `frontend/src/lib/api/`, no inline `fetch()` calls scattered through components.

## Testing requirements

70% coverage floor on new code, enforced in CI, not a suggestion. The policy engine (5.6) requires one test per rule type and per condition operator, not a single happy-path test. The audit log (5.8) requires explicit tampered-entry and odd-count-of-leaves test cases, not just a clean-chain verification test. Any PR touching a module without a corresponding test update should be treated as incomplete.

## Security rules, apply to every task, no exceptions

- Never write a secret, API key, or credential into code or committed config. `.env` is gitignored from the first commit. `.env.example` holds dummy values only.
- Every API endpoint checks caller identity and role (`users.role`) server-side before acting. Never rely on frontend UI hiding as access control.
- TLS in transit everywhere, including local docker-compose services.
- Every input field's validation rule (documented per-screen in the system design doc) is enforced server-side, not only client-side.
- `audit_log` is append-only. Never write UPDATE or DELETE against it, in application code or migrations, this is additionally enforced by a database trigger, do not work around it.
- Anything in `backend/app/crypto/` must state plainly, in every docstring, that liboqs is not independently audited. Do not claim audited-grade or FIPS-certified guarantees the library doesn't back up.
- A stub is labeled a stub in its code, its docstring, and its tests. Never let placeholder logic pass as finished work.
- Confidence-based defaults resolve toward more protection, never less, in both the classifier (5.2) and the Trust Engine (5.5).

## Encryption reference, do not guess these values

Full parameter tables and rationale: `SPEC.md` Section 13. Summary for quick reference:

- **AES-256**: AES-256-GCM, classical baseline.
- **Hybrid**: `X25519MLKEM768` exactly, the named group already deployed in TLS 1.3 by Chrome, Edge, and Cloudflare. Do not invent a different pairing.
- **Full post-quantum**: ML-KEM-1024 (key encapsulation) plus ML-DSA-87 (signatures), via `liboqs-python`.
- Never use the retired names CRYSTALS-Kyber or CRYSTALS-Dilithium in new code or docs, use ML-KEM and ML-DSA.

## Scope boundary

Not building this phase: plugin marketplace, incident-cost simulator, live third-party connectors (Slack, GitHub, cloud storage, IoT). If a task seems to require one of these, stop and flag it rather than building it, check `SPEC.md` Section 4 first.

## Decisions intentionally left open

Three tool choices are not pre-decided, and should not be defaulted to silently: Cedar vs OPA (5.6), Redis Streams vs Kafka (5.1), pgvector vs Qdrant (5.12). Evaluation criteria for each: `SPEC.md` Section 11. Whoever makes the call logs it, with reasoning, to `docs/decisions.md`.

## Commit and PR conventions

Commit messages reference the SPEC.md section number being implemented, for example `feat(5.6): add rule evaluation for policy engine`. PRs touching `backend/app/crypto/`, `backend/app/policy/`, or `backend/app/audit/` require review from Udhav regardless of who authored them, these three modules carry the highest consequence for a mistake.
