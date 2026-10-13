# AGENTS.md

Read this before any task. It is the standing instruction set, auto-read by every agent tool that supports the `AGENTS.md` convention (Antigravity, OpenCode, GitHub Copilot coding agent, Cursor, and others). For anything deeper, `SPEC.md` is the canonical reference — read the specific numbered section for your task before writing code; do not guess module boundaries or algorithm choices. `CLAUDE.md` (local only, git-ignored) carries the live real-vs-stub inventory, current PR state, and host/Docker gotchas — read it too if it exists in your working tree.

## Project

Q-AEGIS Shield: a platform that classifies data sensitivity, continuously scores risk from five independent AI agents, combines them into one continuous Trust Score, gates that score through a deterministic policy layer capable of overriding the AI outright, then selects AES-256, hybrid (`X25519MLKEM768`), or full post-quantum encryption accordingly. Every decision anywhere in that chain writes to a tamper-evident, append-only, Merkle-chained audit log. The bar is production-grade and patent-credible — not a demo, not "prototype vibes," not stub-as-finished.

## Git and version control

Never run `git commit`, `git push`, `git merge`, or `gh pr merge` autonomously. Always stop and present the exact command(s) for a human to review and run, with a one-line explanation of each. This holds every session, regardless of who is driving.

Attribution when you author commits/PRs for a human to run:
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- PR descriptions end with: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

Never commit secrets. Already git-ignored and must stay that way: `.env`/`.env.*` (only `.env.example` with dummy values is tracked), `.claude/` (holds `ANTHROPIC_AUTH_TOKEN`), `.codex/`, `config/` (holds a live `secret_key`), `infra/certs/`, and scratch logs (`backend/backend_test.txt`, `backend/backend_fullrun.txt`). Stage files explicitly; never blanket `git add -A` when secret-bearing dirs are dirty.

## Writing style for commits, PRs, and comments

State what changed and why, plainly, the way a developer actually writes. No exhaustive self-narrated structure, no explaining why a section exists before the section, no restating obvious inferences. If a sentence is only there to sound thorough, cut it.

## Repository layout

```
backend/app/{classifier,risk_engine,agents,trust_engine,policy,crypto,audit,scheduler,graph,rag,api,auth,documents,event_bus}
backend/tests/
frontend/src/     # Next.js App Router, TypeScript, Tailwind
infra/            # docker-compose, deployment config, local certs (infra/certs, git-ignored)
docs/             # data-dictionary.md (schema source of truth), decisions.md, LOCAL_DEV.md
```

Each `backend/app/` subpackage maps to exactly one numbered module in `SPEC.md` Section 3. Do not merge modules for convenience — the separation is structural, not cosmetic.

## Ownership

Q-AEGIS is authored and invented by three people — Abhinav, Udhav, and Sukhmani. `WORK_DIVISION.md` records the current, authoritative, equitable split of modules across the three; it is a live allocation, not history. All three are named inventors on the patent filing and authors on the project, and every document (`PRD.md`, `Q-AEGIS-PATENT-SPECIFICATION.md`, `Q-AEGIS-PROJECT-REPORT.md`) must keep inventorship and authorship consistent with that division. Abhinav is the repository owner and holds final merge authority; that is an operational role, not sole inventorship.

## Build, test, and run

```bash
# backend (host is Python 3.10; the app/prod image is Python 3.13)
cd backend && source venv/bin/activate      # PowerShell: .\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload               # run
pytest --cov=app --cov-fail-under=70        # coverage gate is enforced, not advisory
black --check . && flake8 .                 # must pass before any PR

# frontend
cd frontend && npm run dev
npm run lint && npm test && npm run build

# full stack, local
cd infra && docker compose --env-file ..\.env up -d
```

`black`/`flake8` `max-line-length = 88`, `black` target `py310`. Ignore any IDE that flags E501 at 79 — it is wrong for this repo.

## Engineering invariants that bite

These are the non-obvious rules that have already cost real debugging time. Violating one reintroduces a fixed bug.

- **`import oqs` must stay inside the function that uses it**, never at module top level. A module-load import triggers a liboqs *source build* on the host (no compiler → failure) and breaks in the slim image (no git). Real post-quantum signing/KEM runs only where liboqs is installed; tests gate it behind `oqs_available()` skips. liboqs lives in the Docker image at `/opt/liboqs`.
- **CI Postgres must be `pgvector/pgvector:pg17`.** Plain `postgres:17-alpine` cannot `CREATE EXTENSION vector` and every migration fails.
- **Append-only tables** (`classification_metadata`, `risk_scores`, `trust_scores`, `crypto_profiles`, `audit_log`, `audit_signing_keys`, `audit_checkpoints`) are enforced at the database level by the plpgsql function `qaegis_reject_append_only_write` (raises `SQLSTATE 23001`, `restrict_violation`). Trigger naming: `trg_{table}_no_{operation}`. UPDATE/DELETE triggers are `FOR EACH ROW`; TRUNCATE is `FOR EACH STATEMENT`. New migrations only `CREATE TRIGGER` referencing the existing function — do not recreate the function. `audit_log`, `audit_signing_keys`, and `audit_checkpoints` also reject DELETE and TRUNCATE. When you add an append-only table, update the model `__init__` `UPDATE_REJECTED_TABLES`/`DELETE_REJECTED_TABLES` tuples, the migration triggers, `test_migrations.py`'s expected-trigger list, and `test_db_append_only.py`'s `UPDATE_TARGETS` + `one_row_per_history_table` fixture.
- **Crypto fails closed.** Hybrid/PQ without liboqs never falls back to AES; invalid/non-finite trust raises rather than silently choosing a weaker profile.
- **Ambiguity resolves toward more protection**, always — in the classifier (low confidence → more sensitive label) and the Trust Engine (toward less trust).

## Security rules, apply to every task, no exceptions

- Never write a secret, API key, or credential into code or committed config.
- Every API endpoint checks caller identity and role (`users.role`) server-side before acting. Never treat frontend hiding as access control. The dev-header bypass is allowed only in dev/test envs (`settings.dev_header_bypass_allowed()`), never in production.
- TLS in transit everywhere, including local docker-compose services.
- Every input validation rule is enforced server-side, not only client-side.
- `audit_log` is append-only — never UPDATE/DELETE it in code or migrations, and do not work around the trigger.
- Everything in `backend/app/crypto/` and every audit-checkpoint docstring must state plainly that liboqs is not independently audited; OQS-OpenSSL is dev/interop only; key management this phase is env-configured secrets, not HSM (`PRD.md` NG5). Never claim FIPS-certified or audited-grade guarantees the library does not back.
- A stub is labeled a stub in its code, docstring, and tests. Never let placeholder logic pass as finished work — replacing stubs with real implementations is the job.

## Testing requirements

70% coverage floor on new code, enforced in CI. The policy engine (3.6) needs one test per rule type and per condition operator, not one happy path. The audit log (3.8) needs explicit tampered-entry and odd-leaf test cases. Audit checkpoints need tamper-root, tamper-signature, and wrong-key rejection cases. Any PR touching a module without a corresponding test update is incomplete.

## Encryption reference, do not guess these values

Full tables and rationale: `SPEC.md` Section 6. Summary:

- **AES-256**: AES-256-GCM, classical baseline.
- **Hybrid**: `X25519MLKEM768` exactly — the TLS 1.3 named group already deployed by Chrome, Edge, and Cloudflare. Do not invent a different pairing.
- **Full post-quantum**: ML-KEM-1024 (KEM) + ML-DSA-87 (signatures) via `liboqs-python`. Verified real sizes: ML-DSA-87 public key 2592 B, secret key 4896 B, signature 4627 B.
- Never use the retired names CRYSTALS-Kyber or CRYSTALS-Dilithium in new code or docs — use ML-KEM and ML-DSA.

## Scope boundary

Not this phase (PRD NG1–NG5): plugin marketplace, incident-cost simulator, live third-party connectors (Slack/GitHub/cloud/IoT), public production hosting, HSM-backed keys. If a task seems to require one, stop and flag it — check `SPEC.md` Section 4 first. Patent text may describe these as future extensions; do not implement them by default.

## Decisions intentionally left open

None currently. Closed and logged in `docs/decisions.md` with revisit conditions: Redis Streams over Kafka (3.1), pgvector over Qdrant (3.12), OPA+Rego compiled to WASM and evaluated in-process over Cedar (3.6), and the calibrated trust→crypto and trust→action bands. A re-evaluation starts from the logged decision and its stated revisit condition (measured scale need), not from scratch. Do not reopen any of these in passing, and do not write Cedar into `backend/app/policy/`.

## Commit and PR conventions

Commit messages reference the `SPEC.md` section implemented, e.g. `feat(3.6): add rule evaluation for policy engine`. PRs touching `backend/app/crypto/`, `backend/app/policy/`, or `backend/app/audit/` carry the highest consequence — review them with extra care.
